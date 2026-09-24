"""Contract checks without downloading weights or running model inference."""
import contextlib
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from generation_options import validate_options, exact_text, protect_text, resolve_size, diffusion_kwargs, validate_rewrite, SIZES
from prompt_enhancer import PROFILES, parse_output, messages_for, reference_image
from enhancer_assets import manifest
from image_jobs import run_child, run_image_job
from model_sources import download_url

class GenerationContract(unittest.TestCase):
    def test_official_profiles_and_complete_answer(self):
        self.assertEqual((PROFILES['t2i'].presence_penalty,PROFILES['t2i'].max_new_tokens),(1.5,16256))
        self.assertEqual((PROFILES['edit'].presence_penalty,PROFILES['edit'].max_new_tokens),(0,24000))
        result=parse_output('planning </think>```json\n{"rewrited_prompt":"海报写着：第二次世界大战", "wh_ratio":"3:4"}\n```')
        validate_rewrite(result,0)
        self.assertIn('第二次世界大战',result['positive_prompt'])
        for value in ('unfinished planning', '</think>{"rewritten_prompt":', '</think>{"other":"value"}'):
            with self.assertRaises(ValueError):parse_output(value)
        for result in (dict(parse_ok=False),dict(parse_ok=True,positive_prompt='x',wh_ratio='1:1',ratio_follow='<image1>'),dict(parse_ok=True,positive_prompt='x',ratio_follow='<image3>')):
            with self.assertRaises(ValueError):validate_rewrite(result,2)
    def test_language_and_exact_text_survive(self):
        labels=exact_text('标题“第二次世界大战”，节点 "1939 年"','第二次世界大战\n1945 年')
        self.assertEqual(labels,['第二次世界大战','1945 年','1939 年'])
        prompt=protect_text('生成一张讲解二战历史的流程图',labels)
        self.assertIn('Simplified Chinese',prompt)
        for label in labels:self.assertIn(label,prompt)
    def test_ratios_and_reference_area(self):
        p=dict(width=2048,height=2048,ratio_mode='auto',steps=40)
        for ratio,size in SIZES.items():self.assertEqual(resolve_size(p,{'wh_ratio':ratio}),size)
        self.assertEqual(resolve_size(p,{'ratio_follow':'<image2>'},[(100,100),(1600,900)]),(2720,1536))
        self.assertEqual(resolve_size({**p,'ratio_mode':'fixed'}, {'wh_ratio':'9:16'}),(2048,2048))
        options=diffusion_kwargs({**p,'width':2752,'height':1536},'test')
        self.assertEqual(options['output_resolution'],2056)
        self.assertTrue(options['use_kv_cache']);self.assertEqual(options['true_cfg_scale'],1)
        self.assertNotIn('negative_prompt',options)
    def test_cfg_requires_negative_prompt(self):
        for p in ({'cfg':2},{'negative_prompt':'blur'},{'cfg':float('nan')},{'count':5},{'enhance':'yes'},{'ratio_mode':'reference'}):
            with self.assertRaises(ValueError):validate_options(p)
        p={'negative_prompt':'blurry lettering','cfg':2,'count':4};validate_options(p)
        self.assertEqual(diffusion_kwargs({**p,'width':2048,'height':2048,'steps':40},'x')['negative_prompt'],'blurry lettering')
    def test_reference_order_and_checkpoint_system_prompt(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'system_prompt.txt').write_text('checkpoint-specific')
            messages=messages_for(root,'change only image2',['first','second'])
            self.assertEqual(messages[0]['content'][0]['text'],'checkpoint-specific')
            self.assertEqual([v.get('image') for v in messages[1]['content'][:-1]],['first','second'])
            from PIL import Image
            path=root/'reference.png';Image.new('RGBA',(2400,1200)).save(path)
            image=reference_image(path,1024**2)
            self.assertLessEqual(image.width*image.height,1024**2)
            self.assertAlmostEqual(image.width/image.height,2,places=2)
    def test_download_sources_pin_same_weights(self):
        for target in ('pe-t2i','pe-i2i'):
            files=manifest(target);self.assertTrue(any(f['path']=='system_prompt.txt' for f in files))
            for item in files:
                self.assertEqual(len(item['sha256']),64)
                self.assertIn(item['repo'],download_url(item,'huggingface'))
                self.assertIn(item['hf_revision'],download_url(item,'huggingface'))
                self.assertIn(item['repo'],download_url(item,'modelscope'))
        with self.assertRaises(ValueError):manifest('../escape')
    def test_enhancer_exits_before_diffusion_and_meta_is_traceable(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'images').mkdir();calls=[]
            class Assets:
                def path(self,target):return root/target
                def status(self,target):return {"ready":True}
            def child(worker,config,job,*args):
                calls.append((worker,config.copy()))
                if worker=='enhancer_worker.py':return {'rewrite':dict(parse_ok=True,positive_prompt='A chart reading 第二次世界大战',wh_ratio='9:16')}
                return {'images':['a.png','b.png'],'seeds':[42,43],'effective_prompt':config['prompt']}
            p=dict(mode='image',prompt='生成一张讲解二战历史的流程图',width=2048,height=2048,steps=40,seed=42,enhance=True,ratio_mode='auto',images=[],count=2)
            with patch('image_jobs.run_child',child):result=run_image_job({'id':'test','started':time.time()},p,root,root,root,Assets())
            self.assertEqual([c[0] for c in calls],['enhancer_worker.py','worker.py'])
            self.assertEqual((calls[1][1]['width'],calls[1][1]['height']),(1536,2752))
            self.assertEqual(result['meta']['original_prompt'],p['prompt'])
            self.assertEqual(result['meta']['seeds'],[42,43])
            with patch('image_jobs.run_child',side_effect=[{'rewrite':{}},{'images':['fallback.png']}]) as run:
                fallback=run_image_job({'id':'test','started':time.time()},p,root,root,root,Assets())
                self.assertEqual(run.call_count,2)
                self.assertIsNone(fallback['meta']['enhancer'])
                self.assertIn(p['prompt'],fallback['meta']['effective_prompt'])
                self.assertTrue(fallback['meta']['enhancement_warning'])
    def test_missing_optional_weights_skip_enhancer_and_keep_references(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'images').mkdir();Image.new('RGB',(100,200)).save(root/'images/ref.png')
            class MissingAssets:
                def status(self,target):return {'ready':False}
                def path(self,target):raise AssertionError('Missing weights must not be opened')
            for refs in ([],['ref.png']):
                p=dict(prompt='标题“历史”',exact_text='1939 年',width=1024,height=1024,steps=40,seed=42,enhance=True,ratio_mode='fixed',images=refs)
                with patch('image_jobs.run_child',return_value={'images':['done.png']}) as worker:
                    result=run_image_job({'id':'test','started':time.time()},p,root,root,root,MissingAssets())
                worker.assert_called_once();self.assertEqual(worker.call_args.args[0],'worker.py')
                config=worker.call_args.args[1];self.assertEqual(config['images'],refs)
                self.assertIn('1939 年',config['prompt']);self.assertIn('历史',config['prompt'])
                self.assertIsNone(result['meta']['enhancer']);self.assertTrue(result['meta']['enhancement_warning'])

    def test_process_final_packet_and_cancel_boundary(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'backend').mkdir();(root/'jobs').mkdir()
            (root/'backend/fake.py').write_text('import json,sys;from pathlib import Path;p=json.loads(Path(sys.argv[1]).read_text());Path(p["status_path"]).write_text(json.dumps({"answer":"complete"}))')
            job={'id':'sample'}
            self.assertEqual(run_child('fake.py',{},job,root,root,'.test')['answer'],'complete')
            with self.assertRaises(InterruptedError):run_child('fake.py',{},dict(id='cancelled',cancel=True),root,root,'.test')
            self.assertFalse((root/'jobs/cancelled.test.input.json').exists())

if __name__=='__main__':unittest.main()
