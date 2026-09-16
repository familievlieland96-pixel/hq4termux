---
name: hq4termux
description: "Local video-to-skill and cited knowledge search on Termux."
version: 0.1.0
author: Tony (ykycportal), Bossman/Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [knowledge, video-to-skill, termux, fts5, citations, local]
    related_skills: [video-to-skill, hermes-agent-skill-authoring, last30days]
---

# hq4termux

Fuses the two directions of a local "knowledge HQ" into one Termux-native
skill: a **write path** that turns a video (URL or local file) into an indexed,
timestamped segment corpus, and a **read path** that answers questions from any
such corpus with cited, clickable sources. Retrieval is plain-stdlib SQLite
FTS5 — no qmd, no ONNX, no embeddings, no binary, no network at query time.
The corpus content is local and stays local; only the query text travels.

## When to Use
- You have (or want) a local Markdown segment corpus of transcripts and want
  to **answer from it with citations** (`[Title — MM:SS](url)`).
- You have a video and want it **extracted into a searchable, cited corpus**
  (the video-to-skill write side).
- You need a **fresh-clone, IP-clean, offline** knowledge base on a phone
  (Samsung Fold 5 / Termux) with `$HOME` paths and no sudo.
- Don't use for: live streams, or when semantic (embedding) retrieval is the
  point — FTS5 is keyword retrieval; see Pitfalls for the weak-query fallback.

## Prerequisites
- Python 3.10+ with `sqlite3` (FTS5 enabled — stock on Termux/Linux/macOS).
- Read path only: nothing else.
- Write path: `yt-dlp` (`pkg install python-yt-dlp`), `ffmpeg`, and a local
  `whisper.cpp` build (`~/whisper.cpp/build/bin/whisper-cli` + a `.bin` model).
  Override locations with `WHISPER_CLI` / `WHISPER_MODEL` env vars.
- See `references/termux-setup.md` for the one-time Termux build steps.

## How to Run
All from the repo root. Use the `terminal` tool with a generous timeout.

```bash
# read path: index a corpus, then query it with citations
python3 scripts/build_index.py <corpus-dir>          # -> <corpus-dir>/hq4.db
python3 scripts/query.py <corpus-dir> "<question>" 8  # ranked, cited hits

# write path: video -> segments -> reindex (needs whisper.cpp)
python3 scripts/build_from_video.py <url-or-path> <corpus-dir>
```

## Quick Reference
- `scripts/build_index.py <corpus> [db]` — rebuild the FTS5 index (stdlib).
- `scripts/query.py <corpus-or-db> "<q>" [limit] [--json]` — cited search.
- `scripts/build_from_video.py <url-or-path> <corpus>` — download, transcribe,
  90s-segment, reindex. Scratch (mp4 + transcript) auto-routes to
  `~/scratch-hq4` and self-cleans after a successful downloaded-video run;
  local-file inputs are never touched. Knobs: `H4_SCRATCH` (scratch dir),
  `H4_KEEP_SCRATCH=1` (keep it), `HSEG_SECONDS` (segment length, default 90).
- `scripts/validate_skill.py <skill.md>` — hollow-output gate (exit 1 = hollow).
- `scripts/scan-malware.py <dir>` — static Python exfil/obfuscation scanner.

## Procedure
1. **Build the index.** `python3 scripts/build_index.py <corpus>`.
   Completion: prints `indexed N segments -> <corpus>/hq4.db`; `N` matches the
   segment file count (the repo ships a 5-segment sample corpus at `corpus/`
   so a fresh clone is immediately queryable).
2. **Query with citations.** `python3 scripts/query.py <corpus> "<question>"`.
   Completion: each hit is `[Title — MM:SS](url)` + an FTS5-highlighted
   snippet; if the corpus is silent the tool says so and stops — never invent
   a title, quote, or timestamp.
3. **Weak query?** Run up to 3 focused retries with concrete business terms /
   synonyms. The tool already OR-joins the significant terms on a zero-match
   raw query (the fuzzy fallback); broaden only by re-choosing terms, not by
   loosening scope.
4. **Grow the corpus from video** (write path). `python3 scripts/build_from_video.py <url> <corpus>`.
   Completion: `transcribed N chars, T s -> K segments` then `indexed N`.
   For YouTube, if the bot-check wall appears, climb the ladder: `yt-dlp -U`,
   then `YT_COOKIES=~/cookies.txt`, then `YT_PROXY=socks5://...` (see below).
5. **Distill a reusable skill from a transcript** (optional). Read the
   segments, then author a SKILL.md to the `hermes-agent-skill-authoring`
   standard and run `scripts/validate_skill.py` on it before `skill_view`.
   Completion: gate exits 0 (no placeholder strings, real sections).

## Pitfalls
- **FTS5 is keyword, not semantic.** A question phrased very differently from
  the source words can miss. The built-in OR-fallback + 3-term retry is the
  mitigation; TF-IDF rerank over the same DB (stdlib) is the upgrade path if
  recall feels weak.
- **FTS5 has no stemmer/plural handling.** Live test: querying "elephant"
  missed a segment that only contained "elephants". Query with the word as it
  likely appears in the source (or both forms), or add an FTS5 trigram /
  porter stemmer tokenizer at index build time if recall suffers.
- **qmd / ONNX deliberately absent.** The reference `ask-hormozi` pack used a
  Rust `qmd` binary (glibc-only) — it does not run on Termux bionic. This
  skill replaces its retrieval job with stdlib FTS5, so there is no binary to
  build.
- **Corpus copyright is not code.** Any bundled third-party transcripts are
  that holder's IP. This repo's committed corpus is synthetic/sample only.
  Keep real third-party corpora (e.g. a scraped channel) on-device; the
  `build_index.py`/`query.py`/`build_from_video.py` are ours and may be
  published stripped; the data may not.
- **Local-file citations are honest.** A corpus built from local video cites
  the real file path, never a fabricated `youtube.com/watch` link.
- **`/tmp` is unwritable on Termux** — write scratch under `$HOME`, not `/tmp`.
  `build_from_video.py` does this itself: downloads and whisper transcripts
  go to `~/scratch-hq4` (never into the corpus dir) and are auto-removed
  after a successful downloaded-video run.
- **No `YT_COOKIES` on the phone.** Termux has no local browser, so
  `--cookies-from-browser` is unusable; export a Netscape `.txt` on another
  device and point `YT_COOKIES` at it.

## Verification
- `python3 scripts/build_index.py corpus` prints `indexed 5 segments` on a
  fresh clone (the sample corpus), and `python3 scripts/query.py corpus
  "gap register"` returns the sample grocery SOP with a clickable citation.
- Write path: `python3 scripts/build_from_video.py <local.mp4> <scratch-corpus>`
  prints a `transcribed N chars ... -> K segments` line and reindexes.
- `python3 scripts/scan-malware.py .` reports no exfil/obfuscation in `scripts/`.
- `git status` clean; `corpus/hq4.db` and `__pycache__/` are gitignored so the
  index is regenerated, not shipped.
