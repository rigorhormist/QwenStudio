"""Loopback-only desktop backend. No model code executes in the HTTP process."""
import argparse, base64, contextlib, json, mimetypes, os, secrets, signal, sqlite3, subprocess, sys, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote
from urllib.request import Request, build_opener, ProxyHandler
import psutil
from model_sources import SOURCES, validate_source
from environment_probe import is_environment_error
from enhancer_assets import EnhancerAssets, TARGETS
from generation_options import validate_options, resolve_size, exact_text, protect_text
from image_jobs import run_image_job
from studio_paths import data_path, model_path

ROOT = Path(__file__).resolve().parent.parent
DATA = data_path()
MODEL = model_path(DATA)
CREATE_FLAGS = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
LOCAL_HTTP = build_opener(ProxyHandler({}))
for p in [DATA, DATA/'images', DATA/'jobs', MODEL]: p.mkdir(parents=True, exist_ok=True)
TOKEN = os.environ.get('QWEN_STUDIO_TOKEN') or secrets.token_urlsafe(32)
DB = DATA/'sessions.sqlite3'
LOCK = threading.RLock()
JOBS = {}
DOWNLOAD_SAMPLES = []
CHAT_CAPS = {}
ACTIVE = None
QUEUE = []
STOPPING = False
DOWNLOAD = None
ENHANCERS = EnhancerAssets(MODEL.parent, DATA)
REVISION = 'b3179ad355be050328e483a9dfdd9e60cd62adfa'

@contextlib.contextmanager
def connection():
    c = sqlite3.connect(DB,timeout=15); c.row_factory = sqlite3.Row
    try:
        with c: yield c
    finally: c.close()
with connection() as c:
    c.executescript('CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,title TEXT,created REAL,updated REAL); CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY,session_id TEXT,role TEXT,content TEXT,images TEXT,meta TEXT,created REAL);')
    c.execute('CREATE TABLE IF NOT EXISTS preferences(key TEXT PRIMARY KEY,value TEXT)')

def preferences(values=None):
    defaults={'welcome_language':'zh','welcome_cycle':True,'download_source':None,'interface_language':'auto'}
    with connection() as c:
        if values is not None:
            if not isinstance(values,dict) or set(values)-set(defaults): raise ValueError('未知设置。')
            if 'welcome_language' in values and values['welcome_language'] not in ('auto','zh','en'): raise ValueError('不支持的语言。')
            if 'interface_language' in values and values['interface_language'] not in ('auto','zh','en'): raise ValueError('不支持的语言。')
            if 'welcome_cycle' in values and not isinstance(values['welcome_cycle'],bool): raise ValueError('轮换设置须为开关。')
            if 'download_source' in values: validate_source(values['download_source'])
            for key,value in values.items(): c.execute('INSERT OR REPLACE INTO preferences VALUES(?,?)',(key,json.dumps(value)))
        for row in c.execute('SELECT key,value FROM preferences'):
            if row['key'] in defaults: defaults[row['key']]=json.loads(row['value'])
    language_file=DATA/'ui-language.txt'
    if values and 'interface_language' in values:
        temporary=DATA/('ui-language-'+uuid.uuid4().hex+'.tmp')
        try:
            temporary.write_text(values['interface_language'],encoding='utf-8')
            temporary.replace(language_file)
        finally:
            temporary.unlink(missing_ok=True)
    if language_file.exists():
        chosen=language_file.read_text(encoding='utf-8-sig').strip()
        if chosen in ('auto','zh','en'):defaults['interface_language']=chosen
    return defaults

def read_session(sid):
    with connection() as c:
        s=c.execute('SELECT * FROM sessions WHERE id=?',(sid,)).fetchone()
        if not s: raise ValueError('找不到这个会话。')
        d=dict(s);d['messages']=[dict(x) for x in c.execute('SELECT * FROM messages WHERE session_id=? ORDER BY created',(sid,))]
    for m in d['messages']:
        m['images']=json.loads(m['images']);m['meta']=json.loads(m['meta'])
    # Pair queued prompts with their eventual result before ordering the conversation.
    users={m['meta']['job_id']:m for m in d['messages'] if m['role']=='user' and m['meta'].get('job_id')}
    unmatched=[]
    for m in d['messages']:
        jid=m['meta'].get('job_id')
        if m['role']=='user' and jid:unmatched.append(jid)
        elif m['role']=='assistant':
            if not jid and unmatched:
                # Compatibility with the first queue build, which omitted result job IDs.
                jid=unmatched[0];m['meta']['job_id']=jid
            if jid in unmatched:unmatched.remove(jid)
    d['messages'].sort(key=lambda m:(users.get(m['meta'].get('job_id'),m)['created'],m['role']!='user',m['created']))
    return d

def chat_history(sid,current_id,prompt):
    history=read_session(sid)['messages']
    completed={m['meta'].get('job_id') for m in history if m['role']=='assistant' and not m['meta'].get('error') and not m['meta'].get('cancelled')}
    result=[]
    for m in history:
        meta=m['meta'];jid=meta.get('job_id')
        if meta.get('error') or meta.get('cancelled') or jid==current_id:continue
        if jid and jid not in completed:continue
        result.append({'role':m['role'],'content':m['content']})
    return result[-24:]+[{'role':'user','content':prompt}]

def message(sid,role,content,images=None,meta=None):
    with connection() as c:
        c.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?)',(uuid.uuid4().hex,sid,role,content,json.dumps(images or []),json.dumps(meta or {}),time.time()))
        c.execute('UPDATE sessions SET updated=? WHERE id=?',(time.time(),sid))

def ollama(path, body=None, timeout=10):
    data=json.dumps(body).encode() if body is not None else None
    req=Request('http://127.0.0.1:11434'+path,data=data,headers={'Content-Type':'application/json'})
    return LOCAL_HTTP.open(req,timeout=timeout)

def model_status():
    manifest=ROOT/'backend/model-files.json'
    files=json.loads(manifest.read_text(encoding='utf-8'))
    total=sum(x['size'] for x in files)
    done=sum(min((MODEL/x['path']).stat().st_size,x['size']) for x in files if (MODEL/x['path']).is_file())
    partial=sum(x.stat().st_size for x in MODEL.rglob('*') if x.is_file() and (x.name.endswith('.part') or '.chunk-' in x.name or x.name.endswith('.receiving')))
    ready=(MODEL/'.verified').is_file() and all((MODEL/x['path']).is_file() and (MODEL/x['path']).stat().st_size==x['size'] for x in files)
    running=DOWNLOAD is not None and DOWNLOAD.poll() is None
    try:
        pid=int((MODEL/'.download.pid').read_text(encoding='utf-8'))
        process=psutil.Process(pid)
        running=running or any(str(ROOT/'backend/download.py') == arg for arg in process.cmdline())
    except (OSError,ValueError,psutil.Error): pass
    log=DATA/'download.log'
    error=''
    if not running and DOWNLOAD is not None and DOWNLOAD.poll() not in (None,0):
        error='下载中断。点击继续下载可重试；已完成的分段会保留。详情见本地目录的 download.log。'
    current=min(done+partial,total)
    with LOCK:
        now=time.monotonic()
        DOWNLOAD_SAMPLES.append((now,current))
        while len(DOWNLOAD_SAMPLES)>1 and DOWNLOAD_SAMPLES[0][0]<now-15: DOWNLOAD_SAMPLES.pop(0)
        elapsed=now-DOWNLOAD_SAMPLES[0][0]
        speed=max(0,(current-DOWNLOAD_SAMPLES[0][1])/elapsed) if elapsed>1 else 0
    eta=(total-current)/speed if speed>1024 and not ready else None
    source=preferences()['download_source']
    if running:
        try: source=validate_source((MODEL/'.download-source').read_text(encoding='utf-8').strip())
        except (OSError,ValueError): source='modelscope'
    return {'source':source,'sources':SOURCES,'ready':ready,'downloading':running,'bytes':current,'total':total,'speed':speed,'eta':eta,'verifying':current>=total and not ready and running,'path':str(MODEL),'error':error}

def chat_capabilities(name):
    if name in CHAT_CAPS:return CHAT_CAPS[name]
    try:
        with ollama('/api/show',{'model':name}) as r: info=json.load(r)
        options=[]
        if 'thinking' in info.get('capabilities',[]):
            if info.get('details',{}).get('family')=='gptoss':
                options=[{'value':'low','label':'轻度'},{'value':'medium','label':'标准'},{'value':'high','label':'深入'}]
            else: options=[{'value':True,'label':'开启'},{'value':False,'label':'关闭'}]
        CHAT_CAPS[name]={'options':options}
        return CHAT_CAPS[name]
    except Exception:return {'options':[]}

def status():
    try:
        with ollama('/api/tags') as r: models=json.load(r)['models']
        models=[x['name'] for x in models if 'embedding' not in x['name'] and 'ocr' not in x['name'] and 'cloud' not in x['name']]
        connected=True
    except Exception: models=[];connected=False
    with LOCK: active=JOBS.get(ACTIVE)
    return {'model':model_status(),'enhancers':{key:ENHANCERS.status(key) for key in TARGETS},'ollama':connected,'chat_models':models,'chat_capabilities':{name:chat_capabilities(name) for name in models},'active':active,'pending':[JOBS[jid] for jid,_ in QUEUE],'data':str(DATA)}

def run_job(job, payload):
    global ACTIVE
    sid=job['session_id'];proc=None
    try:
        if payload['mode']=='chat':
            job.update(stage='正在思考',progress=None)
            messages=[{'role':'system','content':'You are a creative assistant. Reply in the user’s language. Help discuss ideas, compose scenes and write image prompts. You have no image tools. Never claim to have generated or edited images. Explain that the user can switch to Image mode to create them.'}]
            messages += chat_history(sid,job['id'],payload['prompt'])
            inp=DATA/'jobs'/f"{job['id']}.input.json";out=DATA/'jobs'/f"{job['id']}.status.json"
            inp.write_text(json.dumps({'history':messages,'chat_model':payload['chat_model'],'think':payload.get('think'),'status_path':str(out)}), encoding='utf-8')
            with (DATA/'jobs'/f"{job['id']}.log").open('w') as log:
                proc=subprocess.Popen([sys.executable,'-X','utf8',str(ROOT/'backend/chat_worker.py'),str(inp)],stdout=log,stderr=log,creationflags=CREATE_FLAGS)
                while proc.poll() is None:
                    if job.get('cancel'):
                        proc.terminate()
                        try: proc.wait(timeout=5)
                        except subprocess.TimeoutExpired: proc.kill();proc.wait()
                        raise InterruptedError()
                    if out.exists():
                        with contextlib.suppress(Exception): job.update(json.loads(out.read_text(encoding='utf-8')))
                    time.sleep(.2)
            if out.exists(): job.update(json.loads(out.read_text(encoding='utf-8')))
            if proc.returncode!=0: raise RuntimeError(job.get('error') or '聊天进程退出，请重试。')
            message(sid,'assistant',job['text'],meta={'job_id':job['id'],'mode':'chat','model':payload['chat_model'],'think':payload.get('think')})
        else:
            # Release Ollama's idle model weights before the image model claims unified memory.
            try:
                with ollama('/api/ps') as r: loaded=json.load(r).get('models',[])
                for m in loaded:
                    with ollama('/api/generate',{'model':m['name'],'keep_alive':0},timeout=30) as r: r.read()
            except Exception: pass
            result=run_image_job(job,payload,ROOT,DATA,MODEL,ENHANCERS)
            message(sid,'assistant','图片已生成。',result['images'],result['meta'])
        job.update(state='done',stage='完成',progress=1)
    except InterruptedError:
        job.update(state='cancelled',stage='已停止')
        message(sid,'assistant','已停止本次任务。',meta={'cancelled':True,'job_id':job['id']})
    except Exception as e:
        diagnostic=str(e)
        log_path=DATA/'jobs'/f"{job['id']}.log"
        with contextlib.suppress(OSError):
            with log_path.open('rb') as stream:
                stream.seek(max(0,log_path.stat().st_size-16000));diagnostic+='\n'+stream.read().decode(errors='replace')
        job.update(state='error',stage='任务失败',error=str(e),environment_error=is_environment_error(diagnostic))
        message(sid,'assistant',str(e),meta={'error':True,'job_id':job['id']})
        if job.get('environment_error'):
            # A broken runtime cannot execute queued work. Keep every prompt in
            # its chat, with an explicit result, instead of repeatedly failing.
            with LOCK:
                for queued_id,_ in QUEUE:
                    queued=JOBS[queued_id];queued.update(state='cancelled',stage='已停止')
                    message(queued['session_id'],'assistant','环境缺失，排队任务已停止。',meta={'cancelled':True,'job_id':queued_id})
                QUEUE.clear()
    finally:
        if proc and proc.poll() is None: proc.kill()
        with LOCK:
            ACTIVE=None
            advance_queue()

def advance_queue():
    global ACTIVE
    if ACTIVE or STOPPING or not QUEUE:return
    jid,payload=QUEUE.pop(0)
    job=JOBS[jid];ACTIVE=jid
    job.update(state='running',stage='准备中',started=time.time())
    threading.Thread(target=run_job,args=(job,payload),daemon=True).start()

def cancel_job(jid):
    with LOCK:
        job=JOBS.get(jid)
        if not job:return
        if job['state']=='queued':
            QUEUE[:]=[(key,p) for key,p in QUEUE if key!=jid]
            job.update(state='cancelled',stage='已取消排队')
            message(job['session_id'],'assistant','已取消排队。',meta={'cancelled':True,'job_id':job['id']})
        elif job['state']=='running':job.update(cancel=True,stage='正在停止')

def start_job(p):
    global ACTIVE
    prompt=str(p.get('prompt','')).strip()
    if not prompt or len(prompt)>16000: raise ValueError('请输入 1–16000 字的内容。')
    if p.get('mode') not in ('chat','image'): raise ValueError('未知模式。')
    read_session(p['session_id'])
    refs=p.get('images',[])
    if not isinstance(refs,list) or len(refs)>10: raise ValueError('最多使用 10 张参考图。')
    for name in refs:
        if Path(name).name!=name or not (DATA/'images'/name).is_file(): raise ValueError('参考图不存在，请重新添加。')
    if p['mode']=='image':
        if not model_status()['ready']: raise ValueError('模型还未下载完成。请在“模型设置”中下载或查看进度。')
        for key in ['width','height']:
            p[key]=int(p.get(key,2048))
            if p[key]<256 or p[key]>2752 or p[key]%32: raise ValueError('图片尺寸须为 256–2752 之间的 32 的倍数。')
        if p['width']*p['height']>4_300_800: raise ValueError('图片总像素暂不超过约 430 万，请选择支持的 2K 尺寸。')
        p['steps']=int(p.get('steps',40))
        if not 1<=p['steps']<=60: raise ValueError('步数须为 1–60。')
        p['seed']=int(p.get('seed',-1))
        if p['seed'] < -1 or p['seed']>2**32-1: raise ValueError('种子须为 -1 或 0–4294967295。')
        p.setdefault('enhance',True);p.setdefault('ratio_mode','auto')
        validate_options(p)
        target='pe-i2i' if refs else 'pe-t2i'
        if p['enhance'] and not ENHANCERS.status(target)['ready']:
            p['enhance']=False
            p['enhancement_warning']='未下载增强模型，本次使用原始提示词。'
    else:
        if refs: raise ValueError('参考图用于“图像”模式，请先切换模式。')
        with ollama('/api/tags') as r: available=[m['name'] for m in json.load(r)['models']]
        if p.get('chat_model') not in available or 'cloud' in p['chat_model']: raise ValueError('请选择已安装的本地聊天模型。')
        opts=chat_capabilities(p['chat_model'])['options']
        chosen=p.get('think')
        if chosen is None and opts: chosen='medium' if any(o['value']=='medium' for o in opts) else opts[0]['value']
        if chosen is not None and not any(type(o['value']) is type(chosen) and o['value']==chosen for o in opts): raise ValueError('这个模型不支持所选思考设置。')
        p['think']=chosen
    with LOCK:
        if STOPPING: raise ValueError('应用正在关闭，请重新打开后发送。')
        if len(QUEUE)>=10: raise ValueError('已有 10 条消息排队，请稍后再发送。')
        jid=uuid.uuid4().hex
        job={'id':jid,'session_id':p['session_id'],'state':'queued','stage':'等待前一个任务完成','progress':0,'text':'','started':time.time(),'mode':p['mode']}
        if p['mode']=='image': job.update(width=p['width'],height=p['height'],enhancement_warning=p.get('enhancement_warning'))
        JOBS[jid]=job
        p['prompt']=prompt
        message(p['session_id'],'user',prompt,refs,{'mode':p['mode'],'job_id':jid})
        with connection() as c:
            c.execute("UPDATE sessions SET title=? WHERE id=? AND title IN ('新会话','New chat')",(prompt[:28],p['session_id']))
        QUEUE.append((jid,p.copy()))
        advance_queue()
    return job

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def send_json(self,data,code=200):
        raw=json.dumps(data,ensure_ascii=False).encode();self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
    def authorized(self):
        host=self.headers.get('Host','').split(':')[0]
        if host not in ('127.0.0.1','localhost'): return False
        if self.path.startswith('/api/'):
            return secrets.compare_digest(self.headers.get('X-Studio-Token',''),TOKEN)
        return True
    def do_GET(self):
        if not self.authorized(): return self.send_json({'error':'Unauthorized'},403)
        path=unquote(urlparse(self.path).path)
        try:
            if path=='/api/status': return self.send_json(status())
            if path=='/api/health': return self.send_json({'service':'qwen-studio','version':'2.2.3-windows','pid':os.getpid()})
            if path=='/api/preferences': return self.send_json(preferences())
            if path=='/api/sessions':
                with connection() as c: return self.send_json([dict(x) for x in c.execute('SELECT * FROM sessions ORDER BY updated DESC')])
            if path.startswith('/api/sessions/'): return self.send_json(read_session(path.split('/')[-1]))
            if path.startswith('/api/jobs/'):
                j=JOBS.get(path.split('/')[-1])
                if not j: raise ValueError('任务已结束或程序已重启。')
                return self.send_json(j)
            if path=='/api/gallery':
                with connection() as c: rows=c.execute("SELECT images,meta,created FROM messages WHERE role='assistant' ORDER BY created DESC").fetchall()
                return self.send_json([{'image':im,'meta':json.loads(r['meta']),'created':r['created']} for r in rows for im in json.loads(r['images'])])
            if path.startswith('/media/'):
                name=path.removeprefix('/media/')
                if Path(name).name!=name: raise ValueError('Invalid path')
                f=DATA/'images'/name
            else:
                rel='index.html' if path=='/' else path.lstrip('/')
                f=(ROOT/'web'/rel).resolve()
                if not f.is_relative_to((ROOT/'web').resolve()): raise ValueError('Invalid path')
            if not f.is_file(): return self.send_json({'error':'Not found'},404)
            raw=f.read_bytes()
            if f.name=='index.html': raw=raw.replace(b'__STUDIO_TOKEN__',TOKEN.encode()).replace(b'__STUDIO_LANGUAGE__',preferences()['interface_language'].encode())
            self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(str(f))[0] or 'application/octet-stream');self.send_header('Content-Length',str(len(raw)));self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store');self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data: blob:; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'");self.end_headers();self.wfile.write(raw)
        except (ValueError,KeyError) as e: self.send_json({'error':str(e),'environment_error':is_environment_error(e)},400)
        except Exception as e: self.send_json({'error':str(e),'environment_error':is_environment_error(e)},500)
    def do_POST(self):
        global DOWNLOAD
        if not self.authorized(): return self.send_json({'error':'Unauthorized'},403)
        try:
            length=int(self.headers.get('Content-Length',0))
            if length>30*1024*1024: raise ValueError('文件过大，请使用小于 20 MB 的图片。')
            p=json.loads(self.rfile.read(length) or '{}');path=urlparse(self.path).path
            if path=='/api/shutdown':
                self.send_json({'ok':True})
                threading.Thread(target=stop,daemon=True).start()
                return
            if path=='/api/preferences':
                with LOCK:
                    if 'download_source' in p and (model_status()['downloading'] or any(ENHANCERS.status(key)['downloading'] for key in TARGETS)): raise ValueError('下载进行中，完成或中断后可更改下载源。')
                    return self.send_json(preferences(p))
            if path=='/api/sessions':
                sid=uuid.uuid4().hex
                with connection() as c: c.execute('INSERT INTO sessions VALUES(?,?,?,?)',(sid,'New chat' if self.headers.get('X-Studio-Language')=='en' else '新会话',time.time(),time.time()))
                return self.send_json(read_session(sid))
            if path=='/api/session/delete':
                with LOCK:
                    if any(j['session_id']==p['id'] and j['state'] in ('running','queued') for j in JOBS.values()): raise ValueError('请先停止这个会话中的任务。')
                    with connection() as c:
                        c.execute('DELETE FROM messages WHERE session_id=?',(p['id'],));c.execute('DELETE FROM sessions WHERE id=?',(p['id'],))
                return self.send_json({'ok':True})
            if path=='/api/session/rename':
                title=str(p['title']).strip()[:80]
                if not title: raise ValueError('名称不能为空。')
                with connection() as c: c.execute('UPDATE sessions SET title=? WHERE id=?',(title,p['id']))
                return self.send_json({'ok':True})
            if path=='/api/upload':
                from PIL import Image, ImageOps
                import io
                raw=base64.b64decode(p['data'],validate=True)
                if len(raw)>20*1024*1024: raise ValueError('图片应小于 20 MB。')
                im=Image.open(io.BytesIO(raw))
                if im.width*im.height>25_000_000: raise ValueError('图片请限制在 2500 万像素以内。')
                im.load();im=ImageOps.exif_transpose(im)
                im=im.convert('RGBA' if 'A' in im.getbands() or 'transparency' in im.info else 'RGB')
                name=uuid.uuid4().hex+'.png';im.save(DATA/'images'/name)
                return self.send_json({'image':name})
            if path=='/api/generate': return self.send_json(start_job(p))
            if path=='/api/cancel':
                cancel_job(p['id'])
                return self.send_json({'ok':True})
            if path=='/api/model/download':
                with LOCK:
                    target=p.get('target','image')
                    if target!='image':
                        source=validate_source(p.get('source') or preferences()['download_source'])
                        current=ENHANCERS.start(target,source)
                        preferences({'download_source':source})
                        return self.send_json(current)
                    current=model_status()
                    if current['ready']: return self.send_json(current)
                    source=validate_source(p.get('source') or preferences()['download_source'])
                    if current['downloading']:
                        if source!=current['source']: raise ValueError('已有下载任务正在运行，请勿同时切换下载源。')
                    else:
                        preferences({'download_source':source})
                        DOWNLOAD_SAMPLES.clear()
                        (MODEL/'.download-source').write_text(source, encoding='utf-8')
                        log=(DATA/'download.log').open('a')
                        DOWNLOAD=subprocess.Popen([sys.executable,'-X','utf8',str(ROOT/'backend/download.py'),str(MODEL),source],stdout=log,stderr=log,creationflags=CREATE_FLAGS)
                        log.close()
                return self.send_json(model_status())
            return self.send_json({'error':'Not found'},404)
        except (ValueError,KeyError,TypeError) as e: self.send_json({'error':str(e),'environment_error':is_environment_error(e)},400)
        except Exception as e: self.send_json({'error':str(e),'environment_error':is_environment_error(e)},500)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=0);args=parser.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print(json.dumps({'port':server.server_port,'pid':os.getpid()}),flush=True)
    def stop(*_):
        global STOPPING
        with LOCK:
            STOPPING=True
            for jid,_payload in QUEUE[:]:cancel_job(jid)
            if ACTIVE: JOBS[ACTIVE]['cancel']=True
        if DOWNLOAD and DOWNLOAD.poll() is None:
            DOWNLOAD.terminate()
        ENHANCERS.stop()
        threading.Thread(target=server.shutdown,daemon=True).start()
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    server.serve_forever()
    deadline=time.time()+10
    while ACTIVE and time.time()<deadline: time.sleep(.2)
