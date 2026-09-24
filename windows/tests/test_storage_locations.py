import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import storage_locations as storage
from runtime_setup import RuntimeInstaller
from runtime_location import runtime_python

class StorageLocationsTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name);self.data=self.base/'data';self.data.mkdir()
        self.env=patch.dict(os.environ,{},clear=False);self.env.start();os.environ.pop('QWEN_STUDIO_MODEL',None);os.environ.pop('QWEN_STUDIO_PYTHON',None)
        content=b'local weights';self.files=[{'path':'weights.bin','size':len(content),'sha256':hashlib.sha256(content).hexdigest()}]
        self.manifest=patch.object(storage,'files_for',return_value=self.files);self.manifest.start()
        self.model=self.base/'old'/'Qwen-Image-2.1';self.locations=storage.ModelLocations(self.data,self.model)
        self.activated=[]
    def tearDown(self):self.manifest.stop();self.env.stop();self.temp.cleanup()
    def folder(self,path,content=b'local weights'):
        path.mkdir(parents=True);(path/'weights.bin').write_bytes(content);return path
    def activate(self,*args):self.activated.append(args)
    def wait(self):
        deadline=time.monotonic()+3
        while self.locations.status()['operation'].get('busy') and time.monotonic()<deadline:time.sleep(.01)
        self.assertFalse(self.locations.status()['operation']['busy'])
        return self.locations.status()['operation']
    def test_import_read_only_folder_verifies_without_copy_or_download(self):
        source=self.folder(self.base/'shared model');source.chmod(0o555)
        try:
            self.locations.select('image',str(source),'existing',self.activate)
            self.assertEqual(self.wait()['state'],'complete')
            self.assertTrue(storage.model_ready(source,'image',self.data))
            self.assertFalse((source/'.verified').exists())
            self.assertEqual(sorted(p.name for p in source.iterdir()),['weights.bin'])
            self.assertEqual(storage.ModelLocations(self.data,self.model).paths['image'],source.resolve())
            self.assertEqual(self.locations.paths['pe-t2i'],self.model.parent/'Qwen-Image-2.1-PE-T2I')
        finally:source.chmod(0o755)
    def test_modified_file_invalidates_receipt(self):
        source=self.folder(self.base/'model');self.locations.select('image',str(source),'existing',self.activate);self.wait()
        (source/'weights.bin').write_bytes(b'wrong weights')
        self.assertFalse(storage.model_ready(source,'image',self.data))
    def test_bad_same_size_hash_keeps_original_location(self):
        source=self.folder(self.base/'bad',b'wrong weights');self.locations.select('image',str(source),'existing',self.activate)
        self.assertEqual(self.wait()['state'],'error');self.assertEqual(self.locations.paths['image'],self.model);self.assertFalse(self.activated)
    def test_hugging_face_cache_and_multiple_snapshots(self):
        hub=self.base/'hub';first=self.folder(hub/'models--Qwen--Qwen-Image-2.1'/'snapshots'/'revision-a')
        self.assertEqual(storage.existing_model(hub,'image'),first.resolve())
        self.folder(first.parent/'revision-b')
        with self.assertRaisesRegex(ValueError,'snapshots'):storage.existing_model(hub,'image')
    def test_download_selection_persists_separate_pe_and_partial_files(self):
        parent=self.base/'disk';parent.mkdir();partial=parent/'Qwen-Image-2.1';partial.mkdir();(partial/'weights.bin.part').write_bytes(b'partial')
        self.locations.select('image',str(parent),'download',self.activate)
        self.locations.select('pe-t2i',str(parent),'download',self.activate)
        self.assertEqual(self.locations.paths['image'],partial);self.assertEqual((partial/'weights.bin.part').read_bytes(),b'partial')
        loaded=storage.ModelLocations(self.data,self.model)
        self.assertEqual(loaded.paths['pe-t2i'],parent/'Qwen-Image-2.1-PE-T2I');self.assertEqual(loaded.paths['pe-i2i'],self.model.parent/'Qwen-Image-2.1-PE-I2I')
    def test_disconnected_drive_is_not_recreated_or_replaced(self):
        path=self.base/'disconnected'/'Qwen-Image-2.1';self.locations.save('image',path)
        loaded=storage.ModelLocations(self.data,self.model);self.assertEqual(loaded.paths['image'],path)
        with self.assertRaises(ValueError):storage.check_download_parent(path)
        self.assertFalse(path.parent.exists())
    def test_incomplete_import_and_explicit_override(self):
        folder=self.base/'partial';folder.mkdir()
        with self.assertRaises(ValueError):self.locations.select('image',str(folder),'existing',self.activate)
        with patch.dict(os.environ,{'QWEN_STUDIO_MODEL':str(self.model)}):
            with self.assertRaises(ValueError):self.locations.select('image',str(folder),'download',self.activate)
        self.assertEqual(self.locations.paths['image'],self.model)
    def test_malformed_preferences_are_reported(self):
        (self.data/'model-locations.json').write_text('{broken')
        self.assertTrue(storage.ModelLocations(self.data,self.model).status()['error'])
    def test_cancelled_check_never_activates(self):
        source=self.folder(self.base/'model')
        self.locations.operation={'busy':True};self.locations.cancelled.set();self.locations._verify('image',source,self.activate)
        self.assertEqual(self.locations.operation['state'],'error');self.assertFalse(self.activated)
    def test_external_dependency_directory_is_activated_by_absolute_path(self):
        root=self.base/'app';root.mkdir();(root/'requirements.txt').write_text('diffusers @ https://example.test/pinned.zip\n')
        external=self.base/'external dependencies';external.mkdir();old=self.base/'python';old.touch()
        installer=RuntimeInstaller(root,self.data,current=old,directory=external)
        with patch.object(installer,'probe',side_effect=[{'ready':False,'items':{}},{'ready':True}]),patch.object(installer,'run_command',return_value='{"ok":true}'),patch.object(installer,'pip'),patch.object(installer,'inherit_packages',side_effect=lambda python:(python.parent.mkdir(parents=True),python.touch())):
            chosen=installer.repair()
        self.assertTrue(chosen.is_relative_to(external));self.assertEqual(runtime_python(root,self.data),chosen)
        self.assertTrue(Path(json.loads((self.data/'runtime-path.json').read_text())['python']).is_absolute())
    def test_missing_dependency_disk_is_not_recreated(self):
        directory=self.base/'unplugged'
        with self.assertRaises(ValueError):RuntimeInstaller(self.base,self.data,directory=directory)
        self.assertFalse(directory.exists())

class StorageApiTest(unittest.TestCase):
    def test_jobs_imports_and_downloads_guard_path_changes(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'QWEN_STUDIO_DATA':tmp,'QWEN_STUDIO_TOKEN':'storage-test'}):
            spec=importlib.util.spec_from_file_location('storage_server',Path(__file__).resolve().parents[1]/'backend/server.py');s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
            server=s.ThreadingHTTPServer(('127.0.0.1',0),s.Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            import urllib.request,urllib.error
            def post(route,payload):
                request=urllib.request.Request(f'http://127.0.0.1:{server.server_port}/api/'+route,data=json.dumps(payload).encode(),headers={'X-Studio-Token':'storage-test'})
                try:
                    with urllib.request.urlopen(request) as result:return result.status
                except urllib.error.HTTPError as error:return error.code
            try:
                s.QUEUE.append(('fixture',{}))
                self.assertEqual(post('model/location',{'target':'image','kind':'download','folder':tmp}),400)
                s.QUEUE.clear();s.LOCATIONS.operation={'busy':True}
                self.assertEqual(post('model/download',{'source':'modelscope'}),400)
                self.assertEqual(post('generate',{}),400)
                s.LOCATIONS.operation={'busy':False}
                self.assertEqual(post('model/location',{'target':'image','kind':'download','folder':tmp}),200)
                self.assertEqual(s.MODEL,Path(tmp)/'Qwen-Image-2.1')
            finally:server.shutdown();server.server_close()

if __name__=='__main__':unittest.main()
