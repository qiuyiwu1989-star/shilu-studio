"""Transactional reconciliation of a public source bundle; no network or review mutation."""
import argparse,json,hashlib
from pathlib import Path
from .core import Store,now
from .curation import source_bundle,encode

def freshness(store):
    with store.connect() as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='public_sync_state'").fetchone():return {'status':'never_synced'}
        row=db.execute('SELECT payload FROM public_sync_state WHERE id=1').fetchone()
    return json.loads(row[0]) if row else {'status':'never_synced'}

def synchronize(store,document):
    if not isinstance(document,dict) or document.get('schema_version')!=1 or set(document)!={'schema_version','sources'}:raise ValueError('INVALID_PUBLIC_BUNDLE')
    # Validate the entire batch before opening a write transaction. Empty is valid removal.
    sources=source_bundle(document['sources']) if document['sources'] else []
    if not isinstance(document['sources'],list):raise ValueError('INVALID_SOURCES')
    manifest_hash=hashlib.sha256(encode(document).encode()).hexdigest()
    incoming={s['id']:s for s in sources}
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('CREATE TABLE IF NOT EXISTS source_versions(id TEXT,version TEXT,payload TEXT,PRIMARY KEY(id,version))')
        db.execute('CREATE TABLE IF NOT EXISTS source_heads(id TEXT PRIMARY KEY,version TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS public_sync_managed(id TEXT PRIMARY KEY)')
        db.execute('CREATE TABLE IF NOT EXISTS public_sync_state(id INTEGER PRIMARY KEY,payload TEXT)')
        heads=dict(db.execute('SELECT id,version FROM source_heads'))
        managed={r[0] for r in db.execute('SELECT id FROM public_sync_managed')}
        # A URL cannot belong to another ID, including manually registered sources.
        for sid,version in heads.items():
            if sid in incoming or sid in managed-incoming.keys():continue
            raw=db.execute('SELECT payload FROM source_versions WHERE id=? AND version=?',(sid,version)).fetchone()
            if raw and json.loads(raw[0])['url'] in {s['url'] for s in sources}:raise ValueError('URL_OWNED_BY_OTHER_SOURCE')
        added=[sid for sid in incoming if sid not in heads]
        changed=[sid for sid,s in incoming.items() if sid in heads and heads[sid]!=s['version']]
        unchanged=[sid for sid,s in incoming.items() if heads.get(sid)==s['version']]
        removed=sorted(managed-incoming.keys())
        for sid,s in incoming.items():
            db.execute('INSERT OR IGNORE INTO source_versions VALUES(?,?,?)',(sid,s['version'],encode(s)))
            db.execute('INSERT OR REPLACE INTO source_heads VALUES(?,?)',(sid,s['version']))
        for sid in removed:db.execute('DELETE FROM source_heads WHERE id=?',(sid,))
        db.execute('DELETE FROM public_sync_managed')
        db.executemany('INSERT INTO public_sync_managed VALUES(?)',[(sid,) for sid in incoming])
        affected=[]
        for pid,payload in db.execute('SELECT id,doc FROM projects'):
            p=json.loads(payload)
            stale=[s['id'] for s in p.get('source_bundle',[]) if s['id'] in removed or (s['id'] in incoming and s['version']!=incoming[s['id']]['version'])]
            if stale:affected.append({'project_id':pid,'sources':stale})
        report=dict(status='synced',manifest_hash=manifest_hash,synced_at=now(),source_count=len(sources),added=added,changed=changed,unchanged=unchanged,removed=removed,affected_projects=affected)
        db.execute('INSERT OR REPLACE INTO public_sync_state VALUES(1,?)',(encode(report),))
    return report

def main():
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True);p.add_argument('--data-dir',type=Path,required=True);a=p.parse_args()
    print(json.dumps(synchronize(Store(a.data_dir/'shilu.sqlite3'),json.loads(a.bundle.read_text())),ensure_ascii=False))
if __name__=='__main__':main()
