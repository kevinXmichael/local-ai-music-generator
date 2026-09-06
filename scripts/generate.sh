#!/usr/bin/env bash
# Simple one-shot wrapper. Example:
#   ./scripts/generate.sh \
#     MUSIC_INPUT/samples/hot_mess_theme.m4a \
#     MUSIC_INPUT/samples/hot_mess_lyrics_hot_gangster.txt \
#     hot-gangster-cover \
#     female
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

AUDIO="${1:?audio path}"
LYRICS="${2:?lyrics path}"
OUT_NAME="${3:?output name}"
VOICE="${4:-female}"
ORIGINAL="${5:-MUSIC_INPUT/samples/hot_mess_lyrics_original.txt}"

exec python -m local_ai_music_generator generate \
  --audio "$AUDIO" \
  --lyrics "$LYRICS" \
  --original-lyrics "$ORIGINAL" \
  --voice "$VOICE" \
  --output-name "$OUT_NAME" \
  --engine auto
