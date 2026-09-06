# MUSIC_INPUT

Dateien hier ablegen, dann:

```bash
./scripts/generate.sh
```

Pro Song ein Unterordner (Beispiel `hot-mess/`):

| Datei | Inhalt |
|-------|--------|
| `song.m4a` | Vorlage |
| `lyrics new.txt` | neue Lyrics |
| `lyrics original.txt` | Original-Lyrics |
| `settings.json` | `voice`, `mode`, `polish`, `output_format`, … |

Beispiel `settings.json`:

```json
{
  "voice": "female",
  "output_name": "hot-gangster-cover",
  "output_format": "m4a",
  "mode": "surgical",
  "polish": true,
  "demucs_model": "htdemucs_ft"
}
```

Details: [docs/usage.md](../docs/usage.md)
