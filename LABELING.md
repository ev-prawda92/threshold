# Labeling guide

Three classes. The whole product rests on getting these apart, because only one
of them can disqualify you.

### `gate`
A requirement that is **objectively checkable** and that a recruiter or an ATS
screens on. Missing one ends the application regardless of everything else.

Signals: a quantified span of experience ("7+ years"), a named credential
(degree, certification, licence), a named technology or methodology (Python,
SQL, NetSuite, ISO 26262, Agile), a logistical constraint (office days, travel,
work authorization), or a named domain of experience ("within transportation or
an adjacent safety-critical industry").

### `soft_required`
Printed under *Required Qualifications* but **not screenable**. Character and
competence claims that every applicant asserts and no recruiter verifies:
"excellent communication skills", "self-starter", "passionate about working
with teams", "strong analytical skills".

These matter in an interview and are nearly worthless as filters. Counting them
as gates is the single biggest source of false "you're not qualified" verdicts —
it is why generic matchers tell strong candidates they score 60%.

### `preference`
Under *Desirable* / *Preferred*, **or** hedged inside a required bullet: "is a
plus", "ideally", "beneficial", "nice to have". Missing these costs you nothing
on the screen.

---

## The rule that matters most

**Section heading is a signal, not the answer.** Two failure modes, both present
in this dataset:

- A *hard* gate printed in the required section that reads soft — Aurora's Staff
  Safety Research Scientist lists "A portfolio of publications and/or conference
  presentations" under Required Qualifications. Checkable, and disqualifying.
- A *preference* printed in the required section — the same company's Senior
  Staff PPM lists a degree bullet that ends "...or the equivalent in experience
  with evidence of exceptional ability preferred."

A classifier that trusts the heading gets both wrong, and they point in opposite
directions.

## Scope is part of the label

Record the requirement's full scope, not its keyword. "7 years as a TPM, PM, or
EM in autonomous systems, robotics, embedded systems, **or software development**"
is a far wider gate than "7 years in autonomous systems" — the trailing
alternative is what decides whether a candidate clears it. Summaries destroy this
distinction routinely, which is why the parser works on verbatim text only.
