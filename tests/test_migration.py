import sqlite3,tempfile,unittest
from pathlib import Path
from shilu.core import Store
from shilu.migrate_workshop import migrate
class Migration(unittest.TestCase):
 def test_source_unchanged_and_review_reset(self):
  with tempfile.TemporaryDirectory() as d:
   src=Path(d)/'old.sqlite3'
   with sqlite3.connect(src) as db:
    db.execute('CREATE TABLE drafts(id,title,transcript,engine,body,reviewed)')
    db.execute('INSERT INTO drafts VALUES(?,?,?,?,?,?)',('one','虚构分享','足够长的虚构原稿，专供迁移测试使用，不包含真实人物或私有数据。','候选稿','## 人工正文\n原样保留',1))
   before=src.read_bytes();store=Store(Path(d)/'new.sqlite3')
   result=migrate(src,store,'示例')
   p=store.get(result[0]['project_id'])
   self.assertIsNone(p['review']);self.assertEqual(p['human'][0]['body'],'## 人工正文\n原样保留')
   self.assertEqual(p['engine']['sections'][0]['body'],'候选稿')
   self.assertEqual(src.read_bytes(),before)
   self.assertEqual(migrate(src,store,'示例')[0]['status'],'already_imported')
   self.assertEqual(len(store.list()),1)
if __name__=='__main__':unittest.main()
