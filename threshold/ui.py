"""Shared page shell. One stylesheet, tokenised, light and dark."""

from __future__ import annotations

CSS = """
:root{--paper:#f4f6f8;--card:#fff;--sunk:#eaeef2;--ink:#12181f;--ink2:#3d4a58;--ink3:#6b7b8c;
--rule:#d6dde4;--rule2:#e7ecf1;--navy:#1f3a63;--navys:#e4eaf4;--pass:#1c6b52;--passs:#dcece5;
--fail:#a83c22;--fails:#f6e2dc;--warn:#8a6410;--warns:#f6ecd6;
--mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;
--sans:"IBM Plex Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
--serif:"Newsreader",Georgia,serif}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]){--paper:#0d1116;--card:#151b22;
--sunk:#101620;--ink:#e8eef4;--ink2:#a8b6c4;--ink3:#74838f;--rule:#26313c;--rule2:#1d262f;
--navy:#93b4e6;--navys:#1a2739;--pass:#6fc4a3;--passs:#142a24;--fail:#e08163;--fails:#2e1a15;
--warn:#d6ab55;--warns:#2a2213}}
:root[data-theme=dark]{--paper:#0d1116;--card:#151b22;--sunk:#101620;--ink:#e8eef4;--ink2:#a8b6c4;
--ink3:#74838f;--rule:#26313c;--rule2:#1d262f;--navy:#93b4e6;--navys:#1a2739;--pass:#6fc4a3;
--passs:#142a24;--fail:#e08163;--fails:#2e1a15;--warn:#d6ab55;--warns:#2a2213}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);font-size:14px;
line-height:1.5;-webkit-font-smoothing:antialiased}
a{color:var(--navy)}
.lbl{font-family:var(--mono);font-size:10px;letter-spacing:.13em;text-transform:uppercase;color:var(--ink3)}
.num{font-family:var(--mono);font-variant-numeric:tabular-nums}
:focus-visible{outline:2px solid var(--navy);outline-offset:2px;border-radius:3px}
header{background:var(--card);border-bottom:1px solid var(--rule)}
header .in{max-width:980px;margin:0 auto;padding:13px 22px;display:flex;gap:14px;align-items:baseline;flex-wrap:wrap}
header h1{font-family:var(--serif);font-size:21px;margin:0;font-weight:600}
header h1 a{text-decoration:none;color:inherit}
header .sub{font-family:var(--mono);font-size:9.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--ink3)}
header nav{margin-left:auto;display:flex;gap:14px;font-size:12.5px}
main{max-width:980px;margin:0 auto;padding:22px 22px 60px}
h2.pt{font-family:var(--serif);font-size:25px;font-weight:600;margin:0 0 4px;letter-spacing:-.015em}
p.psub{margin:0 0 18px;color:var(--ink3);font-size:13px}
h3.sec{font-family:var(--mono);font-size:10px;letter-spacing:.13em;text-transform:uppercase;
color:var(--ink3);font-weight:500;margin:26px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--rule)}
.card{background:var(--card);border:1px solid var(--rule);border-radius:5px;padding:15px;margin-bottom:9px}
.row{display:flex;gap:12px;align-items:baseline;flex-wrap:wrap}
.row .grow{flex:1;min-width:200px}
.pill{font-family:var(--mono);font-size:9.5px;letter-spacing:.1em;text-transform:uppercase;
padding:2px 7px;border-radius:2px;white-space:nowrap}
.p-apply{background:var(--passs);color:var(--pass)}
.p-arguable{background:var(--warns);color:var(--warn)}
.p-open_question{background:var(--navys);color:var(--navy)}
.p-blocked{background:var(--fails);color:var(--fail)}
.p-gate{background:var(--navys);color:var(--navy);font-weight:600}
.p-preference,.p-soft_required{background:var(--sunk);color:var(--ink3)}
.st{font-family:var(--mono);font-size:10px;letter-spacing:.06em;text-transform:uppercase;font-weight:500}
.s-met{color:var(--pass)}.s-arguable{color:var(--warn)}.s-missing{color:var(--fail)}.s-unknown{color:var(--navy)}
.f{display:grid;grid-template-columns:56px 1fr;gap:10px;padding:10px 0;border-top:1px solid var(--rule2)}
.f:first-child{border-top:0;padding-top:0}
.f .txt{font-size:13px;line-height:1.4;margin:0 0 3px}
.ev{font-size:11.5px;color:var(--ink2);line-height:1.45;margin:3px 0 0;padding-left:9px;
border-left:2px solid var(--rule)}
.ev cite{font-style:normal;font-family:var(--mono);font-size:10px;color:var(--ink3);display:block;margin-top:2px}
.bar{height:6px;background:var(--sunk);border-radius:3px;overflow:hidden;margin-top:5px}
.bar i{display:block;height:100%;background:var(--navy)}
.bar i.hot{background:var(--fail)}
.opt{display:flex;gap:10px;align-items:flex-start;padding:9px 10px;border:1px solid var(--rule);
border-radius:4px;margin-bottom:6px;cursor:pointer}
.opt:hover{border-color:color-mix(in srgb,var(--navy) 40%,var(--rule))}
.opt input{margin:2px 0 0;accent-color:var(--navy);width:15px;height:15px;flex:none}
.opt.pre{background:var(--fails);border-color:color-mix(in srgb,var(--fail) 38%,transparent)}
.opt .t{font-size:12.5px;line-height:1.4}
.opt .t small{display:block;font-family:var(--mono);font-size:10px;color:var(--ink3);margin-top:2px}
button.go{font:inherit;font-size:13px;font-weight:500;background:var(--navy);color:var(--card);
border:0;border-radius:4px;padding:8px 18px;cursor:pointer}
input[type=text],textarea{font:inherit;font-size:12.5px;width:100%;padding:7px 9px;border:1px solid var(--rule);
border-radius:4px;background:var(--sunk);color:var(--ink)}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th{text-align:left;font-family:var(--mono);font-size:9.5px;letter-spacing:.09em;text-transform:uppercase;
color:var(--ink3);font-weight:500;padding:0 10px 7px 0;border-bottom:1px solid var(--rule)}
td{padding:8px 10px 8px 0;border-bottom:1px solid var(--rule2);color:var(--ink2);vertical-align:top}
td:first-child{color:var(--ink)}
.note{background:var(--warns);border:1px solid color-mix(in srgb,var(--warn) 30%,transparent);
border-radius:4px;padding:11px 13px;font-size:12.5px;margin-bottom:10px;color:var(--ink)}
.muted{color:var(--ink3);font-size:12px}
footer{max-width:980px;margin:0 auto;padding:16px 22px 40px;color:var(--ink3);font-size:11.5px;
border-top:1px solid var(--rule)}
"""

FONTS = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
         'family=Newsreader:opsz,wght@6..72,400;6..72,600&'
         'family=IBM+Plex+Mono:wght@400;500;600&'
         'family=IBM+Plex+Sans:wght@400;450;500;600&display=swap">')


def esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def page(title: str, body: str, nav: str = "") -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · Threshold</title>{FONTS}<style>{CSS}</style></head><body>
<header><div class="in"><h1><a href="/">Threshold</a></h1><span class="sub">gate ledger</span>
<nav>{nav}</nav></div></header>
<main>{body}</main>
<footer>Local instance · every figure is computed from captured dispositions in this database.
Nothing is inferred that is not cited.</footer>
</body></html>"""
