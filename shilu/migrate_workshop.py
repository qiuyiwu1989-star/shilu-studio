"""Read-only migration from a workshop SQLite database; never transfers approval."""
import argparse,json,sqlite3
from pathlib import Path
from .core import Store,fingerprint,validate_sections,sources

def migrate(source_db,store,author):
    path=Path(source_db).resolve()
    if not path.is_file():raise ValueError('Source database does not exist')
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        rows=[dict(r) for r in db.execute('SELECT id,title,transcript,engine,body,reviewed FROM drafts')]
    known={p.get('legacy_import',{}).get('fingerprint'):p['id'] for p in store.list()}
    report=[]
    for row in rows:
        key=fingerprint(row)
        if key in known:
            report.append(dict(legacy_id=row['id'],status='already_imported',project_id=known[key]));continue
        try:
            config={'title':row['title'],'author':author,'scope_note':'从旧工坊迁入。正文仅关联整份原稿，未进行逐段语义核验；Markdown文本原样保留。'}
            refs=[s['id'] for s in sources(row['transcript'])]
            human=validate_sections([dict(title=row['title'],body=row['body'],source_ids=refs)],set(refs)) if row['body'].strip() else []
            engine=validate_sections([dict(title=row['title'],body=row['engine'],source_ids=refs)],set(refs)) if row['engine'].strip() else []
            p=store.create(config,row['transcript'])
            def change(project):
                refs=[s['id'] for s in project['sources']]
                if row['body'].strip():
                    project['human']=human
                if row['engine'].strip():
                    project['engine']={'mode':'legacy','model':'','sections':engine}
                project['legacy_import']={'id':row['id'],'fingerprint':key,'previous_reviewed':bool(row['reviewed']),'source_mapping':'whole_transcript_unverified'}
                project['review']=None
            p=store.mutate(p['id'],p['revision'],change)
            known[key]=p['id']
            report.append(dict(legacy_id=row['id'],status='imported_pending_review',project_id=p['id']))
        except (ValueError,TypeError) as e:report.append(dict(legacy_id=row['id'],status='not_imported',reason=str(e)))
    return report

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source-db',required=True);parser.add_argument('--data-dir',required=True);parser.add_argument('--author',required=True)
    args=parser.parse_args()
    print(json.dumps(migrate(args.source_db,Store(Path(args.data_dir)/'shilu.sqlite3'),args.author),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
