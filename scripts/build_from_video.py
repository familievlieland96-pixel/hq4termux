#!/usr/bin/env python3
"""build_from_video.py - Extend a hq4termux corpus from one video.

Termux-native write path (the video-to-skill side of the fused skill):
  1. yt-dlp download (bot-check ladder: -U, player_client, YT_COOKIES, YT_PROXY)
  2. whisper.cpp local transcription (offline, no stubs)
  3. split into 90s segments as corpus/segments/<video_id>/<start>.md
  4. rebuild the FTS5 index over the whole corpus

No qmd / ONNX / embeddings. Stdlib + yt-dlp + ffmpeg + whisper.cpp only.

Usage:
  python3 build_from_video.py <url-or-path> [corpus-dir]
"""
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
WHISPER_CLI = Path(os.environ.get(
    "WHISPER_CLI", Path.home() / "whisper.cpp/build/bin/whisper-cli"))
WHISPER_MODEL = Path(os.environ.get(
    "WHISPER_MODEL", Path.home() / "whisper.cpp/models/ggml-base.en.bin"))
SEG_SECONDS = int(os.environ.get("HSEG_SECONDS", "90"))


def ensure_whisper() -> None:
    missing = []
    if not WHISPER_CLI.exists():
        missing.append(f"whisper-cli at {WHISPER_CLI} (build: see references/termux-setup.md)")
    if not WHISPER_MODEL.exists():
        missing.append(f"whisper model at {WHISPER_MODEL} (see references/termux-setup.md)")
    if missing:
        print("ERROR - whisper.cpp not ready:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        sys.exit(1)


def resolve_url(url: str) -> tuple[str, str]:
    """Return (source_name, video_id-ish slug). For YouTube URLs, use the
    video id; for local files, use the stem."""
    m = re.search(r"[?&]v=([A-Za-z0-9_-]{6,})|youtu\.be/([A-Za-z0-9_-]{6,})|/shorts/([A-Za-z0-9_-]{6,})", url)
    if m:
        return url, m.group(1) or m.group(2) or m.group(3)
    p = Path(url)
    return url, re.sub(r"[^A-Za-z0-9_-]", "-", p.stem)[:40] or "local"


def download_video(url: str) -> str:
    """Download with the YouTube bot-check ladder. Returns the real file path."""
    out_base = os.environ.get("YT_OUT", "hq4_video")
    out_dir = Path.cwd()
    cmd = [
        "yt-dlp",
        "-f", "b[height<=480]/bv*[height<=480]+ba/b",
        "--no-playlist",
        "-o", str(out_dir / f"{out_base}.%(ext)s"),
        "--extractor-args", "youtube:player_client=web_embedded",
    ]
    cookies = os.environ.get("YT_COOKIES")
    if cookies:
        cp = Path(cookies).expanduser()
        if cp.exists():
            cmd += ["--cookies", str(cp)]
        else:
            print(f"WARNING: YT_COOKIES={cookies} missing - continuing without", file=sys.stderr)
    proxy = os.environ.get("YT_PROXY")
    if proxy:
        cmd += ["--proxy", proxy]
    cmd.append(url)
    print(f"Downloading {url} ...")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if r.returncode != 0:
        err = r.stderr.strip()
        if "Sign in to confirm you're not a bot" in err or "please log in" in err.lower():
            raise RuntimeError(
                "YouTube bot-check wall. Climb the ladder:\n"
                "  1) yt-dlp -U  (or yt-dlp -U youtube-dl/ytdl-nightly)\n"
                "  2) YT_COOKIES=~/cookies.txt (exported from a signed-in browser elsewhere)\n"
                f"Details: {err[-400:]}")
        raise RuntimeError(f"yt-dlp failed: {err[:400]}")
    cands = sorted(out_dir.glob(f"{out_base}.*"))
    real = [c for c in cands if c.is_file() and c.stat().st_size > 0]
    if not real:
        raise RuntimeError(f"no {out_base}.* file after yt-dlp: {cands}")
    chosen = max(real, key=lambda p: p.stat().st_size)
    for stale in real:
        if stale != chosen:
            stale.unlink()
    return str(chosen)


def transcribe(video_file: str) -> tuple[str, int]:
    """whisper-cli -> (transcript text, duration seconds via ffprobe)."""
    out = Path("output")
    out.mkdir(exist_ok=True)
    stem = out / "hq4_transcript"
    subprocess.run(
        [str(WHISPER_CLI), "-m", str(WHISPER_MODEL), "-t", "4",
         "-otxt", "-of", str(stem), video_file],
        capture_output=True, text=True, timeout=1800, check=True)
    text = (out / "hq4_transcript.txt").read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError("whisper produced an empty transcript - check the video has audio.")
    dur = 0
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", video_file],
            capture_output=True, text=True, timeout=60)
        dur = int(float(r.stdout.strip()))
    except Exception:
        dur = 0
    return text, dur


def fetch_title(url: str) -> str:
    """Best-effort real title. YouTube -> yt-dlp single JSON; local -> stem."""
    if url.startswith(("http", "https")):
        try:
            r = subprocess.run(
                ["yt-dlp", "--no-warnings", "--skip-download",
                 "--dump-single-json", url],
                capture_output=True, text=True, timeout=120)
            import json as _json
            if r.returncode == 0 and r.stdout.strip():
                return _json.loads(r.stdout).get("title", url)
        except Exception:
            pass
    return Path(url).stem


def write_segments(corpus_dir: Path, video_id: str, url: str,
                   text: str, dur: int, title: str) -> int:
    """Split the transcript into ~90s segments; proportional time offsets."""
    sdir = corpus_dir / "segments" / video_id
    sdir.mkdir(parents=True, exist_ok=True)
    for old in sdir.glob("*.md"):
        old.unlink()
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return 0
    # Proportional segmentation: each chunk gets an estimated start second.
    target_chunks = max(1, round(dur / SEG_SECONDS)) if dur else 1
    word_count = len(" ".join(lines).split())
    per_seg = max(1, round(word_count / target_chunks))  # words per chunk
    chunks = []
    cur: list[str] = []
    for l in lines:
        cur.append(l)
        if len(" ".join(cur).split()) >= per_seg:
            chunks.append(" ".join(cur))
            cur = []
    if cur:
        chunks.append(" ".join(cur))
    ts = datetime.now().strftime("%Y-%m-%d")
    n = 0
    for i, chunk in enumerate(chunks):
        start = i * SEG_SECONDS
        mmss = f"{start // 60:02d}:{start % 60:02d}"
        ts_url = f"{url}&t={start}s" if ("watch?" in url or "youtu.be" in url) else url
        (sdir / f"{start:06d}.md").write_text(
            f"---\n"
            f'episode_id: "{video_id}"\n'
            f'title: "{title}"\n'
            f'published: "{ts}"\n'
            f'duration_seconds: {SEG_SECONDS}\n'
            f'episode_url: "{url}"\n'
            f'transcript_source: "whisper.cpp"\n'
            f'start_seconds: {start}\n'
            f'end_seconds: {start + SEG_SECONDS}\n'
            f'timestamp_url: "{ts_url}"\n'
            f"---\n\n"
            f"# {mmss} segment {i}\n\n{chunk}\n\n"
            f'Source: [{mmss}]({ts_url})\n',
            encoding="utf-8")
        n += 1
    return n


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    url = sys.argv[1]
    corpus_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else REPO / "corpus"
    ensure_whisper()
    name, vid = resolve_url(url)
    video_file = download_video(url) if url.startswith(("http", "https")) else url
    if not Path(video_file).exists():
        raise RuntimeError(f"video not found: {video_file}")
    text, dur = transcribe(video_file)
    title = fetch_title(url)
    nseg = write_segments(corpus_dir, vid, url, text, dur, title)
    print(f"transcribed {len(text)} chars, {dur}s -> {nseg} segments under {corpus_dir}/segments/{vid}")
    # Rebuild the index over the whole corpus.
    subprocess.run([sys.executable, str(SCRIPTS / "build_index.py"),
                    str(corpus_dir)], check=True)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as e:
        print(f"FAILED: {e}", file=sys.stderr)
        sys.exit(1)
