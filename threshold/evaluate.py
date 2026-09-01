"""Evaluation harness for the requirement classifier.

Two numbers matter, and they are not the same:

  * Three-class accuracy -- how well the taxonomy is reproduced.
  * Gate F1 -- how well the class that can actually disqualify someone is
    found. A false negative here tells a candidate to apply for something they
    cannot get. A false positive tells them not to apply for something they
    could. The second error is worse and invisible, so precision and recall are
    reported separately rather than blended into one score.

    python -m threshold.evaluate data/aurora-pittsburgh.yaml
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from .classify import HeuristicClassifier, Label

CLASSES = [Label.GATE, Label.SOFT_REQUIRED, Label.PREFERENCE]


def load(path: str | Path):
    data = yaml.safe_load(Path(path).read_text())
    rows = []
    for posting in data["postings"]:
        for req in posting["requirements"]:
            rows.append({
                "posting": posting["id"],
                "section": req["section"],
                "text": req["text"],
                "gold": Label(req["label"]),
                "note": req.get("note", ""),
            })
    return rows


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def main(path: str = "data/aurora-pittsburgh.yaml") -> int:
    rows = load(path)
    clf = HeuristicClassifier()
    confusion: dict[tuple[Label, Label], int] = Counter()
    errors = []

    for row in rows:
        pred = clf.predict(row["text"], row["section"])
        confusion[(row["gold"], pred.label)] += 1
        if pred.label is not row["gold"]:
            errors.append((row, pred))

    n = len(rows)
    correct = sum(v for (g, p), v in confusion.items() if g is p)

    print(f"\n  classifier: {clf.name}")
    print(f"  dataset:    {path}  ({n} requirements, "
          f"{len({r['posting'] for r in rows})} postings)\n")
    print(f"  three-class accuracy   {correct}/{n}  {correct / n:.1%}\n")

    header = "  gold \\ pred        " + "".join(f"{c.value:>16}" for c in CLASSES)
    print(header)
    print("  " + "-" * (len(header) - 2))
    for g in CLASSES:
        line = f"  {g.value:<18}" + "".join(
            f"{confusion[(g, p)]:>16}" for p in CLASSES)
        print(line)

    print()
    for c in CLASSES:
        tp = confusion[(c, c)]
        fp = sum(confusion[(g, c)] for g in CLASSES if g is not c)
        fn = sum(confusion[(c, p)] for p in CLASSES if p is not c)
        p, r, f = prf(tp, fp, fn)
        star = "  <- the one that decides applications" if c is Label.GATE else ""
        print(f"  {c.value:<16} precision {p:5.1%}   recall {r:5.1%}   F1 {f:5.1%}{star}")

    # The decision the product actually makes is binary: is this disqualifying?
    b_tp = confusion[(Label.GATE, Label.GATE)]
    b_fp = sum(confusion[(g, Label.GATE)] for g in CLASSES if g is not Label.GATE)
    b_fn = sum(confusion[(Label.GATE, p)] for p in CLASSES if p is not Label.GATE)
    b_tn = n - b_tp - b_fp - b_fn
    print(f"\n  binary gate / not-gate  {(b_tp + b_tn) / n:.1%}"
          f"   ({b_fp} false gates, {b_fn} missed gates)")

    if errors:
        print(f"\n  {len(errors)} misclassifications\n")
        by_posting = defaultdict(list)
        for row, pred in errors:
            by_posting[row["posting"]].append((row, pred))
        for posting, items in by_posting.items():
            print(f"  {posting}")
            for row, pred in items:
                text = row["text"]
                text = text if len(text) <= 96 else text[:93] + "..."
                print(f"    gold {row['gold'].value:<14} pred {pred.label.value:<14} "
                      f"[{', '.join(pred.fired)}]")
                print(f"      {text}")
                if row["note"]:
                    print(f"      note: {row['note']}")
            print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
