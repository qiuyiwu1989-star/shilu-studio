"""Explicit, opt-in live smoke evaluation using only a synthetic transcript.

Run from repository root: python3 scripts/eval_recap.py --live
Results stay in ignored workspace/evaluation/. Contains no credentials.
This checks anchors and structure, not semantic correctness; read the result.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shilu.config import load_env
from shilu.core import generate, sources, article


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', help='send synthetic input to the configured model')
    args = parser.parse_args()
    if not args.live:
        parser.error('--live is required; this command consumes model tokens')
    load_env('.env')
    transcript = Path('examples/eval-transcript.txt').read_text()
    config = {'title': '一门项目课的 AI 使用试点', 'author': '虚构讲者', 'date': '2026-09-30',
        'occasion': '虚构评测', 'scope_note': '整理全部内容，保留纠正后的数字与限定条件。',
        'anonymize_note': '星河示例教育有限公司统一替换为一家教育机构。'}
    p = {'config': config, 'sources': sources(transcript)}
    started = time.monotonic()
    result = generate(p, 'live')
    body = '\n\n'.join(s['title'] + '\n' + s['body'] for s in result['sections'])
    all_ids = {s['id'] for s in p['sources']}
    used_ids = {ref for s in result['sections'] for ref in s['source_ids']}
    report = {'model': result['model'], 'elapsed_seconds': round(time.monotonic() - started, 2),
        'input_chars': len(transcript), 'output_chars': len(body), 'usage': result.get('usage'),
        'sections': result['sections'], 'unreferenced_sources': sorted(all_ids - used_ids),
        'company_name_removed': '星河示例教育有限公司' not in body,
        'manual_review_required': ['十二组与七组的区别', '四周、三位使用者、两张草图是否保留',
            '无对照实验与不验证学习效果', '30%属于另外场景', '八万元未批准',
            'AI非评分必选条件', '继续小范围而非全校推广', '老师判断仍保留']}
    out = Path('workspace/evaluation')
    out.mkdir(parents=True, exist_ok=True)
    (out / 'ark-flash-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    (out / 'ark-flash-article.html').write_text(article({'config': config, 'human': result['sections'], 'review': None}))
    print(json.dumps({k: v for k, v in report.items() if k not in ('sections', 'manual_review_required')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
