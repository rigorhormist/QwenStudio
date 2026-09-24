import json
import os
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from runtime_setup import RuntimeInstaller
from runtime_location import runtime_python


class SafeRepairTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.env=patch.dict(os.environ,{},clear=False);self.env.start()
        os.environ.pop('QWEN_STUDIO_PYTHON',None)
        self.old=self.root/('.venv/Scripts/python.exe' if sys.platform=='win32' else '.venv/bin/python3');self.old.parent.mkdir(parents=True);self.old.write_bytes(b'keep runtime')
        (self.root/'requirements.txt').write_text('diffusers @ https://example.test/pinned.zip\ntransformers==5.17.0\n');self.model=self.root/'model.safetensors';self.model.write_bytes(b'keep weights')
    def tearDown(self):self.env.stop();self.temp.cleanup()

    def test_healthy_runtime_does_not_install_or_create_a_replacement(self):
        installer=RuntimeInstaller(self.root,self.root/'data',current=self.old)
        with patch.object(installer,'probe',return_value={'ready':True}),patch.object(installer,'run_command') as command:
            self.assertEqual(installer.repair(),self.old);command.assert_not_called()
        self.assertFalse((self.root/'data/runtime-path.json').exists())
        self.assertFalse((self.root/'data/runtime').exists())

    def test_failed_install_keeps_runtime_selection_and_files(self):
        state={'python':str(self.old)};(self.root/'data').mkdir();(self.root/'data/runtime-path.json').write_text(json.dumps(state))
        installer=RuntimeInstaller(self.root,self.root/'data',current=self.old)
        with patch.object(installer,'probe',return_value={'ready':False,'items':{}}),patch.object(installer,'run_command',side_effect=RuntimeError('network unavailable')):
            with self.assertRaisesRegex(RuntimeError,'network unavailable'):installer.repair()
        self.assertEqual(runtime_python(self.root,self.root/'data'),self.old)
        self.assertEqual(self.old.read_bytes(),b'keep runtime');self.assertEqual(self.model.read_bytes(),b'keep weights')
        self.assertEqual(json.loads((self.root/'data/runtime-path.json').read_text()),state)

    def test_failed_final_validation_never_activates_candidate(self):
        installer=RuntimeInstaller(self.root,self.root/'data',current=self.old)
        with patch.object(installer,'probe',return_value={'ready':False,'items':{}}),patch.object(installer,'run_command',return_value='{"ok":true}'),patch.object(installer,'pip'),patch.object(installer,'inherit_packages'):
            with self.assertRaisesRegex(RuntimeError,'original runtime is still selected'):installer.repair()
        self.assertEqual(runtime_python(self.root,self.root/'data'),self.old)
        self.assertFalse((self.root/'data/runtime-path.json').exists())

    def test_activation_happens_only_after_validation(self):
        installer=RuntimeInstaller(self.root,self.root/'data',current=self.old)
        with patch.object(installer,'probe',side_effect=[{'ready':False,'items':{}},{'ready':True}]),patch.object(installer,'run_command',return_value='{"ok":true}'),patch.object(installer,'pip'),patch.object(installer,'inherit_packages',side_effect=lambda python:(python.parent.mkdir(parents=True,exist_ok=True),python.touch())):
            selected=installer.repair()
        self.assertEqual(runtime_python(self.root,self.root/'data').resolve(),selected.resolve())
        self.assertTrue(selected.is_relative_to((self.root/'data/runtime').resolve()))
        self.assertEqual(self.old.read_bytes(),b'keep runtime')

    def test_staged_environment_reuses_packages_without_changing_source(self):
        suffix='Scripts/python.exe' if sys.platform=='win32' else 'bin/python3'
        source=self.root/'source';candidate=self.root/'candidate'
        for directory in (source,candidate):subprocess.run([sys.executable,'-m','venv','--without-pip',str(directory)],check=True,capture_output=True)
        def run(python,code):return subprocess.check_output([str(python),'-I','-X','utf8','-c',code],text=True).strip()
        source_python=source/suffix;candidate_python=candidate/suffix
        source_site=Path(run(source_python,'import sysconfig;print(sysconfig.get_path("purelib"))'))
        candidate_site=Path(run(candidate_python,'import sysconfig;print(sysconfig.get_path("purelib"))'))
        module='qwen_repair_fixture'
        (source_site/(module+'.py')).write_text('value="working CUDA stand-in"')
        installer=RuntimeInstaller(self.root,self.root/'data',current=source_python)
        installer.inherit_packages(candidate_python)
        self.assertEqual(run(candidate_python,'import '+module+';print('+module+'.value)'),'working CUDA stand-in')
        (candidate_site/(module+'.py')).write_text('value="repaired locally"')
        self.assertEqual(run(candidate_python,'import '+module+';print('+module+'.value)'),'repaired locally')
        self.assertEqual(run(source_python,'import '+module+';print('+module+'.value)'),'working CUDA stand-in')

    def test_cpu_only_pytorch_can_be_repaired(self):
        installer=RuntimeInstaller(self.root,self.root/'data',current=self.old)
        report={'ready':False,'items':{'gpu':{'id':'gpu','required':True,'state':'fail','diagnostic':'当前 PyTorch 不含 CUDA 支持，请修复依赖。'}}}
        with patch.object(installer,'probe',return_value=report),patch.object(installer,'run_command',side_effect=RuntimeError('staging reached')):
            with self.assertRaisesRegex(RuntimeError,'staging reached'):installer.repair()

    def test_driver_failure_does_not_trigger_package_reinstallation(self):
        installer=RuntimeInstaller(self.root,self.root/'data',current=self.old)
        report={'ready':False,'items':{'gpu':{'id':'gpu','required':True,'state':'fail'}}}
        with patch.object(installer,'probe',return_value=report),patch.object(installer,'run_command') as command:
            with self.assertRaisesRegex(RuntimeError,'driver'):installer.repair()
            command.assert_not_called()


if __name__=='__main__':unittest.main()
