#!/usr/bin/env python3
"""query.py - Cited keyword search over a hq4termux FTS5 index.

Built on the same schema as build_index.py (segments + seg_fts). Returns
ranked hits with the citation URL and a short snippet, JSON or plain text.
Stdlib only - Termux-safe.

Usage:
  python3 query.py <corpus-dir-or-db> <query> [limit]
  e.g.  python3 query.py corpus "how to raise price" 5

Fuzzy fallback: if the raw query has zero FTS5 matches, retry with the
individual significant terms OR-joined (same spirit as the original
ask-hormozi "3 focused retries" rule).
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DB = REPO / "corpus" / "hq4.db"

STOP = {
    "a", "an", "the", "and", "or", "but", "of", "in", "on", "at", "to", "for",
    "with", "is", "are", "was", "were", "be", "been", "you", "your", "what",
    "how", "why", "when", "where", "which", "who", "do", "does", "did", "i",
    "we", "it", "this", "that", "than", "then", "so", "if", "as", "my", "our",
}


def sanitize(term: str) -> str:
    """Quote an FTS5 term so user input can't inject query syntax."""
    return '"' + term.replace('"', '""') + '"'


def terms(query: str) -> list[str]:
    toks = [t for t in re.findall(r"[a-z0-9$]+", query.lower()) if t not in STOP]
    return toks or re.findall(r"[a-z0-9$]+", query.lower())


def open_db(path: Path) -> sqlite3.Connection:
    p = path
    if p.is_dir():
        p = p / "hq4.db"
    if not p.exists():
        p = DEFAULT_DB
    if not p.exists():
        print(f"ERROR: no index at {p}. Run: python3 scripts/build_index.py {path}",
              file=sys.stderr)
        sys.exit(1)
    return sqlite3.connect(p)


def search(conn: sqlite3.Connection, query: str, limit: int) -> list[dict]:
    sql = (
        "SELECT s.video_id, s.title, s.ts_url, s.start_seconds, s.body, "
        "snippet(seg_fts, 0, '[', ']', '...', 24) AS snip "
        "FROM seg_fts f JOIN segments s ON s.id = f.rowid "
        "WHERE seg_fts MATCH ? ORDER BY rank LIMIT ?"
    )
    expr = " AND ".join(sanitize(t) for t in terms(query))
    rows = conn.execute(sql, (expr, limit)).fetchall()
    if not rows:
        # Fuzzy fallback: OR of the significant terms.
        ft = terms(query)
        if ft:
            expr = " OR ".join(sanitize(t) for t in ft)
            rows = conn.execute(sql, (expr, limit)).fetchall()
    out = []
    for vid, title, ts_url, start, body, snip in rows:
        # Only wrap a URL in a YouTube link if it actually is YouTube; a local
        # file path (write path) must not be invented into watch?v=...
        url = (ts_url or "").strip()
        if url.startswith(("https://www.youtube.com/watch", "https://youtu.be")):
            cite = f"[{title}](https://www.youtube.com/watch?v={vid}&t={start}s)"
        elif url:
            cite = f"[{title}]({url})"
        else:
            cite = title
        out.append({
            "video_id": vid,
            "title": title,
            "citation": cite,
            "url": url,
            "start_seconds": start,
            "snippet": (snip or body).strip()[:200],
        })
    return out


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    db_path = Path(sys.argv[1])
    query = sys.argv[2]
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    conn = open_db(db_path)
    hits = search(conn, query, limit)
    if len(sys.argv) > 4 and sys.argv[4].lower() == "--json":
        print(json.dumps(hits, indent=2))
    else:
        if not hits:
            print(f"corpus is silent on {query!r} - no matches; say so, do not invent.")
        for h in hits:
            print(f"- {h['citation']}")
            print(f"    {h['snippet']}")
            print()


if __name__ == "__main__":
    main()
