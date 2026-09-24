"""Per-user paths survive upgrades; explicit shell overrides remain isolated."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def default_data():
    return Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local/share')))/'QwenStudio'

def local_settings():
    result={}
    for path in (default_data()/'locations.json',ROOT/'settings.local.json'):
        if not path.is_file():continue
        values=json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(values,dict):raise ValueError('存储位置设置须为 JSON 对象。')
        for key in ('data','model'):
            if key in values:
                if not isinstance(values[key],str) or not values[key].strip():raise ValueError('存储位置须为有效路径。')
                result[key]=values[key]
    return result

def data_path():
    return Path(os.environ.get('QWEN_STUDIO_DATA') or local_settings().get('data') or default_data()).expanduser()

def model_path(data):
    configured=None if os.environ.get('QWEN_STUDIO_DATA') else local_settings().get('model')
    return Path(os.environ.get('QWEN_STUDIO_MODEL') or configured or data/'models/Qwen-Image-2.1').expanduser()
