"""Find app runtimes without treating stale or moved runtime pointers as fatal."""
import json
import os
from pathlib import Path
import sys


def selected_runtime(directory):
    directory=Path(directory)
    try:
        value=json.loads((directory/'runtime-path.json').read_text(encoding='utf-8-sig'))['python']
        if not isinstance(value,str) or not value.strip():return None
        path=Path(value).expanduser()
        if not path.is_absolute():path=directory/path
        return path if path.is_file() else None
    except (OSError,ValueError,KeyError,TypeError):return None


def runtime_python(root,data=None):
    override=os.environ.get('QWEN_STUDIO_PYTHON')
    if override:return Path(override).expanduser()
    root=Path(root)
    for directory in (data,root):
        selected=selected_runtime(directory) if directory is not None else None
        if selected:return selected
    suffix='Scripts/python.exe' if sys.platform=='win32' else 'bin/python3'
    candidates=([Path(data)/'runtime'/suffix] if data is not None else [])+[root/'.venv'/suffix,root/'runtime'/suffix]
    return next((path for path in candidates if path.is_file()),candidates[0])
