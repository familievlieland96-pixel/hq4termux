# Termux setup (one-time, ~15 minutes)

The read path (`build_index.py`, `query.py`) needs only `python3` with FTS5 —
stock. The write path needs the toolchain below. Run on a Samsung Fold 5 with
the F-Droid Termux build (the Play Store build is frozen and breaks on updates).

## 1. Install the toolchain
```bash
pkg update
pkg install -y build-essential cmake ffmpeg python python-yt-dlp
```
- `build-essential` = clang + linkers (to compile whisper.cpp)
- `python-yt-dlp` = the `yt-dlp` command
- `ffmpeg` = video decoding + ffprobe duration

## 2. Build whisper.cpp
```bash
cd ~
git clone https://github.com/ggerganov/whisper.cpp
cd whisper.cpp
cmake -B build -DCMAKE_BUILD_TYPE=Release -DWHISPER_SDL2=OFF \
      -DWHISPER_BUILD_TESTS=OFF -DWHISPER_COMMON_FFMPEG=ON
cmake --build build -j
```
Why each flag:
- `WHISPER_SDL2=OFF` — configure fails on Termux without it (SDL2 is GUI-only).
- `WHISPER_COMMON_FFMPEG=ON` — lets `whisper-cli` read `.mp4/.mkv` directly,
  no manual `.wav` conversion.

## 3. Download the model
```bash
cd models
bash download-ggml-model.sh base.en     # ~148 MB, English
```
(non-English: `small` or `large-v3`, same command, bigger download.)

## 4. Verify — do not skip
```bash
cd ~/whisper.cpp
./build/bin/whisper-cli -m models/ggml-base.en.bin samples/jfk.wav
```
You should see the JFK quote. If not, fix this before running the write path —
`build_from_video.py` fails loudly and points back here if whisper is absent.

## 5. Point hq4termux at your build (optional overrides)
Default locations are `~/whisper.cpp/build/bin/whisper-cli` and
`~/whisper.cpp/models/ggml-base.en.bin`. If yours differ:
```bash
export WHISPER_CLI=/abs/path/to/whisper-cli
export WHISPER_MODEL=/abs/path/to/ggml-base.en.bin
```

## Local media on Android storage
```bash
termux-setup-storage     # once, grant access
```
Then pass a full path: `python3 scripts/build_from_video.py /sdcard/Download/clip.mp4 corpus`.

## YouTube bot-check ladder (write path only)
When the source is a YouTube URL and you hit "Sign in to confirm you're not a
bot", climb in order:
1. `yt-dlp -U` (or `yt-dlp -U youtube-dl/ytdl-nightly`) — keep the extractor current.
2. `YT_COOKIES=~/cookies.txt` — Netscape export from a signed-in browser on
   *another* device (Termux has no local browser, so `--cookies-from-browser`
   is unusable).
3. `YT_PROXY=socks5://127.0.0.1:9050` (Tor) — only if the network itself is
   flagged; phone-VPN egress needs none.
The format pick stays `b[height<=480]/...` (free, no-sign-in class) with
`--extractor-args "youtube:player_client=web_embedded"`.

## Note on qmd
The reference `ask-hormozi` pack depended on the `qmd` Rust binary
(https://sh.qntx.fun/qmd), which ships glibc-only `unknown-linux-gnu` release
artifacts. Termux runs **bionic**, so that binary will not run, and its
`fastembed`/ONNX + `sqlite-vec` deps need heavy native builds. hq4termux
deliberately replaces that retrieval job with stdlib SQLite FTS5 — there is
nothing to build beyond the whisper.cpp toolchain above.
