# Usage

## Projektort

```text
~/Code/kms/local-ai-music-generator
```

## Drop-in Workflow

1. Dateien in `MUSIC_INPUT/<job>/` legen  
2. `python -m local_ai_music_generator` bzw. `./scripts/generate.sh`  
3. Cover landet in `MUSIC_OUTPUT/`

### Dateien

| Datei | Pflicht | Bedeutung |
|-------|---------|-----------|
| `song.m4a` / `audio.*` / `track.*` | ja | Vorlage |
| `lyrics new.txt` | ja | Neue Lyrics |
| `lyrics original.txt` | empfohlen | Original-Text |
| `settings.json` | nein | Voice, Mode, Polish, Formate |

### `settings.json`

```json
{
  "voice": "female",
  "output_name": "hot-gangster-cover",
  "output_format": "m4a",
  "mode": "surgical",
  "polish": true,
  "vocal_gain": 1.08,
  "instrumental_gain": 0.9,
  "reverb_mix": "auto",
  "demucs_model": "htdemucs_ft",
  "nfe_step": 28
}
```

| Key | Default | Werte |
|-----|---------|--------|
| `voice` | `female` | `female` \| `male` |
| `output_name` | Audiodatei-Stem | freier Name |
| `output_format` | `m4a` | `m4a` \| `mp3` \| `wav` |
| `apply_voice_gender` | `false` | Pitch/Formant nachträglich — meist **aus** |
| `mode` | `auto` | `surgical` = nur geänderte Stellen (Originalstimme). `full` = alles neu |
| `polish` | `true` | Studio-Finish: Timbre-Glue, Kompression, Presence, Reverb, Cover-Mix |
| `vocal_gain` | `1.06` | Lautstärke Gesang im Mix |
| `instrumental_gain` | `0.9` | Lautstärke Instrumental |
| `reverb_mix` | `auto` | `auto` oder `0`–`0.45` (Nassanteil) |
| `demucs_model` | `htdemucs_ft` | Demucs-Modell (`htdemucs` Fallback) |
| `chunk_seconds` | `20` | nur bei `full` |
| `max_seconds` | aus | Nur die ersten N Sekunden (Test) |
| `nfe_step` | `28` surgical / `16` full Mac | Qualität vs. Tempo |

### Pipeline: beste aus beiden Welten (lokal)

1. **Demucs** — saubere Stems (`htdemucs_ft`)  
2. **Surgical YingMusic** — nur geänderte Wörter neu singen, Rest = Originalstimme  
3. **Timbre-Glue** — spektrale Hüllkurve der Inserts an Originalstimme  
4. **Studio polish** — Kompression, Presence-EQ, leichtes Plate-Reverb  
5. **Cover-Mix** — Gesang/Instrumental-Balance + Soft-Limiter (wie AICoverGen-Stil)

Kein Cloud, kein RVC-Training nötig — alles automatisiert in einem Lauf.

### Output-Format: m4a / mp3 / wav

| Format | Wann |
|--------|------|
| **m4a (Default)** | AAC 256k — gute Qualität, kleine Datei |
| `mp3` | Maximal kompatibel (320k) |
| `wav` | Verlustfrei / DAW |

**Intern** rechnen Demucs/YingMusic immer mit WAV. Input `.m4a`/`.mp3` wird nur zwischengeparkt; Output wieder komprimiert nach `MUSIC_OUTPUT/`.

### Beispiel

```text
MUSIC_INPUT/hot-mess/
  song.m4a
  lyrics new.txt
  lyrics original.txt
  settings.json
```

```bash
./scripts/generate.sh
# → MUSIC_OUTPUT/hot-gangster-cover.m4a
```

## Stem-Trennung (Demucs)

| Modus | Befehl | Qualität |
|-------|--------|----------|
| Standard | schon dabei | HPSS (Test) |
| Besser | `pip install -e ".[separate]"` | Demucs `htdemucs_ft` |

```bash
pip install -e ".[separate]"
python -m local_ai_music_generator doctor
```

## Echtes Neu-Singen (Pflicht für neue Lyrics)

Ohne YingMusic ändert sich der gesungene Text **nicht**.

```bash
./scripts/generate.sh setup-yingmusic
./scripts/generate.sh
```

Nur Pipeline-Test ohne Lyric-Change:

```bash
./scripts/generate.sh --engine mock
```

## Surgical extras

```bash
pip install -e ".[surgical]"
```

Braucht `faster-whisper` für die Zeitstellen der geänderten Phrasen.

## Cleanup

Bei jedem Generate laufen Cache-Aufräumungen. Manuell:

```bash
./scripts/generate.sh cleanup --dry-run
./scripts/generate.sh cleanup
```
