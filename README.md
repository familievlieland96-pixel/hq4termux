# hq4termux

A Termux-native **knowledge HQ**: one skill that both **builds** a local,
timestamped, cited corpus from video, and **answers** from any such corpus with
clickable `[Title — MM:SS](url)` sources. Retrieval is plain-stdlib SQLite FTS5 —
no qmd, no ONNX, no binary, no network at query time.

Built for The Block: clean, lean, agile, phone-native (Samsung Fold 5 / Termux,
`$HOME` paths, no sudo, no Microsoft). Fuses the two directions that used to
live in `video-to-skill` (write: video → skill) and `ask-hormozi` (read: cited
search) into a single reusable skill.

## Two directions, one skill
- **Write path** (`scripts/build_from_video.py`): URL or local file → yt-dlp
  (bot-check ladder) → local whisper.cpp → 90s Markdown segments → rebuild FTS5.
- **Read path** (`scripts/build_index.py` + `scripts/query.py`): any segment
  corpus → cited keyword search with FTS5 snippets and the honest
  "the corpus is silent" behaviour.

## Quick start
```bash
# read path (works on the shipped sample corpus, no setup beyond python3)
python3 scripts/build_index.py corpus
python3 scripts/query.py corpus "grocery gap register" 8

# write path (needs the Termux toolchain - see references/termux-setup.md)
python3 scripts/build_from_video.py "https://youtu.be/<id>" corpus
```

## Repo layout
```
SKILL.md                    # the fused skill (load with skill_view)
scripts/
  build_index.py           # corpus -> FTS5 index (stdlib)
  query.py                 # cited search over the index (stdlib)
  build_from_video.py      # video -> segments -> reindex (yt-dlp + whisper.cpp)
  validate_skill.py        # hollow-output gate (exit 1 = hollow)
  scan-malware.py          # static Python exfil/obfuscation scanner
corpus/
  segments/<vid>/<start>.md   # sample synthetic corpus (IP-clean, committed)
  hq4.db                    # generated index (gitignored)
references/
  termux-setup.md          # one-time Termux build steps (whisper.cpp, yt-dlp, ffmpeg)
```

## Honesty & copyright rules (The Block standard)
- **Our code is ours.** The scripts are original, stdlib-only, published
  stripped (no secrets). The sample corpus is synthetic and ours.
- **Third-party transcripts are not code.** If you index a real scraped
  channel corpus, that data is the rights holder's IP and stays **on-device** —
  never in a GitHub push. The index (`.db`) and downloaded clips are gitignored
  and regenerated, so the committed repo carries only our code + sample.
- **Citations are honest.** Local-file corpora cite their real path; only real
  YouTube sources produce `youtube.com/watch` links. A zero-match query says
  "the corpus is silent" instead of inventing an answer.

## License
MIT. Built for Tony (ykycportal) by Bossman/Hermes Agent. Part of The Block
tools.
