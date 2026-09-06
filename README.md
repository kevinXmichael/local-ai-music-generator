# Local AI Music Generator

Kostenlos, lokal, in Python: nimm einen Song als **Melodie-/Timbre-Vorlage**, gib **angepasste Lyrics** (ein Wort oder ganzer Text), wähle **male/female**, und erzeuge einen Cover-Track.

Typischer Flow (dein Beispiel):

- Vorlage: *Hot Mess* Entrance Theme (`.m4a`)
- Lyrics: `hot mess` → `hot gangster`
- Output: `MUSIC_OUTPUT/hot-gangster-cover.wav`

## Quick start

```bash
cd local-ai-music-generator
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
# empfohlen für bessere Stem-Trennung:
# pip install -e ".[separate]"
brew install ffmpeg   # oder apt install ffmpeg
```

Audio + Lyrics nach `MUSIC_INPUT/` legen (Sample-Lyrics liegen unter `MUSIC_INPUT/samples/`).

```bash
python -m local_ai_music_generator generate \
  --audio MUSIC_INPUT/samples/hot_mess_theme.m4a \
  --lyrics MUSIC_INPUT/samples/hot_mess_lyrics_hot_gangster.txt \
  --original-lyrics MUSIC_INPUT/samples/hot_mess_lyrics_original.txt \
  --voice female \
  --output-name hot-gangster-cover
```

Oder:

```bash
chmod +x scripts/generate.sh
./scripts/generate.sh \
  MUSIC_INPUT/samples/hot_mess_theme.m4a \
  MUSIC_INPUT/samples/hot_mess_lyrics_hot_gangster.txt \
  hot-gangster-cover \
  female
```

Ausgabe: `MUSIC_OUTPUT/<output-name>.wav` (+ `.json` Meta).

## Engines

| Engine | Was sie tut | Wann |
|--------|-------------|------|
| `auto` (Default) | Nutzt YingMusic wenn vorhanden, sonst `mock` | Alltag |
| `yingmusic` | Echte lyric-preserving Re-Singing (Melody behalten, Text ändern) | GPU empfohlen |
| `mock` | Pipeline-Test ohne Neural-Model (Gender-Shaping der Template-Vocals) | CI / Smoke |

Echte Covers (nahe am Original, nur Lyrics geändert):

```bash
python -m local_ai_music_generator setup-yingmusic
# danach Weights laut YingMusic-README von Hugging Face laden
python -m local_ai_music_generator generate ... --engine yingmusic
```

YingMusic-Singer-Plus: [GitHub](https://github.com/ASLP-lab/YingMusic-Singer-Plus) · [Model](https://huggingface.co/ASLP-lab/YingMusic-Singer-Plus)

## Ordner

```
MUSIC_INPUT/     # Songs + Lyrics rein
MUSIC_OUTPUT/    # fertige Covers
models/          # optionale lokale Weights
.work/           # Zwischenprodukte (Stems, Meta)
vendor/          # YingMusic-Checkout (nach setup)
```

## Voice

`--voice female|male` formantiert/pitch-shifted die gesungenen Vocals (leichtgewichtig, offline). Mit YingMusic bleibt die Melodie der Vorlage; Gender ist ein zusätzlicher Shaping-Schritt.

## Docs

- [Usage](docs/usage.md)
- [Architecture](docs/architecture.md)
- [Models](docs/models.md)

## Tests & CI

```bash
pytest -q
ruff check src tests
```

GitHub Actions: `.github/workflows/ci.yml` (Python 3.10 + 3.12).

## Hinweis zu Rechten

Nur Material verwenden, das du nutzen darfst. Audio-Binaries werden **nicht** ins Repo committed (`.gitignore`). Sample-Lyrics dienen dem Workflow-Beispiel.
