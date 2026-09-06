# Architecture

```
audio + lyrics
     │
     ▼
┌─────────────┐
│  load audio │  ffmpeg / soundfile
└──────┬──────┘
       ▼
┌─────────────┐
│  separate   │  demucs (optional) or HPSS fallback
└──────┬──────┘
       │ vocals + instrumental
       ▼
┌─────────────┐
│ lyric cover │  YingMusic (real) or mock (CI)
└──────┬──────┘
       │ new vocals
       ▼
┌─────────────┐
│ voice gender│  pitch + formant shaping (male/female)
└──────┬──────┘
       ▼
┌─────────────┐
│    mix      │  vocals + instrumental → MUSIC_OUTPUT
└─────────────┘
```

## Packages

| Module | Role |
|--------|------|
| `cli.py` | Typer entrypoints (`generate`, `setup-yingmusic`, `doctor`) |
| `pipeline.py` | Orchestrates a full job |
| `lyrics.py` | Normalize txt/srt/lrc → phrases |
| `audio_io.py` | Load/save/mix |
| `engines/separator.py` | Stem separation |
| `engines/yingmusic.py` | Subprocess wrapper around `infer.py` |
| `engines/mock_engine.py` | Deterministic offline path |
| `engines/voice_gender.py` | male/female control |

## Design goals

1. **Script-first** — one command, named output file
2. **Folder convention** — `MUSIC_INPUT` / `MUSIC_OUTPUT`
3. **Free & local** — no paid API
4. **Testable** — mock engine + synthetic audio in CI
5. **Pluggable** — swap cover engines without rewriting the CLI
