#!/bin/zsh
set -eu
studio_root="$(cd "$(dirname "$0")" && pwd)"
studio_data="${QWEN_STUDIO_DATA:-$HOME/Library/Application Support/Qwen Studio}"
typeset -a studio_candidates
if [[ -n "${QWEN_STUDIO_PYTHON:-}" ]]; then
  studio_candidates=("$QWEN_STUDIO_PYTHON")
elif [[ -n "${QWEN_STUDIO_PYTHON_BOOTSTRAP:-}" ]]; then
  studio_candidates=("$QWEN_STUDIO_PYTHON_BOOTSTRAP")
else
  if [[ -f "$studio_data/runtime-path.json" ]]; then
    studio_selected=$(/usr/bin/plutil -extract python raw -o - "$studio_data/runtime-path.json" 2>/dev/null || true)
    if [[ -n "$studio_selected" ]]; then
      [[ "$studio_selected" = /* ]] || studio_selected="$studio_data/$studio_selected"
      studio_candidates+=("$studio_selected")
    fi
  fi
  studio_candidates+=("$studio_data/runtime/bin/python3" "$studio_root/runtime/bin/python3" "$studio_root/.venv/bin/python3" "$studio_root/../../../.venv/bin/python3")
  for studio_version in 3.11 3.12 3.13 3.10; do
    studio_candidates+=("/Library/Frameworks/Python.framework/Versions/$studio_version/bin/python3" "/opt/homebrew/opt/python@$studio_version/bin/python$studio_version" "/usr/local/opt/python@$studio_version/bin/python$studio_version")
  done
  studio_candidates+=(/opt/homebrew/bin/python3 /usr/local/bin/python3)
fi
for studio_candidate in "${studio_candidates[@]}"; do
  [[ -x "$studio_candidate" ]] || continue
  if studio_result=$("$studio_candidate" -I -B -X utf8 -c 'import sys,platform; assert (3,10)<=sys.version_info[:2]<(3,14) and platform.machine()=="arm64"; print(sys.executable)' 2>/dev/null); then
    print -r -- "$studio_result"; exit 0
  fi
done
print -u2 'Install arm64 Python 3.10–3.13, or correct QWEN_STUDIO_PYTHON, then retry.'
exit 1
