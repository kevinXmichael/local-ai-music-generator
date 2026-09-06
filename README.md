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
./scripts/generate.sh
```

→ `MUSIC_OUTPUT/hot-gangster-cover.m4a` (Default: AAC 256k; alternativ `mp3` / `wav` in `settings.json`).

## Echtes Neu-Singen

Ohne YingMusic ändern sich die Lyrics **nicht**. Einmalig:

```bash
./scripts/generate.sh setup-yingmusic
./scripts/generate.sh
```

Mock nur zum Pipeline-Test: `./scripts/generate.sh --engine mock`

Aufräumen (automatisch bei jedem Generate; manuell optional):

```bash
./scripts/generate.sh cleanup --dry-run
./scripts/generate.sh cleanup
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
