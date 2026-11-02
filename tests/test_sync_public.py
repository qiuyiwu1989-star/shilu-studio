import copy,tempfile,unittest
from pathlib import Path
from shilu.core import Store
from shilu.sync_public import synchronize,freshness
class PublicSyncTests(unittest.TestCase):
 def test_sync_remove_and_rollback(self):
  with tempfile.TemporaryDirectory() as tmp:
   s=Store(Path(tmp)/'db');src=dict(id='one',url='https://example.com/one/',title='One',date='',occasion='',sections=[dict(anchor='a',text='original')]);doc=dict(schema_version=1,sources=[src])
   self.assertEqual(synchronize(s,doc)['added'],['one']);self.assertEqual(synchronize(s,doc)['unchanged'],['one'])
   p=s.create_curation(dict(title='Test',author='Author'),['one']);old=s.get_source('one')
   changed=copy.deepcopy(doc);changed['sources'][0]['sections'][0]['text']='changed'
   r=synchronize(s,changed);self.assertEqual(r['changed'],['one']);self.assertEqual(r['affected_projects'][0]['project_id'],p['id']);self.assertEqual(s.get(p['id']),p)
   before=freshness(s);invalid=copy.deepcopy(changed);invalid['sources'].append(src)
   with self.assertRaises(ValueError):synchronize(s,invalid)
   self.assertEqual(freshness(s),before)
   manual=dict(src,id='manual',url='https://example.com/manual/');s.register_source(manual)
   r=synchronize(s,dict(schema_version=1,sources=[]));self.assertEqual(r['removed'],['one']);self.assertEqual(s.get_source('manual')['id'],'manual');self.assertEqual(s.get_source('one',old['version']),old)
   with self.assertRaises(KeyError):s.get_source('one')
 def test_transaction_rolls_back_url_collision(self):
  with tempfile.TemporaryDirectory() as tmp:
   s=Store(Path(tmp)/'db');src=dict(id='manual',url='https://example.com/',title='T',date='',occasion='',sections=[dict(anchor='a',text='t')]);s.register_source(src)
   with self.assertRaisesRegex(ValueError,'URL_OWNED'):synchronize(s,dict(schema_version=1,sources=[dict(src,id='other')]))
   self.assertEqual(freshness(s)['status'],'never_synced');self.assertEqual(len(s.list_sources()),1)
