# Architecture

## Drop-in flow

```
MUSIC_INPUT/<job>/
  song.* + lyrics new.* + lyrics original.* + voice.txt?
        │
        ▼
 discover_jobs()  →  pipeline.generate()  →  MUSIC_OUTPUT/<name>.wav
```

Kein Pflicht-Flags: `python -m local_ai_music_generator` reicht.

```
audio + lyrics
     │
     ▼
┌─────────────┐
│  load audio │  ffmpeg / soundfile
└──────┬──────┘
       ▼
┌─────────────┐
│  separate   │  demucs (optional extra) oder HPSS
└──────┬──────┘
       │ vocals + instrumental
       ▼
┌─────────────┐
│ lyric cover │  YingMusic (real) oder mock (CI)
└──────┬──────┘
       │ new vocals
       ▼
┌─────────────┐
│ voice gender│  pitch + formant (male/female)
└──────┬──────┘
       ▼
┌─────────────┐
│    mix      │  → MUSIC_OUTPUT
└─────────────┘
```

## Packages

| Module | Role |
|--------|------|
| `discover.py` | Feste Dateinamen in `MUSIC_INPUT` finden |
| `cli.py` | Default = `run` aus dem Drop-in-Ordner |
| `pipeline.py` | Orchestriert einen Job |
| `lyrics.py` | txt/srt/lrc normalisieren |
| `audio_io.py` | Load/save/mix |
| `engines/separator.py` | Stem-Trennung |
| `engines/yingmusic.py` | Wrapper um `infer.py` |
| `engines/mock_engine.py` | Offline/CI |
| `engines/voice_gender.py` | male/female |

## Design goals

1. Dateien reinlegen, ein Befehl — fertig
2. `MUSIC_INPUT` / `MUSIC_OUTPUT` Konvention
3. Kostenlos & lokal
4. Mock-Engine für Tests/CI
5. Engines austauschbar
