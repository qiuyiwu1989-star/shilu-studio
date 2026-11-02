import tempfile,unittest,sqlite3,hashlib,json
from pathlib import Path
import test_curation
from shilu.release import prepare
from shilu.backup import copy_database

class ReleaseTests(unittest.TestCase):
 setUp=test_curation.CurationTests.setUp
 tearDown=test_curation.CurationTests.tearDown
 submit=test_curation.CurationTests.submit
 human=test_curation.CurationTests.human
 def test_release_requires_review_and_binds_artifact(self):
  out=Path(self.tmp.name)/'release'
  with self.assertRaises(ValueError):prepare(self.store,self.p['id'],self.p['revision'],out)
  self.assertFalse(out.exists())
  p=self.human();p=self.store.review(p['id'],p['revision'],'human')
  m=prepare(self.store,p['id'],p['revision'],out)
  self.assertEqual(m['article_sha256'],hashlib.sha256((out/'article.json').read_bytes()).hexdigest())
  self.assertNotIn('rules_hash',json.loads((out/'article.json').read_text()))
 def test_backup_restore_integrity(self):
  root=Path(self.tmp.name);backup=copy_database(root/'shilu.sqlite3',root/'backup.sqlite');restored=copy_database(backup,root/'restore.sqlite')
  with sqlite3.connect(restored) as c:self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0],'ok')
  from shilu.core import Store
  self.assertEqual(Store(restored).get(self.p['id'])['id'],self.p['id'])
  with self.assertRaises(FileExistsError):copy_database(backup,restored)

 def test_stale_source_cannot_release(self):
  p=self.human();p=self.store.review(p['id'],p['revision'],'human')
  import copy
  source=copy.deepcopy(test_curation.SOURCE);source['sections'][0]['text']+='new'
  self.store.register_source(source)
  out=Path(self.tmp.name)/'stale'
  with self.assertRaises(ValueError):prepare(self.store,p['id'],p['revision'],out)
  self.assertFalse(out.exists())
