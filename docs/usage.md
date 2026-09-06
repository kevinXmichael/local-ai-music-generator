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
| `apply_voice_gender` | `false` | Pitch/Formant nachträglich — meist **aus** lassen (klingt sonst blechern) |

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

## Echtes Neu-Singen (Pflicht für neue Lyrics)

Ohne YingMusic ändert sich der gesungene Text **nicht**. Der alte Mock-Fallback ist abgeschaltet.

```bash
# einmalig (Python 3.10 + Model-Download, mehrere GB)
./scripts/generate.sh setup-yingmusic

# danach normal
./scripts/generate.sh
```

Nur Pipeline-Test ohne Lyric-Change:

```bash
./scripts/generate.sh --engine mock
```

**Hinweis Mac:** YingMusic ist für NVIDIA gebaut; auf Apple Silicon läuft es über MPS/CPU und kann bei langen Songs **sehr langsam** sein. Kurze Clips zuerst testen.

## Cleanup / Duplikate

Inference nutzt nur `ASLP-lab/YingMusic-Singer`. Der Cache `YingMusic-Singer-Plus` ist überflüssig.

```bash
./scripts/generate.sh cleanup --dry-run
./scripts/generate.sh cleanup
```

Löscht ungenutzte HF-Caches und alte `.work`-Jobs (behält die 2 neuesten).
