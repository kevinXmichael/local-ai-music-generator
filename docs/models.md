# Models & optionale Extras

## Warum klang der Output bisher schlecht / alter Text?

Ohne YingMusic lief nur ein **Mock**-Pfad: gleiche Vocals + Pitch-Shaping.
Der ändert **keine** Lyrics und klingt oft blechern. Der stille Fallback ist abgeschaltet.

## YingMusic (echte Lyric-Edits)

```bash
brew install python@3.10 espeak-ng
./scripts/generate.sh setup-yingmusic
./scripts/generate.sh
```

- Repo: `vendor/YingMusic-Singer-Plus` (eigene Python-3.10-venv)
- Model: Hugging Face `ASLP-lab/YingMusic-Singer` (wird beim ersten Lauf geladen)
- Mac: MPS/CPU — kurze Clips ok, volle Songs können **sehr lange** brauchen
- Linux/NVIDIA: deutlich schneller

## Stem-Trennung: Demucs

```bash
pip install -e ".[separate]"
```

Default-Modell: `htdemucs_ft` (fein abgestimmt). Fallback: `htdemucs`.
YingMusic kann Vocals auch selbst trennen (`--separate_vocals`); Demucs bleibt der Pipeline-Standard.

## Studio polish (ohne RVC)

Nach Surgical/Full läuft lokal automatisch:

- spektrales Timbre-Matching (Inserts → Originalstimme)
- Soft-Kompressor + Presence
- leichtes Plate-Reverb (`reverb_mix: auto`)
- Cover-Mix mit Soft-Limiter

Abschalten: `"polish": false` in `settings.json`.

## `settings.json`

```json
{
  "voice": "female",
  "output_name": "hot-gangster-cover",
  "output_format": "m4a",
  "mode": "surgical",
  "polish": true,
  "apply_voice_gender": false
}
```

`apply_voice_gender: true` formantiert nachträglich — meist aus lassen (klingt blechern).
