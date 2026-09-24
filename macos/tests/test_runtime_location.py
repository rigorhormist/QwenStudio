import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from runtime_location import runtime_python

class RuntimeLocationTests(unittest.TestCase):
    def test_shared_selection_survives_app_update_and_stale_pointer(self):
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{},clear=False):
            os.environ.pop('QWEN_STUDIO_PYTHON',None)
            base=Path(temp);data=base/'data';data.mkdir();app=base/'new-release';app.mkdir()
            suffix='Scripts/python.exe' if sys.platform=='win32' else 'bin/python3'
            healthy=data/'runtime/env-healthy'/suffix;healthy.parent.mkdir(parents=True);healthy.touch()
            (data/'runtime-path.json').write_text(json.dumps({'python':healthy.relative_to(data).as_posix()}))
            (app/'runtime-path.json').write_text(json.dumps({'python':'Z:/removed/python.exe'}))
            self.assertEqual(runtime_python(app,data),healthy)
            # A broken pointer must not hide a valid app-local environment.
            fallback=app/'.venv'/suffix;fallback.parent.mkdir(parents=True);fallback.touch()
            (data/'runtime-path.json').write_text('{incomplete')
            self.assertEqual(runtime_python(app,data),fallback)
            os.environ['QWEN_STUDIO_PYTHON']=str(base/'explicit')
            self.assertEqual(runtime_python(app,data),base/'explicit')
