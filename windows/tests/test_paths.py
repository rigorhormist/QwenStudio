import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import studio_paths

class UpgradeLocations(unittest.TestCase):
    def test_new_release_reuses_custom_locations_and_respects_overrides(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);app=base/'new-release';app.mkdir();local=base/'local';settings=local/'QwenStudio';settings.mkdir(parents=True)
            saved={'data':str(base/'existing data'),'model':str(base/'existing model')}
            (settings/'locations.json').write_text(json.dumps(saved))
            with patch.object(studio_paths,'ROOT',app),patch.dict(os.environ,{'LOCALAPPDATA':str(local)},clear=True):
                self.assertEqual(studio_paths.data_path(),Path(saved['data']))
                self.assertEqual(studio_paths.model_path(studio_paths.data_path()),Path(saved['model']))
                (app/'settings.local.json').write_text(json.dumps({'model':str(base/'preferred model')}))
                self.assertEqual(studio_paths.model_path(studio_paths.data_path()),base/'preferred model')
                os.environ['QWEN_STUDIO_DATA']=str(base/'isolated')
                self.assertEqual(studio_paths.model_path(studio_paths.data_path()),base/'isolated/models/Qwen-Image-2.1')
                del os.environ['QWEN_STUDIO_DATA']
                (app/'settings.local.json').write_text('{broken')
                with self.assertRaises(ValueError):studio_paths.data_path()
