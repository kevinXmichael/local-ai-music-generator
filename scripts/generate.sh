#!/usr/bin/env bash
# Drop-in: Dateien in MUSIC_INPUT/ legen, dann:
#   ./scripts/generate.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec python -m local_ai_music_generator "$@"
