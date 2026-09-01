"""The working app: req list, req audit, candidate scorecard, disposition capture.

Server-rendered HTML and plain forms. No client framework, because the whole
product is one dropdown at the right moment and that does not need one.

    uvicorn threshold.web:app --reload
"""

from __future__ import annotations

import os

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from . import store
from .audit import audit_req
from .profile import load_profile
from .score import Status, score
from .ui import esc, page

DB = os.environ.get("THRESHOLD_DB", "threshold.db")
app = FastAPI(title="Threshold")

NAV = '<a href="/">Reqs</a>'


def _pill(kind: str, text: str) -> str:
    return f'<span class="pill p-{esc(kind)}">{esc(text)}</span>'


# ---------------------------------------------------------------- req list
@app.get("/", response_class=HTMLResponse)
def index() -> str:
    with store.connect(DB) as conn:
        rows = store.list_reqs(conn)
        body = ['<h2 class="pt">Open requisitions</h2>'
                '<p class="psub">Requirement counts are parsed; rejection counts are captured.</p>']
        for r in rows:
            gates = conn.execute(
                "SELECT COUNT(*) n FROM requirements WHERE req_slug=? AND label='gate'",
                (r["slug"],)).fetchone()["n"]
            stated = conn.execute(
                "SELECT COUNT(*) n FROM requirements WHERE req_slug=?",
                (r["slug"],)).fetchone()["n"]
            comp = (f'${r["comp_min"]:,}–{r["comp_max"]:,}'
                    if r["comp_min"] and r["comp_max"] else "—")
            body.append(f"""<div class="card"><div class="row">
              <div class="grow"><a href="/req/{esc(r['slug'])}"><b>{esc(r['title'])}</b></a>
              <div class="muted">{esc(r['company'] or '')} · {esc(r['location'] or '')}</div></div>
              <span class="num muted">{stated} stated · <b>{gates} gates</b></span>
              <span class="num muted">{r['applicants']} applicants · {r['rejected']} rejected</span>
              <span class="num muted">{comp}</span></div></div>""")
    return page("Reqs", "".join(body), NAV)


# --------------------------------------------------------------- req audit
@app.get("/req/{slug}", response_class=HTMLResponse)
def req_view(slug: str) -> HTMLResponse:
    with store.connect(DB) as conn:
        req = store.load_req(conn, slug)
        if req is None:
            return HTMLResponse(page("Not found", "<p>No such req.</p>", NAV), status_code=404)
        a = audit_req(conn, slug)
        apps = conn.execute("""
            SELECT a.id, c.id AS cid, c.name, a.stage FROM applications a
            JOIN candidates c ON c.id=a.candidate_id WHERE a.req_slug=? ORDER BY c.name""",
            (slug,)).fetchall()

    b = [f'<h2 class="pt">{esc(req.title)}</h2>',
         f'<p class="psub">{esc(req.company)} · {esc(req.location)} · '
         f'{req.stated_count} stated requirements, {len(req.gates)} of them gates</p>']

    for n in a.notes:
        b.append(f'<div class="note">{esc(n)}</div>')

    b.append('<h3 class="sec">What each gate costs</h3>')
    if not a.rejections:
        b.append('<div class="card muted">No dispositions captured yet. '
                 'Reject a candidate below and this fills in.</div>')
    for g in a.gates:
        share = f'{g.share:.0%}' if g.share is not None else '—'
        width = int((g.share or 0) * 100)
        hot = " hot" if (g.share or 0) >= 0.4 else ""
        sole = (f'<span class="s-missing st">{g.sole_reason} rejected on this alone</span>'
                if g.sole_reason else '<span class="muted">never the only reason</span>')
        b.append(f"""<div class="card"><div class="row">
          <div class="grow">{esc(g.text)}</div>
          <span class="num"><b>{g.rejections}</b> rejections</span>
          <span class="num">{share} of all</span></div>
          <div class="bar"><i class="{hot}" style="width:{width}%"></i></div>
          <div class="muted" style="margin-top:7px">{sole}</div></div>""")

    b.append('<h3 class="sec">Where the rejections went</h3><div class="card"><table>'
             '<tr><th>Bucket</th><th>Count</th><th>What it means</th></tr>'
             f'<tr><td>Attributed to a gate</td><td class="num">'
             f'{sum(g.rejections for g in a.gates)}</td>'
             '<td>usable — this is what the audit is built from</td></tr>'
             f'<tr><td>Cleared everything, weaker field</td><td class="num">'
             f'{a.stronger_field_count}</td>'
             '<td>not a gate failure; excluded from pool cost</td></tr>'
             f'<tr><td>Other — not the stated requirements</td><td class="num">{a.other_count}</td>'
             '<td>the posting is not describing the real decision</td></tr>'
             f'<tr><td>No reason recorded</td><td class="num">{a.unattributed}</td>'
             '<td>capture gap</td></tr></table></div>')

    acc = a.suggestion_accuracy
    if acc is not None:
        b.append(f'<div class="card muted">Pre-check accuracy: <b class="num">{acc:.0%}</b> — '
                 'how often the scorer&rsquo;s suggestion matched what the recruiter chose. '
                 'If this falls, the suggestions are training people to click through.</div>')

    if a.reroute:
        b.append('<h3 class="sec">Right person, wrong req</h3><div class="card"><table>'
                 '<tr><th>Candidate</th><th>Clears every gate on</th></tr>')
        for name, other, title in a.reroute:
            b.append(f'<tr><td>{esc(name)}</td><td><a href="/req/{esc(other)}">'
                     f'{esc(title)}</a></td></tr>')
        b.append('</table></div>')

    b.append('<h3 class="sec">Pipeline</h3>')
    for row in apps:
        b.append(f"""<div class="card"><div class="row">
          <div class="grow"><b>{esc(row['name'])}</b>
          <span class="muted"> · {esc(row['stage'])}</span></div>
          <a href="/req/{esc(slug)}/candidate/{esc(row['cid'])}">review</a></div></div>""")
    return HTMLResponse(page(req.title, "".join(b), NAV))


# ------------------------------------------------- scorecard + capture form
@app.get("/req/{slug}/candidate/{cid}", response_class=HTMLResponse)
def candidate_view(slug: str, cid: str) -> HTMLResponse:
    with store.connect(DB) as conn:
        req = store.load_req(conn, slug)
        cand = conn.execute("SELECT * FROM candidates WHERE id=?", (cid,)).fetchone()
        if req is None or cand is None:
            return HTMLResponse(page("Not found", "<p>Not found.</p>", NAV), status_code=404)
        prof = load_profile(cand["profile_path"]) if cand["profile_path"] else None
        prior = conn.execute("""
            SELECT d.* FROM dispositions d JOIN applications a ON a.id=d.application_id
            WHERE a.req_slug=? AND a.candidate_id=? ORDER BY d.id DESC LIMIT 1""",
            (slug, cid)).fetchone()

    card = score(req, prof) if prof else None
    b = [f'<h2 class="pt">{esc(cand["name"])}</h2>',
         f'<p class="psub"><a href="/req/{esc(slug)}">{esc(req.title)}</a> · '
         f'{esc(cand["note"] or "")}</p>']

    if card is None:
        b.append('<div class="note">No profile on file — the scorer has nothing to cite, '
                 'so no suggestions are offered.</div>')
        suggested = []
    else:
        b.append(f'<div class="card"><div class="row">'
                 f'{_pill(card.verdict.value, card.verdict.value.replace("_"," "))}'
                 f'<span class="num">{esc(card.summary)}</span></div></div>')
        b.append('<h3 class="sec">Requirement ledger</h3><div class="card">')
        for f in card.findings:
            cites = (f'<cite>{esc(", ".join(f.citations))}</cite>' if f.citations
                     else '<cite>no evidence cited</cite>')
            b.append(f"""<div class="f"><span>{_pill(f.requirement.label.value,
              'gate' if f.requirement.is_gate else f.requirement.label.value[:4])}</span>
              <div><p class="txt">{esc(f.requirement.text)}</p>
              <span class="st s-{f.status.value}">{f.status.value}</span>
              <p class="ev">{esc(f.detail)}{cites}</p></div></div>""")
        b.append('</div>')
        suggested = [f.requirement.ordinal for f in card.gate_findings
                     if f.status in (Status.MISSING, Status.ARGUABLE, Status.UNKNOWN)]

    if prior:
        b.append(f'<div class="note">Already dispositioned: <b>{esc(prior["outcome"])}</b>. '
                 'Recording again replaces nothing — it appends, and both are kept.</div>')

    b.append('<h3 class="sec">Disposition</h3>'
             f'<form method="post" action="/req/{esc(slug)}/candidate/{esc(cid)}/reject">'
             '<div class="card"><p class="muted" style="margin-top:0">'
             'Which requirement did they miss? Pre-checked from the ledger — confirm or correct. '
             'More than one is allowed.</p>')
    for f in (card.gate_findings if card else []):
        pre = f.requirement.ordinal in suggested
        hint = esc(f.detail[:90])
        b.append(f"""<label class="opt{' pre' if pre else ''}">
          <input type="checkbox" name="ordinals" value="{f.requirement.ordinal}"
          {'checked' if pre else ''}>
          <span class="t">{esc(f.requirement.text)}<small>{hint}</small></span></label>""")
    b.append("""
      <label class="opt"><input type="checkbox" name="kind_stronger" value="1">
        <span class="t">Cleared everything — stronger candidates available
        <small>not a gate failure; excluded from pool cost</small></span></label>
      <label class="opt"><input type="checkbox" name="kind_other" value="1">
        <span class="t">Other — not about the stated requirements
        <small>if this is common on a req, the posting is wrong</small></span></label>
      <p style="margin:12px 0 6px" class="lbl">Note (optional)</p>
      <input type="text" name="note" placeholder="what actually decided it">
      <div style="margin-top:14px;display:flex;gap:9px;align-items:center">
        <button class="go" type="submit">Record rejection</button>
        <span class="muted">writes back to the ATS rejection field</span>
      </div></div></form>""")

    if card:
        b.append(f'<form method="post" action="/req/{esc(slug)}/candidate/{esc(cid)}/advance">'
                 '<button class="go" type="submit" style="background:var(--pass)">Advance</button>'
                 '</form>')
    return HTMLResponse(page(cand["name"], "".join(b), NAV))


@app.post("/req/{slug}/candidate/{cid}/reject")
async def reject(slug: str, cid: str, request: Request, note: str = Form("")):
    form = await request.form()
    ordinals = [int(v) for v in form.getlist("ordinals")]
    kind = "gate"
    if form.get("kind_other"):
        kind = "other"
    elif form.get("kind_stronger"):
        kind = "stronger_field"
    with store.connect(DB) as conn:
        req = store.load_req(conn, slug)
        cand = conn.execute("SELECT * FROM candidates WHERE id=?", (cid,)).fetchone()
        suggested: list[int] = []
        if cand and cand["profile_path"]:
            card = score(req, load_profile(cand["profile_path"]))
            suggested = [f.requirement.ordinal for f in card.gate_findings
                         if f.status in (Status.MISSING, Status.ARGUABLE, Status.UNKNOWN)]
        app_id = store.apply_to(conn, slug, cid)
        store.record_disposition(conn, app_id, "rejected", ordinals, kind, note,
                                 suggested_ordinals=suggested)
    return RedirectResponse(f"/req/{slug}", status_code=303)


@app.post("/req/{slug}/candidate/{cid}/advance")
def advance(slug: str, cid: str):
    with store.connect(DB) as conn:
        app_id = store.apply_to(conn, slug, cid)
        store.record_disposition(conn, app_id, "advanced", [], "gate", "")
    return RedirectResponse(f"/req/{slug}", status_code=303)
