"""Load the demo database: real reqs, one real profile, synthetic candidates.

    python -m threshold.seed

The requirement text is verbatim from live postings. The candidates other than
the owner of profile.yaml are invented, and their dispositions are scripted so
the audit has something to compute. Every generated file says so.
"""

from __future__ import annotations

import os
import random
from pathlib import Path

import yaml

from . import store
from .parse import req_from_labeled

DB = os.environ.get("THRESHOLD_DB", "threshold.db")
CAND_DIR = Path("demo/candidates")

# name, years, tags, note
PEOPLE = [
    ("Maya Alvarez", 9, ["program-management", "software-development", "agile"],
     "PM, health tech"),
    ("Devon Okonkwo", 11, ["program-management", "hardware-integration", "agile", "waterfall"],
     "TPM, medical devices"),
    ("Priya Raman", 8, ["product-management", "machine-learning", "agile"], "PM, data platform"),
    ("Tomas Baptiste", 6, ["program-management", "agile"], "PM, fintech"),
    ("Ruth Chen", 14, ["program-management", "hardware-integration", "waterfall", "safety-critical"],
     "Director, med device programs"),
    ("Piotr Nowak", 10, ["product-management", "software-development"], "Group PM, SaaS"),
    ("Amara Diallo", 7, ["program-management", "software-development", "agile", "waterfall"],
     "TPM, logistics"),
    ("Ben Whitfield", 12, ["program-management", "safety-critical", "clinical"],
     "Program director, health system"),
    ("Sofia Marchetti", 9, ["product-management", "agile", "user-research"], "PM, marketplace"),
    ("Idris Karim", 5, ["program-management", "agile"], "Sr PM, consumer"),
    ("Hannah Lindqvist", 13, ["program-management", "hardware-integration", "waterfall"],
     "TPM, industrial"),
    ("Marcus Bell", 8, ["product-management", "software-development", "agile"], "PM, devtools"),
]


def write_candidate(name: str, years: int, tags: list[str], note: str) -> tuple[str, Path]:
    cid = name.lower().replace(" ", "-")
    start_year = 2026 - years
    doc = {
        "person": {"name": name, "location": "Pittsburgh, PA" if years % 3 else "Austin, TX",
                   "current_scope": "senior", "target_band_floor_usd": 150000},
        "evidence": [
            {"id": "emp.main", "kind": "employment", "org": "Prior employer",
             "title": note, "start": f"{start_year}-01", "end": "2026-01",
             "claims": [f"{note} — {years} years of progressively responsible delivery"],
             "tags": tags, "source": "synthetic demo profile"},
        ],
        "absent": ["autonomous_vehicles", "robotics", "aerospace"]
                  + ([] if "waterfall" in tags else ["waterfall"])
                  + ([] if "agile" in tags else ["agile"]),
    }
    CAND_DIR.mkdir(parents=True, exist_ok=True)
    path = CAND_DIR / f"{cid}.yaml"
    path.write_text("# Synthetic demo candidate — invented, not a real person.\n"
                    + yaml.safe_dump(doc, sort_keys=False, width=100))
    return cid, path


def main() -> None:
    try:
        Path(DB).unlink(missing_ok=True)
    except OSError:
        # Some mounts refuse deletes. Re-seeding on top is fine: reqs are
        # replaced by slug and dispositions append.
        pass
    store.init(DB)
    data = yaml.safe_load(Path("data/aurora-pittsburgh.yaml").read_text())
    rng = random.Random(11)

    with store.connect(DB) as conn:
        for posting in data["postings"]:
            store.save_req(conn, req_from_labeled(posting, data.get("company", "")))

        # the real profile
        store.add_candidate(conn, "evan-prawda", "Evan Prawda", "profile.yaml",
                            "independent — program leadership, safety-critical software")
        store.apply_to(conn, "senior-staff-product-and-program-manager", "evan-prawda")

        for name, years, tags, note in PEOPLE:
            cid, path = write_candidate(name, years, tags, note)
            store.add_candidate(conn, cid, name, str(path), note)

        slug = "senior-staff-product-and-program-manager"
        req = store.load_req(conn, slug)
        gates = {r.ordinal: r.text.lower() for r in req.gates}
        travel = next((o for o, t in gates.items() if "travel" in t), None)
        method = next((o for o, t in gates.items() if "agile" in t), None)
        years_g = next((o for o, t in gates.items() if "minimum 7 years" in t), None)
        office = next((o for o, t in gates.items() if "offices at least" in t), None)

        # A scripted but uneven distribution: travel does most of the filtering,
        # the methodology bullet does some, and a few rejections are honest
        # "other" -- which is the finding, not noise.
        script = [
            ([travel], "gate"), ([travel], "gate"), ([travel, method], "gate"),
            ([method], "gate"), ([travel], "gate"), ([years_g], "gate"),
            ([travel], "gate"), ([method], "gate"), ([office], "gate"),
            ([travel], "gate"), ([], "stronger_field"), ([], "other"),
        ]
        for (name, *_), (ordinals, kind) in zip(PEOPLE, script):
            cid = name.lower().replace(" ", "-")
            app_id = store.apply_to(conn, slug, cid)
            suggested = [o for o in (ordinals or []) if o] + (
                [travel] if kind == "other" and rng.random() < 0.5 else [])
            store.record_disposition(
                conn, app_id, "rejected", [o for o in ordinals if o], kind,
                "hiring manager preferred a hardware background" if kind == "other" else "",
                suggested_ordinals=[o for o in suggested if o])

        # a second req with a pipeline, so rerouting has somewhere to point
        for name, *_ in PEOPLE[:4]:
            store.apply_to(conn, "technical-program-manager-hw-systems-and-safety",
                           name.lower().replace(" ", "-"))

    print(f"seeded {DB}: {len(data['postings'])} reqs, {len(PEOPLE) + 1} candidates, "
          f"{len(PEOPLE)} dispositions")


if __name__ == "__main__":
    main()
