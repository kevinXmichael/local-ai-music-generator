# Local AI Music Generator

Kostenlos, lokal: Song als Vorlage + neue Lyrics → Cover in `MUSIC_OUTPUT/`.

Kombiniert **Surgical Lyric-Edit** (Originalstimme bleibt) mit **Cover-Style Studio-Polish** (Timbre-Glue, Kompression, Reverb, Mix) — vollautomatisch.

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
  "output_format": "m4a",
  "mode": "surgical",
  "polish": true
}
```

```bash
cd ~/Code/kms/local-ai-music-generator
./scripts/generate.sh
```

→ `MUSIC_OUTPUT/hot-gangster-cover.m4a`

## Was passiert intern

1. Demucs-Stems (`htdemucs_ft`)  
2. Nur geänderte Wörter neu singen (YingMusic surgical)  
3. Timbre an Originalstimme kleben + Studio-Polish + Cover-Mix  

## Echtes Neu-Singen

```bash
./scripts/generate.sh setup-yingmusic
./scripts/generate.sh
```

Extras: `pip install -e ".[separate,surgical]"`

Mock: `./scripts/generate.sh --engine mock`

## Docs

- [Usage](docs/usage.md) — Settings, Polish, Formate  
- [Architecture](docs/architecture.md)  
- [Models](docs/models.md)  

## Tests

```bash
pytest -q
ruff check src tests
```
