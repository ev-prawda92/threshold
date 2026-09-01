# Threshold

A job-application scorer that reads a careers page, breaks every posting into
atomic requirements, sorts each one into **hard gate** or **soft preference**,
and refuses to score anything it cannot cite back to evidence.

Most matchers embed a résumé, embed a posting, and return a similarity score.
That is the wrong shape. Similarity does not tell you the one thing that decides
an application: *is there a requirement here that ends this regardless of
everything else?*

## The thesis, in one example

Two Aurora postings in Pittsburgh score almost identically on keyword overlap
with the same candidate. One is unreachable and one is the strongest option on
the board, and the only thing separating them is whether the decisive
requirement is a gate or a preference:

| | Applied Researcher | Senior Staff Product & Program Manager |
|---|---|---|
| Decisive requirement | "PhD Graduate in AI, Computer Science, or Robotics (top-tier research lab)" | "Minimum 7 years as a TPM, PM, or EM in autonomous systems, robotics, embedded systems, **or software development**" |
| Type | gate, unarguable | gate, and the trailing alternative clears it |
| Verdict | blocked | apply |

A similarity model sees "AI research" in both and ranks the first one higher.

## It runs

```
pip install -r requirements.txt
python -m threshold seed        # build the demo database
python -m threshold serve       # the app on http://127.0.0.1:8000
```

Three other commands, all reading the same database:

```
python -m threshold score senior-staff-product-and-program-manager
python -m threshold audit senior-staff-product-and-program-manager
python -m threshold eval        # classifier accuracy on the labelled set
```

`serve` gives you the loop end to end: a list of reqs, a candidate scorecard with
every finding cited, a rejection form whose options are that req's own gates
pre-checked from the scorecard, and a req audit that recomputes from what was
captured. Reject someone and watch the audit change.

## What's in the repo

```
profile.yaml              evidence corpus — the asset (gitignored)
profile.example.yaml      committed stand-in
data/aurora-pittsburgh.yaml   85 hand-labeled requirements, 8 postings
LABELING.md               the three-class taxonomy and how to apply it

threshold/parse.py        posting text -> classified requirement ledger
threshold/classify.py     transparent baseline classifier
threshold/evaluate.py     classifier evaluation harness
threshold/profile.py      evidence corpus loader, with span merging
threshold/score.py        requirement x evidence -> cited findings and a verdict
threshold/store.py        SQLite: reqs, requirements, candidates, dispositions
threshold/audit.py        what each gate costs, computed from captured reasons
threshold/web.py          the app — server-rendered, no client framework
threshold/seed.py         demo database
tests/                    15 tests
```

## The capture field

Everything the audit can say is downstream of one column no applicant tracking
system has: **which requirement a rejection was attributed to**. Rejection
reasons in every ATS are a company-wide dropdown — *not qualified, stronger
candidates* — so the funnel knows 214 became 6 and cannot say which of the
eleven bullets did the cutting.

Because the ledger already exists, the form shows that req's four gates instead
of a generic list, pre-checked from the candidate's scorecard. The recruiter is
confirming a guess, not answering a question, which is less work than what they
do today rather than more.

Three options are load-bearing:

- **A gate** — the usable case, and the only one that feeds pool cost.
- **Cleared everything, stronger field** — a real outcome that is *not* a gate
  failure. Collapsing it into one would read a strong field as a throttling
  requirement.
- **Other, not about the stated requirements** — prevents force-fitting. A req
  where this dominates has told you the posting does not describe how the team
  is deciding, which is the most valuable finding in the system.

The scorer's suggestion is stored alongside what was chosen, so
`suggestion_accuracy` measures whether pre-checking is helping or training
people to click through a wrong default.

## Baseline

```
pip install -r requirements.txt
python -m threshold.evaluate data/aurora-pittsburgh.yaml
```

```
three-class accuracy   79/85  92.9%

gold \ pred                    gate   soft_required      preference
gate                            29               4               0
soft_required                    0              20               1
preference                       1               0              30

gate             precision 96.7%   recall 87.9%   F1 92.1%
soft_required    precision 83.3%   recall 95.2%   F1 88.9%
preference       precision 96.8%   recall 96.8%   F1 96.8%

binary gate / not-gate  94.1%   (1 false gate, 4 missed gates)
```

**Read that number with suspicion.** The same person wrote the labels and the
regexes, on a single company's postings, and 85 examples is a small set. Treat
92.9% as an optimistic ceiling for this approach, not a measurement of how it
will behave on Workday postings from a bank. The point of publishing it is that
any future classifier — an LLM, a fine-tune, a second annotator — now has
something specific to beat and a failure list to beat it on.

## Where it fails, and why that's the interesting part

Four of the six errors are the same error: a genuine gate written in ordinary
English with no quantifier, no credential, and no named technology.

- "Experience developing hardware through defined Product Development Process of Stage Gates."
- "Proven experience conducting user research methodologies, such as direct user shadowing, focus groups, or user acceptance testing."
- "Thorough understanding of product development life cycles that incorporate safety"
- "Demonstrated expertise in creating, executing, and optimizing workflows while identifying bottlenecks"

Every one is checkable, and every one would end an application. The regexes miss
them because the signal is *domain knowledge*, not vocabulary — exactly the gap
where a language model earns its cost. That is the next experiment, and now it
has a scoreboard.

The remaining two errors are the opposite problem, and they are the reason the
taxonomy has three classes instead of two: a preference hiding under a
*Required* heading, and a soft claim with a hedge stapled to the end.

**The tempting fix, declined.** Every one of those four misses fires the
`no-signal` path. Flipping that default from `soft_required` to `gate` takes
three-class accuracy to 97.6% in one line. It is also pure overfitting to 85
examples from one company, and it would invent gates everywhere on the next
dataset. The default stays where it is until there is a second company's data to
justify moving it.

## Design rules

1. **Verbatim text only.** Summaries destroy scope, and scope decides outcomes.
   A recruiter's summary of the PPM role read "in autonomous systems or embedded
   software" and dropped "or software development" — the clause that makes the
   role reachable.
2. **Cite or report absent.** A claim with no source in the corpus is not a
   partial match, it is a hole, and the report says so. `profile.yaml` declares
   an explicit `absent` list so a missing skill produces a real finding rather
   than an empty search.
3. **Arguable is a verdict.** Some gates can be argued but not claimed. Those
   are named, and the argument is the thing the cover letter has to carry — and
   the thing outcome tracking should later confirm or kill.
4. **Level is separate from fit.** A Level I role that clears every gate should
   not out-rank a Staff role that misses one. `current_scope` and
   `target_band_floor_usd` exist to catch that.

## Not built yet

- ATS ingestion. Greenhouse, Ashby and Lever adapters cover most of the market;
  Playwright for the rest. Aurora's own page needs a headless browser and a
  load-more loop just to enumerate roles.
- Adverse impact per gate. The schema supports it — attribution plus demographic
  data is all it takes — but demographic data belongs to the employer and should
  never live in this database. It reads, computes, and does not retain.
- Auth, multi-tenancy, and anything resembling security. This is a local tool.
- The comp store. Posted ranges are primary-source market data, and nobody keeps
  a time series of them. Three Aurora postings listing two zones are enough to
  recover their entire policy: a flat 0.90 Pittsburgh multiplier on a national
  band, 1.60× wide.
- Outcome tracking and calibration. With one user this is bookkeeping and base
  rates, not machine learning, and it should be described that way.

## Honest limits of the running system

- **The scorer is deterministic and narrow.** Term matching plus a few typed
  rules — years, credentials, place, travel. It says `unknown` a lot, which is
  the intended failure mode: an unmatched requirement is a hole to ask about,
  not a partial score. A model may later *propose* matches, but it proposes into
  this structure and a person confirms.
- **The demo dispositions are scripted.** Requirement text is verbatim from live
  postings and the profile is real; the twelve other candidates are invented, and
  their files say so.
- **Rates are withheld below eight rejections.** A percentage over four
  dispositions is not a finding, and the audit prints counts and a note instead.

## Known blind spot

Referrals outperform fit. Threshold does not model who you know, and no honest
version of it can.
