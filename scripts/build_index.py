#!/usr/bin/env python3
"""build_index.py - Build a SQLite FTS5 index over a hq4termux corpus.

A corpus is a directory of segment files: <corpus>/segments/<video_id>/<start>.md
Each segment carries YAML frontmatter (title, episode_url, timestamp_url,
start_seconds, ...) followed by the body text. The index is plain stdlib
(sqlite3 FTS5) - no qmd, no ONNX, no binary. Termux-safe.

Usage:
  python3 build_index.py [corpus-dir] [db-path]
  defaults: corpus-dir = <repo>/corpus, db-path = <repo>/corpus/hq4.db
"""
import re
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS = REPO / "corpus"


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Split a segment .md into (frontmatter dict, body). Tolerant: no
    frontmatter means the whole file is body."""
    if not text.startswith("---"):
        return {}, text
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.DOTALL)
    if not m:
        return {}, text
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip().strip('"')
    return fm, m.group(2)


def build(corpus_dir: Path, db_path: Path) -> int:
    seg_dir = corpus_dir / "segments"
    files = sorted(seg_dir.glob("*/*.md"))
    if not files:
        print(f"ERROR: no segments found under {seg_dir}", file=sys.stderr)
        return 1
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS segments ("
        "id INTEGER PRIMARY KEY, video_id TEXT, title TEXT, ts_url TEXT, "
        "start_seconds TEXT, transcript_source TEXT, body TEXT)"
    )
    conn.execute("DELETE FROM segments")
    for i, f in enumerate(files):
        fm, body = parse_frontmatter(f.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO segments (id, video_id, title, ts_url, "
            "start_seconds, transcript_source, body) VALUES (?,?,?,?,?,?,?)",
            (i, f.parent.name,
             fm.get("title", ""),
             fm.get("timestamp_url", fm.get("episode_url", "")),
             fm.get("start_seconds", ""),
             fm.get("transcript_source", ""),
             body.strip()),
        )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_video ON segments(video_id)")
    conn.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS seg_fts USING fts5("
        "body, title, content='segments', content_rowid='id')"
    )
    conn.execute("INSERT INTO seg_fts(seg_fts) VALUES('rebuild')")
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM segments").fetchone()[0]
    conn.close()
    print(f"indexed {n} segments -> {db_path}")
    return 0


if __name__ == "__main__":
    corpus = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CORPUS
    db = Path(sys.argv[2]) if len(sys.argv) > 2 else corpus / "hq4.db"
    sys.exit(build(corpus, db))
