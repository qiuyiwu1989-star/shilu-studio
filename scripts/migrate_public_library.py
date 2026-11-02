"""Import archived public sources; preserve published pages as unreviewed legacy attachments."""
import argparse,hashlib,json,sqlite3,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from shilu.core import Store

def migrate(library,articles,destination):
    destination.mkdir(parents=True,exist_ok=True)
    store=Store(destination/'shilu.sqlite3');latest=json.loads((library/'latest.json').read_text());report={'sources':[],'articles':[]}
    with store.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS legacy_public_articles (slug TEXT PRIMARY KEY, sha256 TEXT NOT NULL, payload TEXT NOT NULL, review_status TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS source_import_provenance (source_id TEXT, source_version TEXT, archive_version TEXT, checked_at TEXT, PRIMARY KEY(source_id,source_version))')
    for event in latest['events']:
        if event['status']!='verified':continue
        original=json.loads((library/'snapshots'/event['version']/'source.json').read_text())
        source=original['source'];saved=store.register_source({k:source[k] for k in ['id','url','title','date','occasion','sections']})
        with store.connect() as db:db.execute('INSERT OR IGNORE INTO source_import_provenance VALUES(?,?,?,?)',(source['id'],saved['version'],event['version'],event.get('verified_at',latest['checked_at'])))
        report['sources'].append({'id':source['id'],'version':saved['version']})
    for path in sorted(articles.glob('*.json')):
        raw=path.read_text();doc=json.loads(raw);sha=hashlib.sha256(raw.encode()).hexdigest()
        with store.connect() as db:
            existing=db.execute('SELECT sha256 FROM legacy_public_articles WHERE slug=?',(doc['slug'],)).fetchone()
            if existing and existing[0]!=sha:raise ValueError('Legacy article changed: '+doc['slug'])
            db.execute('INSERT OR IGNORE INTO legacy_public_articles VALUES(?,?,?,?)',(doc['slug'],sha,raw,'legacy_published_requires_structured_review'))
        report['articles'].append({'slug':doc['slug'],'sha256':sha,'status':'preserved_legacy_not_reviewed'})
    (destination/'migration-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--articles',type=Path,required=True);p.add_argument('--destination',type=Path,required=True);a=p.parse_args()
    r=migrate(a.library,a.articles,a.destination);print(json.dumps({'sources':len(r['sources']),'legacy_articles':len(r['articles'])}))
