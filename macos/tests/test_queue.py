"""Exercise the real serial scheduler with controlled workers; no GPU job required."""
import importlib.util,json,os,sys,tempfile,threading,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
class QueueTest(unittest.TestCase):
 def test_serial_send_cancel_and_history(self):
  with tempfile.TemporaryDirectory() as data:
   os.environ['QWEN_STUDIO_DATA']=data
   spec=importlib.util.spec_from_file_location('queue_server',Path(__file__).resolve().parents[1]/'backend/server.py')
   s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
   with s.connection() as c:c.execute('INSERT INTO sessions VALUES(?,?,?,?)',('s','新会话',0,0))
   s.model_status=lambda:{'ready':True}
   entered=[];gates={};payloads=[]
   def worker(job,payload):
    payloads.append(payload);entered.append(job['id']);gates[job['id']]=threading.Event();gates[job['id']].wait(3)
    job['state']='done'
    with s.LOCK:s.ACTIVE=None;s.advance_queue()
   s.run_job=worker
   def submit(text):return s.start_job(dict(session_id='s',prompt=text,mode='image',width=512,height=512,enhance=True))
   first=submit('first');second=submit('second');third=submit('third')
   self.assertEqual(first['state'],'running');self.assertEqual(second['state'],'queued')
   self.assertEqual(len(entered),1);self.assertFalse(payloads[0]['enhance']);self.assertTrue(first['enhancement_warning']);self.assertEqual(len(s.read_session('s')['messages']),3)
   s.cancel_job(second['id']);self.assertEqual(second['state'],'cancelled')
   gates[first['id']].set()
   for _ in range(100):
    if third['id'] in gates:break
    time.sleep(.01)
   self.assertEqual(entered,[first['id'],third['id']]);self.assertEqual(third['state'],'running')
   gates[third['id']].set()
   for _ in range(100):
    if s.ACTIVE is None:break
    time.sleep(.01)
   self.assertIsNone(s.ACTIVE)
   # Completion timestamps follow queued user timestamps, but history must remain paired.
   with s.connection() as c:c.execute('DELETE FROM messages')
   for jid in ('a','b','c'):s.message('s','user',jid,meta={'job_id':jid})
   s.message('s','assistant','answer a',meta={'job_id':'a'})
   s.message('s','assistant','answer b',meta={'job_id':'b'})
   self.assertEqual([m['content'] for m in s.chat_history('s','c','c')],['a','answer a','b','answer b','c'])
   self.assertEqual([m['content'] for m in s.read_session('s')['messages']],['a','answer a','b','answer b','c'])
   with s.connection() as c:c.execute('DELETE FROM messages')
   s.message('s','user','cancelled prompt',meta={'job_id':'cancel'})
   s.message('s','assistant','已取消排队',meta={'job_id':'cancel','cancelled':True})
   s.message('s','user','failed prompt',meta={'job_id':'fail'})
   s.message('s','assistant','error',meta={'job_id':'fail','error':True})
   self.assertEqual(s.chat_history('s','next','next'),[{'role':'user','content':'next'}])
if __name__=='__main__':unittest.main()
