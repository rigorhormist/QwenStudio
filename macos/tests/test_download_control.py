import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import download_control

class DownloadControlTest(unittest.TestCase):
    def test_only_matching_downloader_is_stopped_with_children(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'.download.pid').write_text('123')
            parent=Mock();child=Mock();parent.children.return_value=[child]
            script=str(Path(download_control.__file__).with_name('download.py'))
            parent.cmdline.return_value=['python',script,str(root)]
            with patch.object(download_control.psutil,'Process',return_value=parent),patch.object(download_control.psutil,'wait_procs',return_value=([],[])):
                self.assertTrue(download_control.stop_download(root));parent.terminate.assert_called_once();child.terminate.assert_called_once()
                self.assertFalse((root/'.download.pid').exists())
                (root/'.download.pid').write_text('123')
                parent.reset_mock();parent.cmdline.return_value=['python',script,str(root/'unrelated')]
                self.assertFalse(download_control.stop_download(root));parent.terminate.assert_not_called()
                parent.cmdline.return_value=['python','unrelated.py',str(root)]
                self.assertFalse(download_control.stop_download(root));parent.terminate.assert_not_called()
    def test_stop_immediately_after_launch_before_pid_file_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            process=Mock();process.cmdline.return_value=['python',str(Path(download_control.__file__).with_name('download.py')),tmp];process.children.return_value=[]
            known=Mock(pid=123);known.poll.return_value=None
            with patch.object(download_control.psutil,'Process',return_value=process),patch.object(download_control.psutil,'wait_procs',return_value=([],[])):
                self.assertTrue(download_control.stop_download(Path(tmp),known));process.terminate.assert_called_once()
    def test_missing_pid_is_a_noop(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(download_control.psutil,'Process') as process:
            self.assertFalse(download_control.stop_download(Path(tmp)));process.assert_not_called()
