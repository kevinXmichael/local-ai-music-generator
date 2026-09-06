# Usage

## Prerequisites

- Python 3.10+
- `ffmpeg` on `PATH`
- Optional: NVIDIA GPU + CUDA for YingMusic
- Optional: `pip install -e ".[separate]"` for Demucs stem separation

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Generate a cover

```bash
python -m local_ai_music_generator generate \
  --audio MUSIC_INPUT/samples/hot_mess_theme.m4a \
  --lyrics MUSIC_INPUT/samples/hot_mess_lyrics_hot_gangster.txt \
  --original-lyrics MUSIC_INPUT/samples/hot_mess_lyrics_original.txt \
  --voice female \
  --output-name hot-gangster-cover \
  --engine auto
```

### Arguments

| Flag | Description |
|------|-------------|
| `--audio` / `-a` | Template track (mp3, m4a, wav, flac, …) |
| `--lyrics` / `-l` | **New** lyrics to sing |
| `--original-lyrics` | Lyrics as on the recording (for edit alignment) |
| `--voice` / `-v` | `female` or `male` |
| `--output-name` / `-o` | Basename → `MUSIC_OUTPUT/<name>.wav` |
| `--engine` / `-e` | `auto`, `yingmusic`, or `mock` |
| `--keep-work` | Keep stems under `.work/` (default on) |

### Shell helper

```bash
./scripts/generate.sh <audio> <lyrics> <output-name> [voice] [original-lyrics]
```

## Lyric formats

- `.txt` — plain / section headers like `[Chorus]`
- `.srt` — timed SRT **or** lyric sheets mistakenly named `.srt`
- `.lrc` — timed LRC lines

Section headers are ignored when building model phrase strings.

## Only change one word

Keep a copy of the original lyrics and edit the target file (or use a small script):

```python
from pathlib import Path
from local_ai_music_generator.lyrics import apply_replacements, load_lyrics

original = load_lyrics(Path("MUSIC_INPUT/samples/hot_mess_lyrics_original.txt"))
edited = apply_replacements(original.text, {"hot mess": "hot gangster"})
Path("MUSIC_INPUT/samples/hot_mess_lyrics_hot_gangster.txt").write_text(edited)
```

## Health check

```bash
python -m local_ai_music_generator doctor
```
