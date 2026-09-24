"""Pinned PE weights use the same verified, resumable downloader as image weights."""
import json
import os
import psutil
from pathlib import Path
import subprocess
import threading
import time
from model_sources import SOURCES, validate_source
from download_control import stop_download
from storage_locations import model_ready, check_download_parent

TARGETS={'pe-t2i':'Qwen-Image-2.1-PE-T2I','pe-i2i':'Qwen-Image-2.1-PE-I2I'}

def manifest(target):
    if target not in TARGETS:raise ValueError('未知模型。')
    return json.loads(Path(__file__).with_name(target+'-files.json').read_text(encoding='utf-8'))

def ready(root,target,data=None):
    return model_ready(root,target,data)

class EnhancerAssets:
    def __init__(self,model_parent,data):
        self.paths={};self.parent=Path(model_parent);self.data=Path(data);self.processes={};self.samples={};self.lock=threading.RLock()
    def path(self,target):
        if target not in TARGETS:raise ValueError('未知模型。')
        return self.paths.get(target,self.parent/TARGETS[target])
    def status(self,target):
        with self.lock:
            root=self.path(target);files=manifest(target);total=sum(f['size'] for f in files)
            done=sum(min((root/f['path']).stat().st_size,f['size']) for f in files if (root/f['path']).is_file())
            partial=sum(f.stat().st_size for f in root.rglob('*') if f.is_file() and ('.chunk-' in f.name or f.name.endswith('.part') or f.name.endswith('.receiving')))
            process=self.processes.get(target);running=process is not None and process.poll() is None
            try:
                candidate=psutil.Process(int((root/'.download.pid').read_text(encoding='utf-8')))
                running=running or (str(Path(__file__).with_name('download.py')) in candidate.cmdline())
            except (OSError,ValueError,psutil.Error):pass
            current=min(total,done+partial);now=time.monotonic();samples=self.samples.setdefault(target,[]);samples.append((now,current))
            while len(samples)>1 and samples[0][0]<now-15:samples.pop(0)
            elapsed=now-samples[0][0];speed=max(0,(current-samples[0][1])/elapsed) if elapsed>1 else 0
            is_ready=ready(root,target,self.data)
            return dict(path=str(root),ready=is_ready,bytes=current,total=total,speed=speed,downloading=running,verifying=running and current>=total and not is_ready,error='下载中断，请继续下载。' if not running and process is not None and process.poll() not in (None,0) else '',sources=SOURCES)
    def start(self,target,source):
        validate_source(source)
        with self.lock:
            current=self.status(target)
            if current['ready']:return current
            if current['downloading']:
                if (self.path(target)/'.download-source').read_text(encoding='utf-8').strip()!=source:raise ValueError('已有下载任务正在运行，请勿同时切换下载源。')
                return current
            root=self.path(target);check_download_parent(root);self.samples[target]=[];(root/'.download-source').write_text(source, encoding='utf-8')
            with (self.data/(target+'-download.log')).open('a') as log:
                self.processes[target]=subprocess.Popen([os.sys.executable,'-X','utf8',str(Path(__file__).with_name('download.py')),str(root),source,target],stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            return self.status(target)
    def stop(self):
        for target in TARGETS:stop_download(self.path(target),self.processes.get(target))
