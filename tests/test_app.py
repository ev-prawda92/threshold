"""End-to-end behaviour of the working system.

The tests that matter are the ones that stop the app asserting things it cannot
support: no citation, no claim; no sample, no percentage.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from threshold import store
from threshold.audit import MIN_SAMPLE, audit_req
from threshold.parse import parse_req, req_from_labeled
from threshold.profile import load_profile
from threshold.score import Status, Verdict, score

DATA = Path("data/aurora-pittsburgh.yaml")
PPM = "senior-staff-product-and-program-manager"


@pytest.fixture(scope="module")
def postings():
    return {p["id"]: p for p in yaml.safe_load(DATA.read_text())["postings"]}


@pytest.fixture(scope="module")
def profile():
    return load_profile("profile.yaml")


@pytest.fixture()
def db(tmp_path, postings):
    path = tmp_path / "t.db"
    store.init(path)
    with store.connect(path) as conn:
        for p in postings.values():
            store.save_req(conn, req_from_labeled(p, "Aurora"))
        store.add_candidate(conn, "evan", "Evan", "profile.yaml")
    return path


# ---------------------------------------------------------------- parsing

def test_parser_skips_responsibilities_and_keeps_qualifications():
    text = """
Responsibilities
- Own the roadmap and herd the cats

Required Qualifications
- 7+ years of program management experience
- Proficiency in Python

Preferred Qualifications
- Advanced degree
"""
    req = parse_req(text, "Some Role", "Acme")
    assert [r.section for r in req.requirements] == ["required", "required", "desirable"]
    assert "roadmap" not in " ".join(r.text for r in req.requirements)


def test_parser_joins_wrapped_bullets():
    text = "Required Qualifications\n- 7+ years of experience\n  across regulated industries\n"
    req = parse_req(text, "R", "A")
    assert req.requirements[0].text.endswith("regulated industries")


# ---------------------------------------------------------------- scoring

def test_only_a_missed_gate_blocks(postings, profile):
    card = score(req_from_labeled(postings["staff-software-engineer-perception"]), profile)
    assert card.verdict is Verdict.BLOCKED
    missed = [f for f in card.gate_findings if f.status is Status.MISSING]
    assert missed and any("c++" in " ".join(f.terms) for f in missed)


def test_preferences_never_block(postings, profile):
    card = score(req_from_labeled(postings["staff-safety-standards-engineer"]), profile)
    prefs = [f for f in card.findings if not f.requirement.is_gate]
    assert prefs
    assert not any(f.blocks for f in prefs)


def test_unknown_is_not_silently_treated_as_met(postings, profile):
    card = score(req_from_labeled(postings[PPM]), profile)
    f = next(f for f in card.gate_findings if "Agile and Waterfall" in f.requirement.text)
    assert f.status is Status.UNKNOWN
    assert card.verdict is Verdict.OPEN_QUESTION


def test_every_met_finding_cites_or_explains(postings, profile):
    for p in postings.values():
        for f in score(req_from_labeled(p), profile).findings:
            if f.status is Status.MET:
                assert f.citations or f.detail, f"{f.requirement.text[:40]} asserts without support"


def test_years_gate_merges_overlapping_spans(profile):
    total = sum(e.months() for e in profile.evidence if e.start and e.end)
    assert profile.employment_months() < total


def test_absent_list_produces_a_finding_not_a_shrug(postings, profile):
    card = score(req_from_labeled(postings["staff-safety-research-scientist"]), profile)
    f = next(f for f in card.gate_findings if "publications" in f.requirement.text.lower())
    assert f.status is Status.MISSING
    assert "absent" in f.detail


def test_a_short_term_cannot_match_a_longer_absent_entry(profile):
    assert "hardware_development_npi" in profile.absent
    req = parse_req("Required Qualifications\n- Experience integrating hardware\n", "R", "A")
    f = score(req, profile).findings[0]
    assert f.status is not Status.MISSING


# ---------------------------------------------------------------- capture

def test_audit_withholds_rates_below_the_sample_floor(db):
    with store.connect(db) as conn:
        app_id = store.apply_to(conn, PPM, "evan")
        store.record_disposition(conn, app_id, "rejected", [1], "gate")
        a = audit_req(conn, PPM)
    assert a.rejections == 1 and a.undersampled
    assert all(g.share is None for g in a.gates)
    assert any("below the" in n for n in a.notes)


def test_pool_cost_is_computed_only_from_captured_reasons(db):
    with store.connect(db) as conn:
        for i in range(MIN_SAMPLE + 2):
            store.add_candidate(conn, f"c{i}", f"Candidate {i}")
            app_id = store.apply_to(conn, PPM, f"c{i}")
            store.record_disposition(conn, app_id, "rejected", [1] if i % 2 == 0 else [6], "gate")
        a = audit_req(conn, PPM)
    top = a.gates[0]
    assert top.share is not None and 0 < top.share <= 1
    assert sum(g.rejections for g in a.gates) == a.rejections


def test_stronger_field_is_not_counted_as_a_gate_failure(db):
    with store.connect(db) as conn:
        for i in range(MIN_SAMPLE):
            store.add_candidate(conn, f"s{i}", f"S{i}")
            app_id = store.apply_to(conn, PPM, f"s{i}")
            store.record_disposition(conn, app_id, "rejected", [], "stronger_field")
        a = audit_req(conn, PPM)
    assert a.stronger_field_count == MIN_SAMPLE
    assert all(g.rejections == 0 for g in a.gates)


def test_high_other_rate_is_surfaced_as_a_finding(db):
    with store.connect(db) as conn:
        for i in range(MIN_SAMPLE + 2):
            store.add_candidate(conn, f"o{i}", f"O{i}")
            app_id = store.apply_to(conn, PPM, f"o{i}")
            store.record_disposition(conn, app_id, "rejected", [], "other")
        a = audit_req(conn, PPM)
    assert a.other_rate == 1.0
    assert any("not describing" in n for n in a.notes)


def test_suggestion_drift_is_measured(db):
    with store.connect(db) as conn:
        for i in range(MIN_SAMPLE + 2):
            store.add_candidate(conn, f"d{i}", f"D{i}")
            app_id = store.apply_to(conn, PPM, f"d{i}")
            store.record_disposition(conn, app_id, "rejected", [1], "gate",
                                     suggested_ordinals=[6])
        a = audit_req(conn, PPM)
    assert a.suggestion_accuracy is not None and a.suggestion_accuracy < 0.6


def test_reprocessing_appends_rather_than_overwrites(db):
    with store.connect(db) as conn:
        app_id = store.apply_to(conn, PPM, "evan")
        store.record_disposition(conn, app_id, "rejected", [1], "gate")
        store.record_disposition(conn, app_id, "rejected", [6], "gate")
        rows = store.dispositions_for(conn, PPM)
    assert len(rows) == 2
