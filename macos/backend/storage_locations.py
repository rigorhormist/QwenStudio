"""User-selected model locations and read-only, local model imports."""
import hashlib
import json
import os
from pathlib import Path
import threading
from io_utils import atomic_json

NAMES={'image':'Qwen-Image-2.1','pe-t2i':'Qwen-Image-2.1-PE-T2I','pe-i2i':'Qwen-Image-2.1-PE-I2I'}
BUSY='请先停止任务和下载，再更改目录。'


def files_for(target):
    if target not in NAMES:raise ValueError('未知模型。')
    name='model' if target=='image' else target
    return json.loads(Path(__file__).with_name(name+'-files.json').read_text(encoding='utf-8'))


def fingerprint(root,files):
    try:
        result=[]
        for entry in files:
            path=root/entry['path'];stat=path.stat()
            if not path.is_file() or stat.st_size!=entry['size']:return None
            result.append([entry['path'],str(path.resolve()),stat.st_size,stat.st_mtime_ns])
        return result
    except OSError:return None


def receipt_path(data,root,target):
    key=hashlib.sha256((str(root.resolve())+'\n'+target).encode()).hexdigest()
    return Path(data)/'model-verifications'/(key+'.json')


def model_ready(root,target,data=None):
    files=files_for(target);current=fingerprint(root,files)
    if current is None:return False
    if (root/'.verified').is_file():return True
    if data is None:return False
    try:
        receipt=json.loads(receipt_path(data,root,target).read_text(encoding='utf-8'))
        return receipt.get('files')==files and receipt.get('fingerprint')==current
    except (OSError,ValueError):return False


def existing_model(folder,target):
    """Bounded search: direct model, named child, or a Hugging Face snapshot."""
    folder=Path(folder).expanduser()
    if not folder.is_absolute() or not folder.is_dir():raise ValueError('目录不可用，请确认硬盘已连接并重新选择。')
    name=NAMES.get(target)
    if not name:raise ValueError('未知模型。')
    roots=[folder,folder/name,folder/('models--Qwen--'+name),folder/'hub'/('models--Qwen--'+name)]
    candidates=[]
    files=files_for(target)
    for root in roots:
        if fingerprint(root,files) is not None:return root.resolve()
        snapshots=root if root.name=='snapshots' else root/'snapshots'
        if snapshots.is_dir():
            candidates.extend(p for p in snapshots.iterdir() if p.is_dir() and fingerprint(p,files) is not None)
    candidates=list(dict.fromkeys(p.resolve() for p in candidates))
    if len(candidates)==1:return candidates[0]
    if len(candidates)>1:raise ValueError('找到多个模型版本，请选择具体的 snapshots 子目录。')
    raise ValueError('未找到完整模型。请选择对应模型目录；若文件尚未下载完成，请将该目录设为下载位置后继续下载。')


def check_download_parent(root):
    # Never recreate a missing removable drive or a user's deleted selected folder.
    if not root.parent.is_dir():raise ValueError('下载目录不可用，请连接硬盘或重新选择目录。')
    root.mkdir(exist_ok=True)


class ModelLocations:
    def __init__(self,data,default,lock=None):
        self.data=Path(data);self.file=self.data/'model-locations.json';self.lock=lock or threading.RLock()
        self.paths={'image':Path(default),**{key:Path(default).parent/name for key,name in NAMES.items() if key!='image'}}
        self.error='';self.operation={'busy':False};self.cancelled=threading.Event()
        try:
            values=json.loads(self.file.read_text(encoding='utf-8'))
            if not isinstance(values,dict):raise ValueError()
            if any(key not in NAMES or not isinstance(value,str) or not Path(value).is_absolute() for key,value in values.items()):raise ValueError()
            self.paths.update({key:Path(value) for key,value in values.items()})
        except FileNotFoundError:pass
        except (OSError,ValueError,TypeError):self.error='模型目录设置无法读取，请重新选择目录。'
        override=os.environ.get('QWEN_STUDIO_MODEL')
        if override:self.paths['image']=Path(override).expanduser()

    def status(self):
        with self.lock:return {'paths':{key:str(value) for key,value in self.paths.items()},'operation':dict(self.operation),'error':self.error,'imageLocked':bool(os.environ.get('QWEN_STUDIO_MODEL'))}

    def save(self,target,path):
        values={**self.paths,target:Path(path)}
        atomic_json(self.file,{key:str(value) for key,value in values.items()})
        self.paths=values;self.error=''

    def select(self,target,folder,kind,activate):
        if target not in NAMES:raise ValueError('未知模型。')
        if target=='image' and os.environ.get('QWEN_STUDIO_MODEL'):raise ValueError('模型目录已由 QWEN_STUDIO_MODEL 指定，请移除该环境变量后再更改。')
        if self.operation.get('busy'):raise ValueError(BUSY)
        path=Path(folder).expanduser()
        if not path.is_absolute() or not path.is_dir():raise ValueError('目录不可用，请确认硬盘已连接并重新选择。')
        if kind=='download':
            # Selecting the model itself resumes it; selecting a parent keeps each model separate.
            if path.name!=NAMES[target] and not any((path/f['path']).is_file() for f in files_for(target)):path=path/NAMES[target]
            self.save(target,path);activate(target,path)
            self.operation={'busy':False,'state':'selected','target':target};return
        if kind!='existing':raise ValueError('未知目录操作。')
        path=existing_model(path,target)
        self.cancelled.clear()
        self.operation={'busy':True,'state':'verifying','target':target,'path':str(path),'bytes':0,'total':sum(f['size'] for f in files_for(target))}
        threading.Thread(target=self._verify,args=(target,path,activate),daemon=True).start()

    def _verify(self,target,path,activate):
        try:
            files=files_for(target);before=fingerprint(path,files)
            if not model_ready(path,target,self.data):
                done=0
                for entry in files:
                    digest=hashlib.sha256()
                    with (path/entry['path']).open('rb') as handle:
                        while chunk:=handle.read(8*1024*1024):
                            if self.cancelled.is_set():raise ValueError('已停止检查，原模型目录保持不变。')
                            digest.update(chunk);done+=len(chunk)
                            with self.lock:self.operation['bytes']=done
                    if digest.hexdigest()!=entry['sha256']:raise ValueError('模型文件校验失败。原目录保持不变；请修复文件后重试。')
                if before is None or before!=fingerprint(path,files):raise ValueError('检查过程中模型文件发生变化，请停止其他下载后重试。')
                receipt=receipt_path(self.data,path,target);receipt.parent.mkdir(exist_ok=True)
                atomic_json(receipt,{'files':files,'fingerprint':before})
            with self.lock:
                if self.cancelled.is_set():raise ValueError('已停止检查，原模型目录保持不变。')
                self.save(target,path);activate(target,path)
                self.operation={'busy':False,'state':'complete','target':target,'path':str(path)}
        except Exception as error:
            with self.lock:self.operation={'busy':False,'state':'error','target':target,'error':str(error)}
