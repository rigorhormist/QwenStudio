"""Source choice and resume API regression. No network or model download."""
import importlib.util,json,os,sys,tempfile,threading,unittest,urllib.error,urllib.request
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from model_sources import download_url,HF_REVISION

class DownloadSourceTest(unittest.TestCase):
 def test_choice_resume_and_busy_guard(self):
  with tempfile.TemporaryDirectory() as data,patch.dict(os.environ,{'QWEN_STUDIO_DATA':data,'QWEN_STUDIO_TOKEN':'source-test'}):
   spec=importlib.util.spec_from_file_location('source_server',Path(__file__).resolve().parents[1]/'backend/server.py')
   s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
   server=s.ThreadingHTTPServer(('127.0.0.1',0),s.Handler)
   thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
   def request(path,body):
    req=urllib.request.Request(f'http://127.0.0.1:{server.server_port}/api/{path}',data=json.dumps(body).encode(),headers={'X-Studio-Token':'source-test','Content-Type':'application/json'})
    try:
     with urllib.request.urlopen(req) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as error:return error.code,json.load(error)
   s.MODEL.mkdir(parents=True,exist_ok=True)
   partial=s.MODEL/'model_index.json.part';partial.write_bytes(b'resume-me')
   try:
    with patch.object(s.subprocess,'Popen') as launch:
     launch.return_value.poll.return_value=None
     self.assertEqual(request('model/download',{})[0],400)
     self.assertEqual(request('model/download',{'source':'bad'})[0],400)
     launch.assert_not_called()
     self.assertEqual(request('model/download',{'source':'modelscope'})[0],200)
     self.assertEqual(launch.call_args.args[0][-1],'modelscope')
     self.assertEqual(request('model/download',{'source':'huggingface'})[0],400)
     self.assertEqual(request('preferences',{'download_source':'huggingface'})[0],400)
     self.assertEqual(launch.call_count,1)
     launch.return_value.poll.return_value=0
     self.assertEqual(request('model/download',{'source':'huggingface'})[0],200)
     self.assertEqual(launch.call_args.args[0][-1],'huggingface')
     self.assertEqual(s.preferences()['download_source'],'huggingface')
     self.assertEqual(partial.read_bytes(),b'resume-me')
   finally:server.shutdown();server.server_close();thread.join()
 def test_pinned_urls(self):
  item={'path':'vae/config.json','revision':'source-pin'}
  self.assertIn('Revision=source-pin',download_url(item,'modelscope'))
  self.assertEqual(download_url(item,'huggingface'),f'https://huggingface.co/Qwen/Qwen-Image-2.1/resolve/{HF_REVISION}/vae/config.json')
  with self.assertRaises(ValueError):download_url(item,'https://arbitrary.example')

if __name__=='__main__':unittest.main()
