"""Command line for the working system.

    python -m threshold seed                  build the demo database
    python -m threshold serve                 run the app on :8000
    python -m threshold score <req-slug>      score a req against profile.yaml
    python -m threshold audit <req-slug>      what each gate is costing
    python -m threshold eval                  classifier accuracy on the labelled set
"""

from __future__ import annotations

import argparse
import os
import sys

DB = os.environ.get("THRESHOLD_DB", "threshold.db")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="threshold", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed")
    p_serve = sub.add_parser("serve")
    p_serve.add_argument("--port", type=int, default=8000)
    p_score = sub.add_parser("score"); p_score.add_argument("slug")
    p_score.add_argument("--profile", default="profile.yaml")
    p_audit = sub.add_parser("audit"); p_audit.add_argument("slug")
    sub.add_parser("eval")
    args = ap.parse_args(argv)

    if args.cmd == "seed":
        from .seed import main as seed
        seed(); return 0

    if args.cmd == "serve":
        import uvicorn
        uvicorn.run("threshold.web:app", host="127.0.0.1", port=args.port, reload=False)
        return 0

    if args.cmd == "eval":
        from .evaluate import main as ev
        return ev("data/aurora-pittsburgh.yaml")

    from . import store
    from .profile import load_profile

    if args.cmd == "score":
        from .score import score
        with store.connect(DB) as conn:
            req = store.load_req(conn, args.slug)
        if req is None:
            print(f"no req '{args.slug}' in {DB} — run: python -m threshold seed"); return 1
        card = score(req, load_profile(args.profile))
        print(f"\n  {req.title}\n  {card.verdict.value.upper()} — {card.summary}\n")
        for f in card.findings:
            kind = "GATE" if f.requirement.is_gate else f.requirement.label.value[:4]
            print(f"  [{kind:>4}] {f.status.value:<9} {f.requirement.text[:74]}")
            print(f"           {f.detail[:88]}")
            if f.citations:
                print(f"           cites: {', '.join(f.citations)}")
        for flag in card.flags:
            print(f"\n  flag: {flag}")
        print()
        return 0

    if args.cmd == "audit":
        from .audit import audit_req
        with store.connect(DB) as conn:
            a = audit_req(conn, args.slug)
        print(f"\n  {a.title}\n  {a.applicants} applicants · {a.rejections} rejections captured\n")
        for g in a.gates:
            share = f"{g.share:>4.0%}" if g.share is not None else "   —"
            print(f"  {g.rejections:>3} {share}  sole={g.sole_reason:<3} {g.text[:64]}")
        print(f"\n  other: {a.other_count}   stronger field: {a.stronger_field_count}"
              f"   unattributed: {a.unattributed}")
        if a.suggestion_accuracy is not None:
            print(f"  pre-check accuracy: {a.suggestion_accuracy:.0%}")
        for n in a.notes:
            print(f"\n  note: {n}")
        print()
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
