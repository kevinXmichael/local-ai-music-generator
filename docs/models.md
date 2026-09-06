# Models

## YingMusic-Singer-Plus (recommended for real covers)

Melody-preserving lyric editing: change one word or the full text while keeping the template performance’s melody/rhythm as guidance.

```bash
python -m local_ai_music_generator setup-yingmusic
```

This clones [ASLP-lab/YingMusic-Singer-Plus](https://github.com/ASLP-lab/YingMusic-Singer-Plus) into `vendor/YingMusic-Singer-Plus` and attempts to install its requirements.

Then follow their README to download weights from Hugging Face:

- Model: https://huggingface.co/ASLP-lab/YingMusic-Singer-Plus

Optional:

```bash
export YINGMUSIC_HOME=/absolute/path/to/YingMusic-Singer-Plus
```

Run with:

```bash
python -m local_ai_music_generator generate ... --engine yingmusic
```

**Hardware:** GPU strongly recommended. CPU may work for short clips but will be slow.

## Demucs (optional separation)

```bash
pip install -e ".[separate]"
```

Uses `htdemucs` when available; otherwise the pipeline falls back to librosa HPSS.

## Mock engine

No neural weights. Used automatically when YingMusic is missing, and always in CI. It gender-shapes the separated template vocals so you can validate I/O, folders, and mixing — it does **not** phonetically re-sing new lyrics.

## Voice gender without RVC

`engines/voice_gender.py` applies a light pitch + formant shift. For artist-cloning quality, train/plug an RVC model later; the cover engine interface is intentionally small.
