import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from shilu.mcp import recap_context,call
from shilu.core import Store
class RecapProfile(unittest.TestCase):
 def test_profile_snapshot_and_failure(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'private-profile.md';p.write_text('Personal single-event rules')
   with patch.dict(os.environ,{'SHILU_RECAP_PROFILE_PATH':str(p)}):
    c=recap_context();self.assertIn('Personal single-event rules',c['skill']);self.assertNotIn(str(p),str(c));self.assertEqual(len(c['profile_version']),64)
    store=Store(Path(d)/'db.sqlite');project=call(store,'create_recap',{'config':{'title':'Test','author':'Speaker'},'transcript':'An original transcript with sufficient characters.'})
    self.assertEqual(store.get(project['id'])['skill_context']['profile_version'],c['profile_version'])
    p.write_text('')
    with self.assertRaisesRegex(ValueError,'RECAP_PROFILE_UNAVAILABLE'):recap_context()
    p.unlink()
    with self.assertRaises(ValueError) as error:recap_context()
    self.assertNotIn(str(p),str(error.exception))
