import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from runtime_progress import PipProgress,SOURCES
from runtime_setup import RuntimeInstaller

class ProgressTests(unittest.TestCase):
    def test_file_progress_resets_and_reports_real_speed(self):
        events=[];ticks=iter([10,11,12])
        tracker=PipProgress(lambda stage,**values:events.append(dict(stage=stage,**values)),lambda:next(ticks))
        tracker.feed('  Downloading torch.whl (2 GB)')
        self.assertTrue(tracker.feed('Progress 0 of 2000'))
        tracker.feed('Progress 1000 of 2000')
        self.assertEqual(events[-1]['speed'],1000)
        tracker.feed('Downloading next.whl')
        tracker.feed('Progress 100 of 0')
        self.assertEqual(events[-1]['speed'],0)
        self.assertEqual(events[-1]['total'],0)
        self.assertEqual(events[-1]['file'],'next.whl')

    def test_source_applies_to_packages_but_not_cuda_index(self):
        installer=RuntimeInstaller('.','.','cu128',sys.executable,'tuna');installer.raw_progress=True
        with patch.object(installer,'run_command') as run:
            installer.pip(sys.executable,'install','numpy')
            self.assertIn(SOURCES['tuna'],run.call_args.args[0])
            self.assertIn('raw',run.call_args.args[0])
            installer.pip(sys.executable,'install','torch','--index-url','https://download.pytorch.org/whl/cu128')
            command=run.call_args.args[0]
            self.assertEqual(command.count('--index-url'),1)
            self.assertIn('https://download.pytorch.org/whl/cu128',command)

    def test_streaming_command_emits_progress_and_keeps_errors(self):
        installer=RuntimeInstaller('.','.',current=sys.executable)
        with patch('sys.stdout',new_callable=io.StringIO) as output:
            installer.run_command([sys.executable,'-c','print("Downloading test.whl"); print("Progress 100 of 200"); print("ordinary log")'])
        self.assertIn('"downloaded": 100',output.getvalue())
        self.assertIn('ordinary log',output.getvalue())
        with self.assertRaises(RuntimeError):installer.run_command([sys.executable,'-c','raise SystemExit(2)'])

    def test_unknown_source_is_rejected(self):
        with self.assertRaises(ValueError):RuntimeInstaller('.','.',source='unknown')
