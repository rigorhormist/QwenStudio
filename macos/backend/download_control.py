"""Stop only the downloader belonging to the selected model directory."""
from pathlib import Path
import psutil


def stop_download(root,known_process=None):
    root=Path(root)
    try:
        pid=known_process.pid if known_process is not None and known_process.poll() is None else int((root/'.download.pid').read_text(encoding='utf-8'))
        process=psutil.Process(pid)
        args=process.cmdline();script=str(Path(__file__).with_name('download.py'))
        index=args.index(script)
        if Path(args[index+1]).resolve()!=root.resolve():return False
        children=process.children(recursive=True)
        # Stop the parent first so its threads cannot launch new curl processes.
        process.terminate()
        for child in children:
            try:child.terminate()
            except psutil.NoSuchProcess:pass
        _,alive=psutil.wait_procs([process,*children],timeout=3)
        for item in alive:
            try:item.kill()
            except psutil.NoSuchProcess:pass
        _,alive=psutil.wait_procs(alive,timeout=3)
        if alive:raise RuntimeError('下载进程尚未停止，请稍后重试。')
        return True
    except (OSError,ValueError,IndexError,psutil.NoSuchProcess):return False
