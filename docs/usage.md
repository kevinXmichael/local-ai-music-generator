# Usage

## Projektort

```text
~/Code/kms/local-ai-music-generator
```

## Drop-in Workflow

1. Dateien in `MUSIC_INPUT/<job>/` legen  
2. `python -m local_ai_music_generator`  
3. Cover landet in `MUSIC_OUTPUT/`

### Dateien

| Datei | Pflicht | Bedeutung |
|-------|---------|-----------|
| `song.m4a` / `audio.*` / `track.*` | ja | Vorlage |
| `lyrics new.txt` | ja | Neue Lyrics |
| `lyrics original.txt` | empfohlen | Original-Text |
| `settings.json` | nein | Voice, Output-Name, Format, spätere Optionen |

### `settings.json`

```json
{
  "voice": "female",
  "output_name": "hot-gangster-cover",
  "output_format": "m4a"
}
```

| Key | Default | Werte |
|-----|---------|--------|
| `voice` | `female` | `female` \| `male` |
| `output_name` | Audiodatei-Stem | freier Name |
| `output_format` | `m4a` | `m4a` \| `mp3` \| `wav` |

Weitere Keys kannst du schon eintragen — unbekannte Felder bleiben in `settings.extra` für spätere Features erhalten.

### Output-Format: warum m4a?

| Format | Wann |
|--------|------|
| **m4a (Default)** | AAC 256k — gute Qualität, kleine Datei, einfach abspielbar |
| `mp3` | Maximal kompatibel (320k) |
| `wav` | Verlustfrei / Weiterverarbeitung in DAWs |

Zwischenprodukte unter `.work/` bleiben als WAV (Arbeitsqualität). Nur das fertige Cover in `MUSIC_OUTPUT` nutzt `output_format`.

### Beispiel

```text
MUSIC_INPUT/hot-mess/
  song.m4a
  lyrics new.txt
  lyrics original.txt
  settings.json
```

```bash
python -m local_ai_music_generator
# → MUSIC_OUTPUT/hot-gangster-cover.m4a
```

## Stem-Trennung (Demucs)

Der Song wird in **Gesang** und **Instrumental** zerlegt.

| Modus | Befehl | Qualität |
|-------|--------|----------|
| Standard | schon dabei | HPSS (Test) |
| Besser | `pip install -e ".[separate]"` | Demucs |

```bash
pip install -e ".[separate]"
python -m local_ai_music_generator doctor
```

## Echtes Neu-Singen

```bash
python -m local_ai_music_generator setup-yingmusic
python -m local_ai_music_generator
python -m local_ai_music_generator --engine mock
```
