#!/bin/bash
# Один раз: створити venv і поставити залежності (подвійний клік на Mac)
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"
DESKTOP_DIR="$ROOT/desktop"
VENV="$DESKTOP_DIR/.venv"

export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"

echo "=== ServiceDiag: встановлення ==="
echo "Папка: $ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Помилка: python3 не знайдено."
  echo "Встановіть Python 3 з https://www.python.org/downloads/"
  read -r -p "Натисніть Enter…"
  exit 1
fi

python3 -m venv "$VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
python -m pip install --upgrade pip
pip install -r "$DESKTOP_DIR/requirements.txt"

echo
echo "Готово. Тепер можна подвійним кліком відкрити «Запустити.command»"
read -r -p "Натисніть Enter, щоб закрити…"
