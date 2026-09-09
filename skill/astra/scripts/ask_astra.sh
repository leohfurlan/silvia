#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "$0")" && pwd -P)"

if command -v python3 >/dev/null 2>&1; then
  python_bin='python3'
elif command -v python >/dev/null 2>&1; then
  python_bin='python'
else
  echo "Python 3 is required to call GPT-6 Astra." >&2
  exit 127
fi

exec "$python_bin" "$script_dir/ask_astra.py" "$@"
