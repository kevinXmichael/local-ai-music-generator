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
| `apply_voice_gender` | `false` | Pitch/Formant nachträglich — meist **aus** |
| `mode` | `auto` | `surgical` = nur geänderte Stellen (Originalstimme bleibt). `full` = alles neu singen |
| `chunk_seconds` | `20` | nur bei `full` |
| `max_seconds` | aus | Nur die ersten N Sekunden (Test) |
| `nfe_step` | `24` surgical / `16` full Mac | Qualität vs. Tempo |

Weitere Keys kannst du schon eintragen — unbekannte Felder bleiben in `settings.extra` für spätere Features erhalten.

### Output-Format: m4a / mp3 / wav

| Format | Wann |
|--------|------|
| **m4a (Default)** | AAC 256k — gute Qualität, kleine Datei |
| `mp3` | Maximal kompatibel (320k) |
| `wav` | Verlustfrei / DAW |

**Intern** rechnen Demucs/YingMusic immer mit WAV (rohes PCM) — so funktionieren Fast alle Audio-KI-Modelle. Dein Input (`.m4a`/`.mp3`) wird dafür nur **zwischengeparkt**, das fertige Cover schreibt wieder `.m4a`/`.mp3` nach `MUSIC_OUTPUT/`. Du musst nichts manuell in WAV speichern.

Zwischenprodukte unter `.work/` bleiben als WAV (Arbeitsqualität).

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

**Hinweis Mac / Qualität:** Für kleine Lyric-Edits (`hot mess` → `hot gangster`) immer

```json
{ "mode": "surgical" }
```

Dann bleibt die Originalstimme, nur die geänderten Stellen werden neu gesungen.
`mode: full` baut die komplette Stimme neu (klingt oft anders).

## Cleanup / Duplikate

Läuft **automatisch** bei jedem `./scripts/generate.sh` (nur ungenutzte HF-Caches + alte `.work`, behält benötigte Models und die 2 neuesten Jobs).

Manuell optional:

```bash
./scripts/generate.sh cleanup --dry-run
./scripts/generate.sh cleanup
```
