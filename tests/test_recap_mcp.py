import tempfile,unittest
from pathlib import Path
from shilu.core import Store,Conflict
from shilu.mcp import call
class RecapMCP(unittest.TestCase):
 def test_candidate_boundary(self):
  with tempfile.TemporaryDirectory() as d:
   s=Store(Path(d)/'test.sqlite');p=call(s,'create_recap',{'config':{'title':'Test','author':'Speaker'},'transcript':'An original transcript with enough detail to retain.'})
   sec=[{'title':'Section','body':'Human text','source_ids':['s1']}]
   p=s.save(p['id'],p['revision'],p['config'],sec);p=s.review(p['id'],p['revision'],'Human')
   rev=p['revision'];review=p['review'];candidate=[dict(sec[0],body='Candidate text')]
   q=call(s,'submit_recap',dict(project_id=p['id'],revision=rev,sections=candidate))
   self.assertEqual(q['human'],sec);self.assertEqual(q['review'],review)
   self.assertEqual(q['engine']['sections'],candidate)
   self.assertFalse(call(s,'validate_recap',{'project_id':p['id']})['release_ready'])
   with self.assertRaises(Conflict):call(s,'submit_recap',dict(project_id=p['id'],revision=rev,sections=candidate))
   with self.assertRaises(ValueError):call(s,'submit_recap',dict(project_id=p['id'],revision=q['revision'],sections=[dict(sec[0],source_ids=['bad'])]))
   self.assertEqual(s.get(p['id'])['revision'],q['revision'])
   with self.assertRaises(ValueError):call(s,'submit_recap',dict(project_id=p['id'],revision=True,sections=candidate))
   self.assertIn('recap',call(s,'get_module_context',{}))
   reopened=Store(Path(d)/'test.sqlite')
   self.assertIn('skill',call(reopened,'get_project',{'project_id':p['id']})['skill_context'])
   second=call(reopened,'submit_recap',dict(project_id=p['id'],revision=q['revision'],sections=sec))
   self.assertEqual(second['candidate_history'][-1]['candidate']['sections'],candidate)
   self.assertEqual(second['human'],sec)
