#!/usr/bin/env bash
# Drop-in: Dateien in MUSIC_INPUT/ legen, dann:
#   ./scripts/generate.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="$ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  echo "Kein .venv gefunden. Einmalig:" >&2
  echo "  cd \"$ROOT\"" >&2
  echo "  python3 -m venv .venv && .venv/bin/pip install -e ." >&2
  exit 1
fi

if ! "$PYTHON" -c "import local_ai_music_generator" 2>/dev/null; then
  echo "Paket fehlt im venv — installiere …" >&2
  "$PYTHON" -m pip install -e .
fi

# Keep macOS responsive while heavy ML runs
run() {
  if command -v taskpolicy >/dev/null 2>&1; then
    exec taskpolicy -c utility nice -n 15 "$PYTHON" -m local_ai_music_generator "$@"
  fi
  exec nice -n 15 "$PYTHON" -m local_ai_music_generator "$@"
}

run "$@"
