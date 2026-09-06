# Sample inputs

Place your song + lyrics here.

This repo ships **example lyrics** for the Chelsea Green “Hot Mess” entrance theme workflow:

| File | Role |
|------|------|
| `hot_mess_lyrics_original.txt` | Lyrics as sung on the recording (`hot mess`) |
| `hot_mess_lyrics_hot_gangster.txt` | Edited target lyrics (`hot gangster`) |
| `hot_mess_theme.m4a` | Local-only audio (not committed; copy from your Downloads) |

Copy audio into this folder (gitignored):

```bash
cp "/path/to/Chelsea Green – Hot Mess (Entrance Theme).m4a" \
  MUSIC_INPUT/samples/hot_mess_theme.m4a
```

Then generate:

```bash
python -m local_ai_music_generator generate \
  --audio MUSIC_INPUT/samples/hot_mess_theme.m4a \
  --lyrics MUSIC_INPUT/samples/hot_mess_lyrics_hot_gangster.txt \
  --original-lyrics MUSIC_INPUT/samples/hot_mess_lyrics_original.txt \
  --voice female \
  --output-name hot-gangster-cover
```
