# Architecture

## Drop-in flow

```
MUSIC_INPUT/<job>/
  song.* + lyrics new.* + lyrics original.* + settings.json?
        │
        ▼
 discover_jobs()  →  pipeline.generate()  →  MUSIC_OUTPUT/<name>.<m4a|mp3|wav>
```

```
audio + lyrics
     │
     ▼
┌─────────────┐
│  load audio │  ffmpeg / soundfile
└──────┬──────┘
       ▼
┌─────────────┐
│  separate   │  demucs htdemucs_ft (oder HPSS)
└──────┬──────┘
       │ vocals + instrumental
       ▼
┌─────────────────────┐
│ surgical | full     │  YingMusic lyric edit
│ (core splices)      │  + per-splice timbre glue
└──────┬──────────────┘
       ▼
┌─────────────┐
│   polish    │  spectral glue, compress, presence, reverb
└──────┬──────┘
       ▼
┌─────────────┐
│ studio mix  │  vocal/inst balance + soft limit → MUSIC_OUTPUT
└─────────────┘
```

## Packages

| Module | Role |
|--------|------|
| `discover.py` | Drop-in Dateien + `settings.json` |
| `cli.py` | Default = `run` |
| `pipeline.py` | Orchestriert einen Job |
| `surgical.py` | Nur geänderte Kernwörter ersetzen |
| `polish.py` | Cover-ähnliches Finish (lokal, ohne RVC) |
| `lyrics.py` / `lyrics_diff.py` | Lyrics + Diff |
| `audio_io.py` | Load/save/mix |
| `engines/separator.py` | Demucs / HPSS |
| `engines/yingmusic.py` | YingMusic Infer |
| `engines/mock_engine.py` | Offline/CI |
| `engines/voice_gender.py` | optional male/female |

## Design goals

1. Dateien reinlegen, ein Befehl — fertig  
2. Surgical Lyric-Edit **und** Cover-Mix-Qualität, lokal & automatisiert  
3. `MUSIC_INPUT` / `MUSIC_OUTPUT` Konvention  
4. Kostenlos & lokal (kein Cloud-RVC nötig)  
5. Mock-Engine für Tests/CI  
