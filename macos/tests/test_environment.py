"""Preflight failures must block admission; optional chat must not block images."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('studio_environment_probe',Path(__file__).resolve().parents[1]/'backend/environment_probe.py')
probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)

class OfflineOllama:
    def open(self,*a,**kw): raise OSError('offline')

class EnvironmentChecks(unittest.TestCase):
    def collect(self,check):
        with tempfile.TemporaryDirectory() as data:
            events=list(probe.collect(Path(data),check=check,opener=OfflineOllama()))
            return events,{x['id']:x for x in events}
    def test_offline_chat_is_optional(self):
        events,items=self.collect(lambda name:'test version')
        self.assertTrue(probe.ready(items))
        self.assertEqual(items['ollama']['state'],'optional')
        self.assertFalse(items['ollama']['required'])
        self.assertIn('dependencies',items)
        self.assertIn('pipeline',items)
        self.assertIn('gpu',items)
    def test_unavailable_optional_enhancer_does_not_block_entry(self):
        def check(name):
            if name=='enhancer':raise ImportError('optional interface missing')
            return 'ok'
        _,items=self.collect(check)
        self.assertTrue(probe.ready(items));self.assertFalse(items['enhancer']['required'])
        self.assertEqual(items['enhancer']['state'],'optional')
    def test_missing_import_and_gpu_block(self):
        for broken in ('diffusers','gpu','dependencies'):
            def check(name):
                if name==broken:raise ImportError('test missing dependency')
                return 'test version'
            _,items=self.collect(check)
            self.assertFalse(probe.ready(items))
            failures=[v for v in items.values() if v['state']=='fail']
            self.assertEqual(len(failures),1)
            self.assertIn('diagnostic',failures[0])
    def test_timeout_is_not_a_success(self):
        def check(name):
            if name=='pipeline':raise subprocess.TimeoutExpired('probe',60)
            return 'test version'
        _,items=self.collect(check)
        self.assertFalse(probe.ready(items))
        self.assertEqual(items['pipeline']['state'],'fail')
        self.assertFalse(probe.ready({}))
    def test_recovery_distinguishes_environment_from_memory(self):
        self.assertTrue(probe.is_environment_error("ModuleNotFoundError: No module named 'torch'"))
        self.assertTrue(probe.is_environment_error('DLL load failed'))
        self.assertFalse(probe.is_environment_error('CUDA out of memory'))
        self.assertFalse(probe.is_environment_error('No generated image was returned'))

if __name__=='__main__':unittest.main()
