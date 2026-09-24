"""Non-destructive dependency repair: validate, stage separately, then activate.

Never clear/uninstall the current environment or touch model/user-data files.
A failed or cancelled repair leaves the selected runtime unchanged.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

from io_utils import atomic_json
from runtime_location import runtime_python
from runtime_dependencies import ROOT_REQUIREMENTS

FLAGS=getattr(subprocess,'CREATE_NO_WINDOW',0)


@contextmanager
def installation_lock(root):
    # Keep the lock file; closing its handle releases ownership, even after a crash.
    root.mkdir(parents=True,exist_ok=True)
    with (root/'.install.lock').open('a+b') as handle:
        if handle.tell()==0:handle.write(b'0');handle.flush()
        handle.seek(0)
        if os.name=='nt':
            import msvcrt
            try:msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            except OSError:raise RuntimeError('Another dependency repair is running. Wait for it to finish.')
        else:
            import fcntl
            fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield


class RuntimeInstaller:
    def __init__(self,root,data,cuda='cu130',current=None):
        self.root=Path(root).resolve();self.data=Path(data).resolve()
        self.cuda=cuda;self.current=Path(current) if current else runtime_python(self.root,self.data)

    def run_command(self,arguments,timeout=1800,capture=False):
        result=subprocess.run([str(x) for x in arguments],cwd=self.root,timeout=timeout,
            creationflags=FLAGS,encoding='utf-8',errors='replace',
            stdout=subprocess.PIPE if capture else None,stderr=subprocess.PIPE if capture else None,
            env={**os.environ,'PYTHONUTF8':'1','PYTHONUNBUFFERED':'1','PIP_NO_INPUT':'1','PIP_DISABLE_PIP_VERSION_CHECK':'1','PYTHONDONTWRITEBYTECODE':'1'})
        if result.returncode:
            raise RuntimeError(f'Command failed (exit {result.returncode}). '+((result.stderr or result.stdout or '')[-2000:] if capture else 'See the installation log.'))
        return result.stdout or ''

    def probe(self,python):
        if not Path(python).is_file():return {'ready':False,'items':{}}
        try:
            output=self.run_command([python,'-X','utf8',self.root/'backend/environment_probe.py','--data',self.data,'--summary'],timeout=180,capture=True)
            return json.loads(output.strip().splitlines()[-1])
        except (RuntimeError,OSError,ValueError,subprocess.TimeoutExpired) as error:
            print('Runtime check: '+str(error),flush=True)
            return {'ready':False,'items':{}}

    def pip(self,python,*arguments):
        self.run_command([python,'-m','pip','--disable-pip-version-check','--no-input',*arguments,'--retries','2','--timeout','30'])

    def inherit_packages(self,python):
        # Discover paths using the selected interpreter, not the base interpreter:
        # a user's CUDA wheel may live inside a venv rather than global Python.
        source=self.run_command([self.current,'-X','utf8','-c',
            'import json,sys; print(json.dumps([p for p in sys.path if p.endswith(("site-packages","dist-packages"))]))'],capture=True)
        paths=json.loads(source.strip().splitlines()[-1])
        code='import pathlib,sysconfig; pathlib.Path(sysconfig.get_path("purelib"),"studio-inherited.pth").write_text('+repr('\n'.join(paths)+'\n')+',encoding="utf-8")'
        self.run_command([python,'-I','-X','utf8','-c',code],timeout=30)

    def repair(self):
        print('Checking the existing runtime before making any changes...',flush=True)
        previous=self.probe(self.current)
        if previous.get('ready'):
            print('All required checks passed. Existing CUDA and dependencies kept; nothing to install.',flush=True)
            return self.current
        failures=[v for v in previous.get('items',{}).values() if v.get('required',True) and v.get('state')!='pass']
        wrong_build=any(v['id']=='gpu' and 'PyTorch 不含' in v.get('diagnostic','') for v in failures)
        if failures and not wrong_build and all(v['id'] in ('gpu','storage','curl') for v in failures):
            raise RuntimeError('Python dependencies are available. Repair the GPU driver, storage, or system downloader shown in the check page; reinstalling Python packages will not fix these items.')
        if os.environ.get('QWEN_STUDIO_PYTHON'):
            raise RuntimeError('QWEN_STUDIO_PYTHON selects a custom runtime. It has not been changed. Remove that override to let Qwen Studio create a separate repaired runtime.')
        with installation_lock(self.data/'runtime'):
            candidate=self.data/'runtime'/('env-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8])
            print('Preparing a separate runtime: '+str(candidate),flush=True)
            print('Your current environment, models, sessions and images will be kept.',flush=True)
            base=Path(getattr(sys,'_base_executable',sys.executable))
            self.run_command([base,'-m','venv',candidate],timeout=120)
            python=candidate/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python3')
            # Append the selected runtime's package directories AFTER the candidate's.
            # pip installs repairs into this new prefix and cannot uninstall the source.
            self.inherit_packages(python)
            torch_ready=True
            try:
                gpu=json.loads(self.run_command([python,'-X','utf8',self.root/'backend/environment_probe.py','--check','cuda-stack'],timeout=60,capture=True).strip().splitlines()[-1])
                if not gpu.get('ok'):raise RuntimeError('GPU probe failed')
                print('Existing GPU runtime works. Keeping PyTorch without downloading it again.',flush=True)
            except (RuntimeError,OSError,ValueError,subprocess.TimeoutExpired):
                torch_ready=False
                print('Installing PyTorch into the separate runtime...',flush=True)
                packages=['torch==2.12.0','torchvision==0.27.0'] if sys.platform=='darwin' else ['torch==2.9.0','torchvision==0.24.0']
                index=[] if sys.platform=='darwin' else ['--index-url','https://download.pytorch.org/whl/'+self.cuda]
                self.pip(python,'install','--ignore-installed','--no-deps',*packages,*index)
            broken={item['id'].removeprefix('package:') for item in failures if item['id'].startswith('package:')}
            if previous.get('items',{}).get('pipeline',{}).get('state')!='pass':broken.add('diffusers')
            versions={'PIL':'Pillow'}
            pinned={line.split('==')[0]:line for line in (self.root/'requirements.txt').read_text().splitlines() if '==' in line and not line.startswith('#')}
            diffusion=next(line for line in (self.root/'requirements.txt').read_text().splitlines() if line.startswith('diffusers '))
            for name in sorted(broken-{'torch','torchvision'}):
                package=versions.get(name,name)
                requirement=diffusion if package=='diffusers' else pinned.get(package,pinned.get(package.lower(),package))
                # Reinstall ONLY an import that failed. Healthy packages stay inherited.
                self.pip(python,'install','--ignore-installed','--no-deps',requirement)
            requirements=list(ROOT_REQUIREMENTS)
            if not torch_ready and sys.platform=='win32':
                # The CUDA wheel was installed above; resolving its dependencies uses
                # PyPI without substituting the working CUDA distribution.
                requirements=[value for value in requirements if not value.startswith(('torch>=','torchvision>='))]+packages
            # The resolver repairs only unsatisfied transitive constraints. No global pip check.
            self.pip(python,'install',*requirements)
            print('Validating the repaired runtime before activation...',flush=True)
            final=self.probe(python)
            if not final.get('ready'):
                diagnostics='\n'.join(v['title']+': '+v.get('diagnostic',v.get('detail','')) for v in final.get('items',{}).values() if v.get('required',True) and v.get('state')!='pass')
                raise RuntimeError('The new runtime did not pass validation. The original runtime is still selected.\n'+diagnostics)
            atomic_json(self.data/'runtime-path.json',{'python':python.relative_to(self.data).as_posix()})
            print('Repair complete. The validated runtime is now selected; the previous environment was preserved.',flush=True)
            return python


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--cuda',choices=('cu130','cu128'),default='cu130')
    parser.add_argument('--data',type=Path,required=True)
    parser.add_argument('--python',type=Path,default=Path(sys.executable))
    options=parser.parse_args()
    try:RuntimeInstaller(options.root,options.data,options.cuda,options.python).repair()
    except Exception as error:
        print('Dependency repair stopped: '+str(error),file=sys.stderr,flush=True)
        sys.exit(1)
