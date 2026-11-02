import json,tempfile,unittest
from pathlib import Path
from shilu.core import Store
from shilu.archive_superseded import apply
class SupersessionTests(unittest.TestCase):
 def test_archive_preserves_draft_and_is_idempotent(self):
  with tempfile.TemporaryDirectory() as tmp:
   s=Store(Path(tmp)/'db');old={'id':'old','revision':7,'human':['original'],'review':{'signed':'yes'},'source_bundle':['locked']};new=dict(old,id='new')
   with s.connect() as db:
    for p in [old,new,dict(new,id='third')]:db.execute('INSERT INTO projects VALUES(?,?)',(p['id'],json.dumps(p)))
   m={'projects':[dict(old_id='old',new_id='new')]};self.assertEqual(apply(s,m)['updated'],1);self.assertEqual(apply(s,m)['updated'],0)
   self.assertEqual(s.get('old'),dict(old,superseded_by='new'));self.assertEqual(len(s.list()),2);self.assertEqual(len(s.list(include_archived=True)),3)
   with self.assertRaisesRegex(ValueError,'CONFLICT'):apply(s,{'projects':[dict(old_id='old',new_id='third')]})
   self.assertEqual(s.get('old')['superseded_by'],'new')
