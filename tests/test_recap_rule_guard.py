import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from shilu.core import Store
from shilu.mcp import call

class RecapRuleGuardTests(unittest.TestCase):
    def test_changed_removed_and_missing_profile_block_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / 'profile.md'
            profile.write_text('Original rules')
            with patch.dict(os.environ, {'SHILU_RECAP_PROFILE_PATH': str(profile)}):
                store = Store(Path(directory) / 'db.sqlite3')
                p = store.create({'title':'Title','author':'Author'}, 'Original transcript with enough characters.')
                p = store.save(p['id'],p['revision'],p['config'],[{'title':'Section','body':'Body','source_ids':['s1']}])
                p = store.review(p['id'],p['revision'],'Human')
                call(store,'submit_recap',{'project_id':p['id'],'revision':p['revision'],'sections':p['human']})
                p=store.get(p['id'])
                self.assertTrue(call(store,'validate_recap',{'project_id':p['id']})['machine_passed'])
                profile.write_text('Changed rules')
                with self.assertRaisesRegex(ValueError,'规则'):
                    call(store,'validate_recap',{'project_id':p['id']})
                with self.assertRaisesRegex(ValueError,'规则'):
                    store.draft(p['id'],p['revision'],'verbatim')
                for action in (lambda: store.review(p['id'],p['revision'],'Human'), lambda: store.export(p['id'],p['revision'])):
                    with self.assertRaisesRegex(ValueError,'规则'): action()
                    self.assertEqual(store.get(p['id']),p)
                profile.unlink()
                with self.assertRaisesRegex(ValueError,'UNAVAILABLE'): store.export(p['id'],p['revision'])
                self.assertEqual(store.get(p['id']),p)
                with patch.dict(os.environ, {}, clear=True):
                    with self.assertRaisesRegex(ValueError,'规则'): store.export(p['id'],p['revision'])
                profile.write_text('Original rules')
                store.export(p['id'],p['revision'])

    def test_legacy_missing_snapshot_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            store=Store(Path(directory)/'db.sqlite3')
            with self.assertRaisesRegex(ValueError,'规则'):
                store.check_recap_rules({'human':[]})

    def test_live_generation_sends_locked_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            profile=Path(directory)/'profile.md'
            profile.write_text('PRIVATE_PROFILE_SENTINEL')
            with patch.dict(os.environ, {'SHILU_RECAP_PROFILE_PATH':str(profile)}, clear=True):
                store=Store(Path(directory)/'db.sqlite3')
                p=store.create({'title':'Title','author':'Author'},'Original transcript with enough characters.')
                response={'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'sections':[{'title':'Section','body':'Body','source_ids':['s1']}]})}}]}
                config={'key':'fake','base':'https://example.invalid','model':'fake','max_tokens':100,'effort':'','thinking':''}
                with patch('shilu.core.model_config',return_value=config), patch('shilu.core.urlopen',return_value=io.BytesIO(json.dumps(response).encode())) as request:
                    store.draft(p['id'],p['revision'],'live')
                payload=json.loads(request.call_args.args[0].data)
                self.assertIn('PRIVATE_PROFILE_SENTINEL',payload['messages'][0]['content'])
                self.assertIn(p['skill_context']['skill'],payload['messages'][0]['content'])
