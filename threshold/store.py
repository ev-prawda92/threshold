"""SQLite store. Small on purpose.

The schema exists to make one field possible that no applicant tracking system
has: which requirement a rejection was attributed to. Everything the audit can
say is downstream of the `dispositions` table.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS reqs (
  slug TEXT PRIMARY KEY, title TEXT NOT NULL, company TEXT, location TEXT,
  comp_min INTEGER, comp_max INTEGER, opened_at TEXT, raw TEXT
);
CREATE TABLE IF NOT EXISTS requirements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  req_slug TEXT NOT NULL REFERENCES reqs(slug),
  ordinal INTEGER NOT NULL, section TEXT NOT NULL, text TEXT NOT NULL,
  label TEXT NOT NULL, confidence REAL, signals TEXT,
  UNIQUE (req_slug, ordinal)
);
CREATE TABLE IF NOT EXISTS candidates (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, profile_path TEXT, note TEXT
);
CREATE TABLE IF NOT EXISTS applications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  req_slug TEXT NOT NULL REFERENCES reqs(slug),
  candidate_id TEXT NOT NULL REFERENCES candidates(id),
  stage TEXT NOT NULL DEFAULT 'screen', applied_at TEXT,
  UNIQUE (req_slug, candidate_id)
);
-- The whole point. One row per rejection, attributed to specific requirements.
CREATE TABLE IF NOT EXISTS dispositions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  application_id INTEGER NOT NULL REFERENCES applications(id),
  outcome TEXT NOT NULL,                    -- rejected | advanced | withdrawn
  -- requirement ordinals this rejection was attributed to; [] is meaningful
  reason_ordinals TEXT NOT NULL DEFAULT '[]',
  reason_kind TEXT NOT NULL DEFAULT 'gate', -- gate | stronger_field | other
  note TEXT, decided_by TEXT, decided_at TEXT NOT NULL,
  -- what the scorer had predicted, so drift between the two is measurable
  suggested_ordinals TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS ix_disp_app ON dispositions(application_id);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect(path: str | Path = "threshold.db"):
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init(path: str | Path = "threshold.db") -> None:
    with connect(path) as c:
        c.executescript(SCHEMA)


def save_req(conn, req, opened_at: str | None = None, raw: str = "") -> None:
    conn.execute(
        "INSERT OR REPLACE INTO reqs (slug,title,company,location,comp_min,comp_max,opened_at,raw)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (req.slug, req.title, req.company, req.location, req.comp_min, req.comp_max,
         opened_at or now(), raw))
    conn.execute("DELETE FROM requirements WHERE req_slug = ?", (req.slug,))
    conn.executemany(
        "INSERT INTO requirements (req_slug,ordinal,section,text,label,confidence,signals)"
        " VALUES (?,?,?,?,?,?,?)",
        [(req.slug, r.ordinal, r.section, r.text, r.label.value, r.confidence,
          json.dumps(list(r.signals))) for r in req.requirements])


def add_candidate(conn, cid: str, name: str, profile_path: str = "", note: str = "") -> None:
    conn.execute("INSERT OR REPLACE INTO candidates (id,name,profile_path,note) VALUES (?,?,?,?)",
                 (cid, name, profile_path, note))


def apply_to(conn, req_slug: str, candidate_id: str, applied_at: str | None = None) -> int:
    cur = conn.execute(
        "INSERT OR IGNORE INTO applications (req_slug,candidate_id,applied_at) VALUES (?,?,?)",
        (req_slug, candidate_id, applied_at or now()))
    if cur.lastrowid:
        return cur.lastrowid
    row = conn.execute(
        "SELECT id FROM applications WHERE req_slug=? AND candidate_id=?",
        (req_slug, candidate_id)).fetchone()
    return row["id"]


def record_disposition(conn, application_id: int, outcome: str,
                       reason_ordinals: list[int] | None = None,
                       reason_kind: str = "gate", note: str = "",
                       decided_by: str = "recruiter",
                       suggested_ordinals: list[int] | None = None) -> int:
    cur = conn.execute(
        "INSERT INTO dispositions (application_id,outcome,reason_ordinals,reason_kind,note,"
        "decided_by,decided_at,suggested_ordinals) VALUES (?,?,?,?,?,?,?,?)",
        (application_id, outcome, json.dumps(sorted(reason_ordinals or [])), reason_kind,
         note, decided_by, now(), json.dumps(sorted(suggested_ordinals or []))))
    conn.execute("UPDATE applications SET stage=? WHERE id=?",
                 ("rejected" if outcome == "rejected" else "advanced", application_id))
    return cur.lastrowid


def load_req(conn, slug: str):
    from .classify import Label
    from .parse import Req, Requirement
    r = conn.execute("SELECT * FROM reqs WHERE slug=?", (slug,)).fetchone()
    if r is None:
        return None
    req = Req(slug=r["slug"], title=r["title"], company=r["company"] or "",
              location=r["location"] or "", comp_min=r["comp_min"], comp_max=r["comp_max"])
    for row in conn.execute(
            "SELECT * FROM requirements WHERE req_slug=? ORDER BY ordinal", (slug,)):
        req.requirements.append(Requirement(
            ordinal=row["ordinal"], section=row["section"], text=row["text"],
            label=Label(row["label"]), confidence=row["confidence"] or 1.0,
            signals=tuple(json.loads(row["signals"] or "[]"))))
    return req


def list_reqs(conn) -> list[sqlite3.Row]:
    return conn.execute("""
        SELECT r.*,
          (SELECT COUNT(*) FROM applications a WHERE a.req_slug=r.slug) AS applicants,
          (SELECT COUNT(*) FROM applications a JOIN dispositions d ON d.application_id=a.id
             WHERE a.req_slug=r.slug AND d.outcome='rejected') AS rejected
        FROM reqs r ORDER BY r.title""").fetchall()


def dispositions_for(conn, slug: str) -> list[dict]:
    rows = conn.execute("""
        SELECT d.*, a.candidate_id, c.name AS candidate_name
        FROM dispositions d
        JOIN applications a ON a.id = d.application_id
        JOIN candidates c ON c.id = a.candidate_id
        WHERE a.req_slug = ? ORDER BY d.id""", (slug,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["reason_ordinals"] = json.loads(r["reason_ordinals"])
        d["suggested_ordinals"] = json.loads(r["suggested_ordinals"])
        out.append(d)
    return out
