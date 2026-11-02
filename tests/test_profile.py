import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from shilu.core import Store
from shilu.curation import skill_context

class ProfileTests(unittest.TestCase):
 def test_real_profile_drift_blocks_candidate_review_export(self):
  with tempfile.TemporaryDirectory() as d:
   f=Path(d)/'profile.md';f.write_text('Rule A')
   with patch.dict(os.environ,{'SHILU_PROFILE_PATH':str(f)}):
    s=Store(Path(d)/'db.sqlite');source=s.register_source(dict(id='s',url='https://example.org/s/',title='Example',date='',occasion='',sections=[dict(anchor='a',text='Actual words.')]))
    p=s.create_curation(dict(title='Example',author='Example'),['s'])
    blocks=[dict(id='b',type='original',text='Actual words.',source_id='s',anchor='a',source_version=source['version'],citation=1)]
    p=s.submit_curation(p['id'],p['revision'],blocks);p=s.adopt_curation(p['id'],p['revision']);p=s.review(p['id'],p['revision'],'Reviewer')
    f.write_text('Rule B')
    self.assertIn('RULES_CHANGED',s.validate_curation(p,blocks)['errors'])
    self.assertIn('RULES_CHANGED',s.validate_curation(p)['errors'])
    for action,args in [(s.review,('Reviewer',)),(s.export,())]:
     with self.assertRaises(ValueError):action(p['id'],p['revision'],*args)
 def test_missing_empty_and_unconfigured(self):
  with patch.dict(os.environ,{},clear=True):self.assertNotIn('profile_version',skill_context())
  with tempfile.TemporaryDirectory() as d:
   f=Path(d)/'missing'
   with patch.dict(os.environ,{'SHILU_PROFILE_PATH':str(f)}):
    with self.assertRaisesRegex(ValueError,'PROFILE_UNAVAILABLE'):skill_context()
    f.write_text(' ')
    with self.assertRaisesRegex(ValueError,'EMPTY_PROFILE'):skill_context()
 def test_protocol_errors_do_not_kill_process(self):
  with tempfile.TemporaryDirectory() as d:
   requests=['{',json.dumps([]),json.dumps(dict(jsonrpc='2.0',id=1,method='initialize',params=[])),json.dumps(dict(jsonrpc='2.0',id=2,method='initialize',params={'protocolVersion':'evil'})),json.dumps(dict(jsonrpc='2.0',id=3,method='tools/call',params={'name':[]})),json.dumps(dict(jsonrpc='2.0',id=4,method='ping'))]
   p=subprocess.run([sys.executable,'-m','shilu.mcp','--data-dir',d],input='\n'.join(requests)+'\n',capture_output=True,text=True,timeout=10)
   self.assertEqual(p.returncode,0);r=[json.loads(x) for x in p.stdout.splitlines()]
   self.assertEqual([x['error']['code'] for x in r[:3]],[-32700,-32600,-32602]);self.assertEqual(r[3]['result']['protocolVersion'],'2025-06-18');self.assertTrue(r[4]['result']['isError']);self.assertEqual(r[5]['result'],{})
