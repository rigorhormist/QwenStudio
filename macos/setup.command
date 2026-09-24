#!/bin/zsh
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONUTF8=1 PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
studio_data="${QWEN_STUDIO_DATA:-$HOME/Library/Application Support/Qwen Studio}"
studio_python=$(/bin/zsh ./find-python.command)
"$studio_python" -X utf8 backend/runtime_setup.py --root "$PWD" --data "$studio_data" --python "$studio_python"
