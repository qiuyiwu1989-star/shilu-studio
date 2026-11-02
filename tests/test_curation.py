import copy,io,json,os,subprocess,sys,tempfile,threading,unittest,zipfile
from pathlib import Path
from urllib.request import Request,urlopen
from unittest.mock import patch
from shilu.core import Store,Conflict,article,scan
from shilu.curation import public_document,skill_context
from shilu.mcp import call,SPECS
from shilu.__main__ import Server

SOURCE={'id':'fictional-talk','url':'https://example.org/talk/','title':'虚构教学分享','date':'2026-01-01','occasion':'虚构评测',
        'sections':[{'anchor':'one','text':'这是完全虚构的教学材料。我们先确认问题，再用真实反馈检验想法。未引用的私有尾句。'}]}
class CurationTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'shilu.sqlite3')
  self.source=self.store.register_source(copy.deepcopy(SOURCE))
  self.p=self.store.create_curation({'title':'虚构专题','author':'示例讲者'},[SOURCE['id']])
  self.blocks=[
   {'id':'h','type':'heading','text':'先确认问题'},
   {'id':'p1','type':'original','text':'我们先确认问题，再用真实反馈检验想法。','source_id':SOURCE['id'],'anchor':'one','source_version':self.source['version'],'citation':1},
   {'id':'bridge','type':'editorial','text':'这给读者提供了一条检查思路。'}]
 def tearDown(self):self.tmp.cleanup()
 def submit(self,p=None,blocks=None):
  p=p or self.p
  return self.store.submit_curation(p['id'],p['revision'],blocks or self.blocks)
 def human(self):
  p=self.submit();return self.store.adopt_curation(p['id'],p['revision'])
 def test_candidate_never_overwrites_human(self):
  p=self.human();old=copy.deepcopy(p['human_blocks'])
  blocks=copy.deepcopy(self.blocks);blocks[-1]['text']='修改后的编辑衔接。'
  p=self.submit(p,blocks)
  self.assertEqual(p['human_blocks'],old)
  self.assertEqual(len(p['candidate_history']),1)
  self.assertNotEqual(p['engine']['blocks'],old)
  p=self.store.adopt_curation(p['id'],p['revision'])
  self.assertEqual(p['history'][0]['blocks'],old)
 def test_review_export_and_invalidation(self):
  p=self.human()
  with self.assertRaises(ValueError):self.store.export(p['id'],p['revision'])
  p=self.store.review(p['id'],p['revision'],'评测人员')
  p=self.store.export(p['id'],p['revision'])
  p=self.store.save_curation(p['id'],p['revision'],p['config'],p['human_blocks'])
  self.assertIsNone(p['review'])
  with self.assertRaises(ValueError):self.store.export(p['id'],p['revision'])
 def test_source_drift_and_historical_source(self):
  p=self.human();p=self.store.review(p['id'],p['revision'],'评测人员')
  changed=copy.deepcopy(SOURCE);changed['sections'][0]['text']+='新增原文'
  self.store.register_source(changed)
  self.assertEqual(self.store.get_source(SOURCE['id'],self.source['version']),self.source)
  report=self.store.validate_curation(p)
  self.assertEqual(report['source_changes'][0]['affected_blocks'],['p1'])
  with self.assertRaises(ValueError):self.store.export(p['id'],p['revision'])
 def test_rules_drift(self):
  p=self.human()
  with patch('shilu.curation.skill_context',return_value={'version':'new'}):
   self.assertIn('RULES_CHANGED',self.store.validate_curation(p)['errors'])
   with self.assertRaises(ValueError):self.store.review(p['id'],p['revision'],'人')
 def test_invalid_quote_anchor_number_rejected(self):
  for key,value in [('text','编造的原话'),('anchor','missing'),('source_version','wrong')]:
   b=copy.deepcopy(self.blocks);b[1][key]=value
   with self.assertRaises(ValueError):self.submit(blocks=b)
  b=copy.deepcopy(self.blocks);extra=dict(b[1],id='p2',citation=2);b.append(extra)
  with self.assertRaises(ValueError):self.submit(blocks=b)
  b=copy.deepcopy(self.blocks);b[-1]['source_id']='fictional-talk'
  with self.assertRaises(ValueError):self.submit(blocks=b)
 def test_conflicts_and_legacy_bypass(self):
  p=self.submit()
  with self.assertRaises(Conflict):self.submit()
  with self.assertRaises(ValueError):self.store.save(p['id'],p['revision'],p['config'],p['engine']['sections'])
  with self.assertRaises(ValueError):self.store.draft(p['id'],p['revision'],'verbatim')
 def test_private_import_and_public_export(self):
  p=self.human();p=self.store.review(p['id'],p['revision'],'私人复核人')
  imported=self.store.create({},'',imported=json.loads(json.dumps(p)))
  self.assertIsNone(imported['review']);self.assertNotEqual(p['id'],imported['id'])
  self.assertEqual(imported['human_blocks'],p['human_blocks'])
  exported=json.dumps(public_document(p),ensure_ascii=False)
  for secret in ['私有尾句','私人复核人','skill_context','source_version']:self.assertNotIn(secret,exported)
  html=article(p);self.assertEqual(html.count('<h2>原文出处</h2>'),1)
  self.assertNotIn('↗',html)
 def test_email_scan(self):
  self.assertTrue(any(x['kind']=='邮箱' for x in scan([{'title':'测试','body':'sample@example.org'}])['flags']))
 def test_mcp_process_shared_database_and_no_review_tools(self):
  proc=subprocess.Popen([sys.executable,'-m','shilu.mcp','--data-dir',self.tmp.name],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
  def rpc(method,params):
   proc.stdin.write(json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params})+'\n');proc.stdin.flush()
   return json.loads(proc.stdout.readline())['result']
  try:
   tools=rpc('tools/list',{})['tools'];self.assertFalse(any('review' in t['name'] or 'export' in t['name'] for t in tools))
   response=rpc('tools/call',{'name':'get_project','arguments':{'project_id':self.p['id']}})
   self.assertEqual(json.loads(response['content'][0]['text'])['skill_context'],skill_context())
   response=rpc('tools/call',{'name':'submit_curation','arguments':{'project_id':self.p['id'],'revision':1,'blocks':self.blocks}})
   self.assertFalse(response.get('isError'))
   self.assertIsNotNone(self.store.get(self.p['id'])['engine'])
  finally:proc.stdin.close();proc.wait(timeout=5);proc.stdout.close()
 def test_http_human_edit_review_zip(self):
  p=self.submit();server=Server(('127.0.0.1',0),self.store)
  thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  def post(action,data):
   req=Request('http://127.0.0.1:%d/api/projects/%s/%s'%(server.server_port,p['id'],action),
      data=json.dumps(data).encode(),headers={'Content-Type':'application/json','X-Shilu-Token':server.token})
   with urlopen(req) as r:return r.read()
  try:
   p=json.loads(post('save-curation',{'revision':p['revision'],'config':p['config'],'blocks':self.blocks}))['project']
   p=json.loads(post('review',{'revision':p['revision'],'reviewer':'人工评测','confirmed':True}))['project']
   result=post('export',{'revision':p['revision']})
   with zipfile.ZipFile(io.BytesIO(result)) as z:
    data=json.loads(z.read('article.json'));self.assertEqual(data['kind'],'curation')
    self.assertNotIn('未引用的私有尾句',z.read('index.html').decode())
  finally:server.shutdown();thread.join();server.server_close()
if __name__=='__main__':unittest.main()
