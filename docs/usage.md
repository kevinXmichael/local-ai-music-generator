# Usage

## Projektort

Das Repo liegt unter:

```text
~/Code/kms/local-ai-music-generator
```

## Super-einfacher Workflow

1. Dateien in `MUSIC_INPUT/` (oder einen Unterordner) legen  
2. Ein Befehl starten  
3. Ergebnis liegt in `MUSIC_OUTPUT/`

```bash
cd ~/Code/kms/local-ai-music-generator
source .venv/bin/activate   # falls vorhanden
python -m local_ai_music_generator
```

### Erwartete Dateinamen

| Datei | Pflicht | Bedeutung |
|-------|---------|-----------|
| `song.m4a` / `song.mp3` / `audio.*` / `track.*` | ja | Vorlage-Song |
| `lyrics new.txt` | ja | Neue Lyrics (auch `lyrics_new.txt`) |
| `lyrics original.txt` | empfohlen | Original-Text wie auf dem Track |
| `voice.txt` | nein | eine Zeile: `female` oder `male` (Default: female) |
| `output name.txt` | nein | Ausgabe-Basename; sonst Name der Audio-Datei |

Leerzeichen, `_` und `-` sind egal: `lyrics new`, `lyrics_new`, `lyrics-new` funktionieren alle.

### Beispiel (Hot Mess → hot gangster)

```text
MUSIC_INPUT/hot-mess/
  song.m4a
  lyrics new.txt          # enthält „hot gangster“
  lyrics original.txt     # enthält „hot mess“
  voice.txt               # female
  output name.txt         # hot-gangster-cover
```

```bash
python -m local_ai_music_generator
# → MUSIC_OUTPUT/hot-gangster-cover.wav
```

Mehrere Songs: einfach mehrere Unterordner unter `MUSIC_INPUT/` — der Befehl baut alle.

## Stem-Trennung (Demucs) — was heißt das?

Der Song wird intern in **Gesang (Vocals)** und **Rest/Instrumental** zerlegt.  
Nur so kann die KI den Text neu singen und danach wieder mit dem Beat mischen.

| Modus | Befehl | Qualität |
|-------|--------|----------|
| Standard (ohne Extra-Install) | schon dabei | grobe Trennung (HPSS) — reicht zum Testen |
| **Besser (empfohlen)** | `pip install -e ".[separate]"` | **Demucs** — deutlich sauberere Vocals/Instrumental |

`".[separate]"` ist nur die optionale Extra-Gruppe aus `pyproject.toml` (Demucs + Torch). Kein zweites Projekt — einmal im venv installieren:

```bash
cd ~/Code/kms/local-ai-music-generator
source .venv/bin/activate
pip install -e ".[separate]"
```

Danach nutzt `run` Demucs automatisch, wenn es importierbar ist. Check:

```bash
python -m local_ai_music_generator doctor
```

## Echtes Neu-Singen (YingMusic)

Ohne YingMusic läuft ein **mock**-Pfad (Pipeline/Test). Für echte Lyric-Covers:

```bash
python -m local_ai_music_generator setup-yingmusic
# Weights laut docs/models.md laden
python -m local_ai_music_generator          # engine=auto → yingmusic wenn da
python -m local_ai_music_generator --engine mock   # erzwungen testen
```

## Optional: Voice override auf der CLI

Nur wenn du `voice.txt` nicht anfassen willst:

```bash
python -m local_ai_music_generator --voice male
```
