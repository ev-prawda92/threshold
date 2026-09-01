"""Req audit: what each requirement actually costs.

Computed from captured dispositions, never from the posting alone. A gate is
only expensive if it is the recorded reason people were turned away, and the
only way to know that is to have asked at the moment of the decision.

Every number here reports its own denominator. A rate over four dispositions is
not a finding, and the report says so rather than rendering a confident 25%.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

MIN_SAMPLE = 8          # below this, report counts and withhold rates


@dataclass
class GateStat:
    ordinal: int
    text: str
    label: str
    rejections: int = 0            # dispositions attributed to this requirement
    sole_reason: int = 0           # ...where it was the ONLY reason
    share: float | None = None     # of all rejections, None when undersampled
    suggested_but_not_chosen: int = 0
    chosen_but_not_suggested: int = 0

    @property
    def is_sole_blocker(self) -> bool:
        return self.sole_reason > 0


@dataclass
class Audit:
    slug: str
    title: str
    applicants: int = 0
    rejections: int = 0
    gates: list[GateStat] = field(default_factory=list)
    other_count: int = 0
    stronger_field_count: int = 0
    unattributed: int = 0
    reroute: list[tuple[str, str, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def undersampled(self) -> bool:
        return self.rejections < MIN_SAMPLE

    @property
    def other_rate(self) -> float | None:
        if self.undersampled or not self.rejections:
            return None
        return self.other_count / self.rejections

    @property
    def suggestion_accuracy(self) -> float | None:
        """How often the scorer's pre-checked guess matched what was chosen.

        This is the number that says whether the pre-checking is helping or
        quietly training recruiters to click through a wrong default.
        """
        total = sum(g.rejections for g in self.gates)
        if not total or self.undersampled:
            return None
        wrong = sum(g.suggested_but_not_chosen + g.chosen_but_not_suggested
                    for g in self.gates)
        return max(0.0, 1 - wrong / (2 * total))


def audit_req(conn, slug: str) -> Audit:
    from . import store

    req = store.load_req(conn, slug)
    if req is None:
        raise KeyError(slug)
    disps = store.dispositions_for(conn, slug)
    applicants = conn.execute(
        "SELECT COUNT(*) n FROM applications WHERE req_slug=?", (slug,)).fetchone()["n"]

    a = Audit(slug=slug, title=req.title, applicants=applicants)
    by_ordinal = {r.ordinal: r for r in req.requirements}
    stats = {r.ordinal: GateStat(r.ordinal, r.text, r.label.value)
             for r in req.requirements if r.is_gate}

    rejections = [d for d in disps if d["outcome"] == "rejected"]
    a.rejections = len(rejections)

    for d in rejections:
        chosen = [o for o in d["reason_ordinals"] if o in stats]
        suggested = [o for o in d["suggested_ordinals"] if o in stats]

        if d["reason_kind"] == "other":
            a.other_count += 1
        elif d["reason_kind"] == "stronger_field":
            a.stronger_field_count += 1
        elif not chosen:
            a.unattributed += 1

        for o in chosen:
            stats[o].rejections += 1
            if len(chosen) == 1:
                stats[o].sole_reason += 1
        for o in set(suggested) - set(chosen):
            stats[o].suggested_but_not_chosen += 1
        for o in set(chosen) - set(suggested):
            stats[o].chosen_but_not_suggested += 1

    if a.rejections >= MIN_SAMPLE:
        for s in stats.values():
            s.share = s.rejections / a.rejections
    else:
        a.notes.append(
            f"{a.rejections} rejections captured — below the {MIN_SAMPLE} needed before "
            "rates mean anything. Counts shown, percentages withheld.")

    a.gates = sorted(stats.values(), key=lambda s: (-s.rejections, s.ordinal))

    if a.other_rate is not None and a.other_rate >= 0.3:
        a.notes.append(
            f"{a.other_rate:.0%} of rejections were 'not about the stated requirements'. "
            "The posting is not describing how this team is actually deciding.")

    a.reroute = _reroute(conn, slug)
    if a.unattributed:
        a.notes.append(f"{a.unattributed} rejections were recorded with no reason attached.")
    return a


def _reroute(conn, slug: str) -> list[tuple[str, str, str]]:
    """Candidates rejected here who clear every gate on another open req.

    Uses the scorer, not similarity: 'clears every stated requirement over
    there' is a claim you can put in front of a hiring manager.
    """
    from . import store
    from .profile import load_profile
    from .score import Status, score

    rejected = conn.execute("""
        SELECT c.id, c.name, c.profile_path FROM applications a
        JOIN dispositions d ON d.application_id = a.id
        JOIN candidates c ON c.id = a.candidate_id
        WHERE a.req_slug = ? AND d.outcome = 'rejected' AND c.profile_path <> ''
        """, (slug,)).fetchall()
    others = [r["slug"] for r in conn.execute(
        "SELECT slug FROM reqs WHERE slug <> ?", (slug,)).fetchall()]

    out: list[tuple[str, str, str]] = []
    cache: dict[str, object] = {}
    for cand in rejected:
        try:
            prof = cache.get(cand["profile_path"]) or load_profile(cand["profile_path"])
        except Exception:
            continue
        cache[cand["profile_path"]] = prof
        for other in others:
            req = store.load_req(conn, other)
            card = score(req, prof)
            gates = card.gate_findings
            if gates and all(f.status is Status.MET for f in gates):
                out.append((cand["name"], other, req.title))
    return out
