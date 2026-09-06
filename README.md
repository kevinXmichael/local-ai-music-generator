# Local AI Music Generator

Kostenlos, lokal: Song als Vorlage + neue Lyrics → Cover in `MUSIC_OUTPUT/`.

**Pfad:** `~/Code/kms/local-ai-music-generator`  
**Repo:** https://github.com/kevinXmichael/local-ai-music-generator

## So einfach

```text
MUSIC_INPUT/hot-mess/
  song.m4a
  lyrics new.txt
  lyrics original.txt
  settings.json
```

```json
{
  "voice": "female",
  "output_name": "hot-gangster-cover",
  "output_format": "m4a"
}
```

```bash
cd ~/Code/kms/local-ai-music-generator
source .venv/bin/activate
python -m local_ai_music_generator
```

→ `MUSIC_OUTPUT/hot-gangster-cover.m4a` (Default: AAC 256k; alternativ `mp3` / `wav` in `settings.json`).

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
brew install ffmpeg
# bessere Stem-Trennung:
pip install -e ".[separate]"
# echtes Lyric-Re-Singing:
python -m local_ai_music_generator setup-yingmusic
```

## Docs

- [Usage](docs/usage.md) — Drop-in, `settings.json`, Demucs, Formate
- [Architecture](docs/architecture.md)
- [Models](docs/models.md)

## Tests

```bash
pytest -q
ruff check src tests
```
