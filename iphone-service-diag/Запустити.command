#!/bin/bash
# Подвійний клік на Mac → відкриває вікно ServiceDiag
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"
DESKTOP_DIR="$ROOT/desktop"
VENV="$DESKTOP_DIR/.venv"

export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"

if ! command -v python3 >/dev/null 2>&1; then
  osascript -e 'display dialog "Не знайдено python3.\nВстановіть з https://www.python.org/downloads/ (галочка Add to PATH) або через brew install python." buttons {"OK"} default button 1 with title "ServiceDiag"'
  exit 1
fi

if [ ! -d "$VENV" ]; then
  osascript -e 'display dialog "Спочатку один раз запустіть файл:\n«Встановити один раз.command»" buttons {"OK"} default button 1 with title "ServiceDiag"'
  exit 1
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"
cd "$DESKTOP_DIR"
exec python -m service_diag.gui
