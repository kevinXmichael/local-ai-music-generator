# Local AI Music Generator

Kostenlos, lokal: Song als Vorlage + neue Lyrics → Cover in `MUSIC_OUTPUT/`.

**Pfad:** `~/Code/kms/local-ai-music-generator`  
**Repo:** https://github.com/kevinXmichael/local-ai-music-generator

## So einfach geht’s

Dateien so benennen und in `MUSIC_INPUT/` (oder einen Unterordner) legen:

```text
MUSIC_INPUT/hot-mess/
  song.m4a
  lyrics new.txt
  lyrics original.txt
  voice.txt              # optional: female | male
  output name.txt        # optional
```

Dann:

```bash
cd ~/Code/kms/local-ai-music-generator
source .venv/bin/activate
python -m local_ai_music_generator
```

→ `MUSIC_OUTPUT/hot-gangster-cover.wav` (bzw. Name aus `output name.txt` / Audiodatei).

## Setup (einmal)

```bash
cd ~/Code/kms/local-ai-music-generator
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
brew install ffmpeg   # falls nötig
```

**Bessere Vocal/Instrumental-Trennung (empfohlen):**

```bash
pip install -e ".[separate]"
```

Das ist nur Demucs+Torch im selben venv — Erklärung: [docs/usage.md](docs/usage.md#stem-trennung-demucs--was-heißt-das).

**Echtes Neu-Singen der Lyrics:**

```bash
python -m local_ai_music_generator setup-yingmusic
# Weights siehe docs/models.md
```

## Docs

- [Usage (Drop-in + Demucs erklärt)](docs/usage.md)
- [Architecture](docs/architecture.md)
- [Models](docs/models.md)

## Tests & CI

```bash
pytest -q
ruff check src tests
```

## Rechte

Nur Material nutzen, das du nutzen darfst. Audio-Dateien werden nicht committed (`.gitignore`).
