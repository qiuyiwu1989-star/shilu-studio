import importlib.util,json,tempfile,unittest
from pathlib import Path
from shilu.core import Store
spec=importlib.util.spec_from_file_location('migration',Path(__file__).parents[1]/'scripts/migrate_curated_candidates.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class MigrationTests(unittest.TestCase):
 def test_idempotent_preserves_candidate_and_rejects_changed_source_document(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);store=Store(root/'db.sqlite');folder=root/'articles';folder.mkdir()
   store.register_source(dict(id='s',url='https://example.com/talk/',title='Talk',date='2026-01-01',occasion='class',sections=[dict(anchor='one',text='A complete original quotation.')]))
   d=dict(slug='test',title='Topic',article_html='<h2>Question</h2><p class="story-original">A complete original quotation.<sup><a data-cite="1">[1]</a></sup></p>',citations=[dict(url='https://example.com/talk/#one')]);f=folder/'test.json';f.write_text(json.dumps(d))
   first=m.migrate(store,folder)[0];pid=first['project_id'];before=store.get(pid)
   self.assertIsNone(before['review']);self.assertEqual(before['engine']['blocks'][1]['text'],'A complete original quotation.')
   self.assertEqual(m.migrate(store,folder)[0]['project_id'],pid);self.assertEqual(store.get(pid),before)
   d['title']='Changed';f.write_text(json.dumps(d))
   with self.assertRaisesRegex(ValueError,'IMPORT_CHANGED'):m.migrate(store,folder)
   self.assertEqual(store.get(pid),before)
 def test_unmatched_quote_is_reported_not_imported(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);s=Store(root/'db.sqlite');d=dict(slug='bad',title='Bad',article_html='<p class="story-original">Untraceable words</p>',citations=[]);(root/'bad.json').write_text(json.dumps(d))
   r=m.migrate(s,root)[0];self.assertEqual(r['status'],'requires_reconciliation');self.assertEqual(r['blocks'][0]['text'],'Untraceable words')
