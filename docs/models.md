# Models & optionale Extras

## Stem-Trennung: Demucs (`.[separate]`)

**Problem:** Ein fertiger Song ist eine Mischung. Zum Covern brauchen wir getrennt:
Gesang (als Melodie-/Timbre-Vorlage) und Instrumental (zum Remixen).

**Ohne Extra-Install:** eingebaute HPSS-Näherung (schnell, ungenau).  
**Mit Demucs:** deutlich bessere Trennung.

```bash
pip install -e ".[separate]"
```

Das installiert nur zusätzliche Python-Pakete (`demucs`, `torch`, …) in dein venv.
Kein zweites Repo. Einmal ausführen, danach automatisch aktiv.

Siehe auch [usage.md](usage.md#stem-trennung-demucs--was-heißt-das).

## YingMusic-Singer-Plus (echtes Lyric-Editing)

Melody-preserving lyric editing: ein Wort oder ganzer Text, Melodie bleibt nahe am Original.

```bash
python -m local_ai_music_generator setup-yingmusic
```

Klont [ASLP-lab/YingMusic-Singer-Plus](https://github.com/ASLP-lab/YingMusic-Singer-Plus) nach `vendor/`.
Weights: https://huggingface.co/ASLP-lab/YingMusic-Singer-Plus — GPU empfohlen.

```bash
export YINGMUSIC_HOME=/pfad/zu/YingMusic-Singer-Plus   # optional
python -m local_ai_music_generator --engine yingmusic
```

## Mock engine

Kein Neural-Model. Für CI und „läuft die Pipeline?“. Formt nur Template-Vocals (Gender) — singt keine neuen Worte.
