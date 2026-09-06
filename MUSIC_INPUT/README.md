# MUSIC_INPUT

Dateien hier ablegen, dann:

```bash
python -m local_ai_music_generator
```

Pro Song ein Unterordner (Beispiel `hot-mess/`):

| Datei | Inhalt |
|-------|--------|
| `song.m4a` | Vorlage |
| `lyrics new.txt` | neue Lyrics |
| `lyrics original.txt` | Original-Lyrics |
| `settings.json` | `voice`, `output_name`, `output_format`, … |

Beispiel `settings.json`:

```json
{
  "voice": "female",
  "output_name": "hot-gangster-cover",
  "output_format": "m4a"
}
```

`output_format`: `m4a` (Default, AAC 256k), `mp3` (320k) oder `wav` (verlustfrei).

Details: [docs/usage.md](../docs/usage.md)
