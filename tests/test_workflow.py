import io
import json
import os
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from shilu.core import Conflict, Store, article, generate, scan
from shilu.__main__ import Server


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / 'data.sqlite3')
        self.config = {'title': '测试分享', 'author': '示例讲者'}
        self.p = self.store.create(self.config, '第一段现场发言，记录背景和想法，不添加没有说过的观点。\n\n第二段需要保留的内容，以及尚未确定的假设。')

    def tearDown(self):
        self.tmp.cleanup()

    def saved(self):
        p = self.store.draft(self.p['id'], self.p['revision'], 'verbatim')
        return self.store.save(p['id'], p['revision'], p['config'], p['engine']['sections'])

    def test_regeneration_preserves_human_body(self):
        p = self.saved()
        p['human'][0]['body'] = '人工编辑版本'
        p = self.store.save(p['id'], p['revision'], p['config'], p['human'])
        p = self.store.draft(p['id'], p['revision'], 'verbatim')
        self.assertEqual(p['human'][0]['body'], '人工编辑版本')
        self.assertEqual(len(p['history']), 1)

    def test_review_required_and_invalidated_by_edit(self):
        p = self.saved()
        with self.assertRaises(ValueError):
            self.store.export(p['id'], p['revision'])
        p = self.store.review(p['id'], p['revision'], '复核人')
        p = self.store.export(p['id'], p['revision'])
        self.assertEqual(p['exports'][-1]['status'], 'exported')
        p = self.store.save(p['id'], p['revision'], p['config'], p['human'])
        with self.assertRaises(ValueError):
            self.store.export(p['id'], p['revision'])

    def test_stale_save_cannot_overwrite(self):
        p = self.saved()
        with self.assertRaises(Conflict):
            self.store.save(p['id'], 1, p['config'], p['human'])

    def test_bad_source_reference_rejected(self):
        p = self.saved()
        p['human'][0]['source_ids'] = ['nonexistent']
        with self.assertRaises(ValueError):
            self.store.save(p['id'], p['revision'], p['config'], p['human'])

    def test_html_is_escaped_in_body_and_metadata(self):
        p = self.saved()
        p['config']['title'] = '</script><img src=x onerror=alert(1)>'
        p['human'][0]['body'] = '<script>alert(1)</script>'
        rendered = article(p)
        self.assertNotIn('<img src=x', rendered)
        self.assertNotIn('<script>alert', rendered)
        self.assertIn('&lt;script&gt;', rendered)
        self.assertIn('待人工复核', rendered)

    def test_import_restores_content_but_not_approval(self):
        p = self.saved()
        p = self.store.review(p['id'], p['revision'], 'reviewer')
        imported = self.store.create(p['config'], p['transcript'], imported=p)
        self.assertNotEqual(imported['id'], p['id'])
        self.assertEqual(imported['human'], p['human'])
        self.assertEqual(imported['sources'], p['sources'])
        self.assertIsNone(imported['review'])

    def test_restart_keeps_project(self):
        p = self.saved()
        reopened = Store(self.store.path)
        self.assertEqual(reopened.get(p['id']), p)

    def test_scanner_does_not_mutate(self):
        sections = [{'title': '联系方式', 'body': '电话13812345678', 'source_ids': ['s1']}]
        result = scan(sections)
        self.assertEqual(result['flags'][0]['text'], '138***')
        self.assertIn('13812345678', sections[0]['body'])

    def test_invalid_generation_leaves_project_unchanged(self):
        with self.assertRaises(ValueError):
            self.store.draft(self.p['id'], 1, 'unknown')
        self.assertEqual(self.store.get(self.p['id']), self.p)

    def test_live_adapter_and_truncation(self):
        response = {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps({'sections': [
            {'title': '测试章节', 'body': '测试正文', 'source_ids': ['s1']} ]})}}], 'usage': {'total_tokens': 42}}
        def fake(*args, **kwargs):
            return io.BytesIO(json.dumps(response).encode())
        with patch.dict(os.environ, {'SHILU_API_KEY': 'test-only', 'SHILU_BASE_URL': 'https://provider.example/v1', 'SHILU_MODEL': 'test-model'}), patch('shilu.core.urlopen', fake):
            result = generate(self.p, 'live')
            self.assertEqual(result['usage']['total_tokens'], 42)
            response['choices'][0]['finish_reason'] = 'length'
            with self.assertRaises(ValueError):
                generate(self.p, 'live')


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.server = Server(('127.0.0.1', 0), Store(Path(self.tmp.name) / 'test.sqlite3'))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def request(self, path, data=None, headers=None):
        h = {'Content-Type': 'application/json', 'X-Shilu-Token': self.server.token}
        h.update(headers or {})
        return urlopen(Request(self.base + path, data=json.dumps(data).encode() if data is not None else None, headers=h))

    def test_origin_and_host_rejected(self):
        for headers in ({'Origin': 'https://malicious.example'}, {'Host': 'malicious.example'}):
            with self.assertRaises(HTTPError) as err:
                self.request('/api/session', headers=headers)
            self.assertEqual(err.exception.code, 403)

    def test_missing_token_rejected(self):
        with self.assertRaises(HTTPError) as err:
            self.request('/api/projects', headers={'X-Shilu-Token': ''})
        self.assertEqual(err.exception.code, 403)

    def test_end_to_end_export_and_migration(self):
        p = json.load(self.request('/api/projects', {'config': {'title': '分享', 'author': '讲者', 'anonymize_note': 'private rule'},
            'transcript': 'PRIVATE SOURCE 应该只在私人项目里出现，这是一段足够完整的虚构逐字稿。'}))['project']
        prefix = '/api/projects/' + p['id']
        sections = [{'title': '公开章节', 'body': '仅包含编辑后的公开内容。', 'source_ids': ['s1']}]
        p = json.load(self.request(prefix + '/save', {'revision': p['revision'], 'config': p['config'], 'sections': sections}))['project']
        with self.assertRaises(HTTPError):
            self.request(prefix + '/export', {'revision': p['revision']})
        p = json.load(self.request(prefix + '/review', {'revision': p['revision'], 'reviewer': 'private reviewer', 'confirmed': True}))['project']
        zipped = self.request(prefix + '/export', {'revision': p['revision']}).read()
        with zipfile.ZipFile(io.BytesIO(zipped)) as z:
            self.assertEqual(set(z.namelist()), {'index.html', 'article.md', 'article.json'})
            for name in z.namelist():
                text = z.read(name).decode()
                self.assertNotIn('PRIVATE SOURCE', text)
                self.assertNotIn('private rule', text)
                self.assertNotIn('private reviewer', text)
        p = json.load(self.request(prefix))['project']
        backup = json.load(self.request(prefix + '/backup', {'revision': p['revision']}))
        imported = json.load(self.request('/api/import', {'project': backup}))['project']
        self.assertEqual(imported['transcript'], p['transcript'])
        self.assertIsNone(imported['review'])


if __name__ == '__main__':
    unittest.main()
