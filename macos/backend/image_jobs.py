"""Prompt rewriting and diffusion run serially, with cancellation between stages."""
import contextlib
import json
import math
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from generation_options import exact_text, protect_text, resolve_size, validate_rewrite


def run_child(worker,config,job,root,data,suffix):
    if job.get('cancel'):raise InterruptedError()
    stem=job['id']+suffix
    inp=data/'jobs'/(stem+'.input.json');out=data/'jobs'/(stem+'.status.json')
    config={**config,'status_path':str(out)}
    inp.write_text(json.dumps(config),encoding='utf-8')
    process=None;result={}
    try:
        with (data/'jobs'/(job['id']+'.log')).open('a',encoding='utf-8') as log:
            process=subprocess.Popen([sys.executable,'-X','utf8',str(root/'backend'/worker),str(inp)],stdout=log,stderr=log,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),env={**os.environ,'PYTHONUTF8':'1',
                    'PYTORCH_ENABLE_MPS_FALLBACK':'1','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false'})
            while True:
                if job.get('cancel'):raise InterruptedError()
                if out.exists():
                    with contextlib.suppress(OSError,ValueError):
                        result=json.loads(out.read_text(encoding='utf-8'));job.update({key:value for key,value in result.items() if key!='rewrite'})
                if process.poll() is not None:break
                time.sleep(.25)
            if out.exists():
                result=json.loads(out.read_text(encoding='utf-8'));job.update({key:value for key,value in result.items() if key!='rewrite'})
            if job.get('cancel'):raise InterruptedError()
            if process.returncode!=0:
                error=result.get('error')
                if not error:
                    with (data/'jobs'/(job['id']+'.log')).open('rb') as stream:
                        stream.seek(max(0,stream.seek(0,2)-16000));tail=stream.read().decode(errors='replace').lower()
                    error='GPU 内存分配失败，图像生成已停止。请关闭其他占用内存的应用后重试，或选择较小的图片尺寸。' if any(key in tail for key in ('failed to allocate mtlbuffer','oversized fused alloc','out of memory')) else '推理进程退出。请在模型设置查看日志。'
                raise RuntimeError(error)
        return result
    finally:
        if process and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:process.kill();process.wait()


def run_image_job(job,payload,root,data,model,enhancers):
    from PIL import Image
    config={**payload,'model_path':str(model),'data':str(data),'job_id':job['id']}
    config['seed']=payload['seed'] if payload['seed']>=0 else secrets.randbelow(2**32)
    rewrite=None;original=payload['prompt'];warning=payload.get('enhancement_warning')
    if payload.get('enhance',True):
        target='pe-i2i' if payload.get('images') else 'pe-t2i'
        if enhancers.status(target)['ready']:
            config['enhancer_path']=str(enhancers.path(target))
            try:
                result=run_child('enhancer_worker.py',config,job,root,data,'.pe')
                rewrite=result.get('rewrite',{})
                validate_rewrite(rewrite,len(payload.get('images',[])))
            except InterruptedError:raise
            except (RuntimeError,ValueError,OSError):
                rewrite=None
                warning='提示词增强未完成，已使用原始提示词生成。'
                # Optional enhancement failures must not redirect the whole app to setup.
                job.pop('error',None);job.pop('environment_error',None)
        else:warning='未下载增强模型，本次使用原始提示词。'
    config['prompt']=rewrite['positive_prompt'] if rewrite else protect_text(original,exact_text(original,payload.get('exact_text','')))
    if warning:job['enhancement_warning']=warning
    sizes=[]
    for name in payload.get('images',[]):
        with Image.open(data/'images'/name) as image:sizes.append(image.size)
    config['width'],config['height']=resolve_size(payload,rewrite,sizes)
    job.update(width=config['width'],height=config['height'],progress=0,stage='正在加载模型')
    result=run_child('worker.py',config,job,root,data,'.image')
    images=result.get('images') or ([result['image']] if result.get('image') else [])
    if not images:raise RuntimeError('没有收到生成图片。')
    meta={key:config.get(key) for key in ('width','height','steps','seed','count','transparent','negative_prompt','cfg','ratio_mode')}
    meta.update(job_id=job['id'],mode='image',seconds=round(time.time()-job['started']),
        enhancement_warning=warning,original_prompt=original,effective_prompt=result.get('effective_prompt',config['prompt']),
        enhanced_prompt=rewrite['positive_prompt'] if rewrite else None,
        enhancer=('PE-I2I' if payload.get('images') else 'PE-T2I') if rewrite else None,
        seeds=result.get('seeds',[config['seed']]),reference_images=payload.get('images',[]))
    return dict(images=images,meta=meta)
