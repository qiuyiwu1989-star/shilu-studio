"""Non-destructive project supersession from a reviewed reconciliation manifest."""
import argparse,json
from pathlib import Path
from .core import Store

def apply(store,manifest):
    pairs=manifest['projects'];mapping={p['old_id']:p['new_id'] for p in pairs}
    if len(mapping)!=len(pairs) or set(mapping)&set(mapping.values()):raise ValueError('INVALID_SUPERSESSION_GRAPH')
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE');updates=[]
        for old,new in mapping.items():
            p=store.get(old,db);target=store.get(new,db)
            if target.get('superseded_by'):raise ValueError('TARGET_ARCHIVED')
            if p.get('superseded_by') not in (None,new):raise ValueError('SUPERSESSION_CONFLICT')
            if p.get('superseded_by')==new:continue
            p['superseded_by']=new;updates.append((json.dumps(p,ensure_ascii=False),old))
        db.executemany('UPDATE projects SET doc=? WHERE id=?',updates)
    return {'updated':len(updates),'links':mapping}

def main():
    p=argparse.ArgumentParser();p.add_argument('--data-dir',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True);a=p.parse_args()
    print(json.dumps(apply(Store(a.data_dir/'shilu.sqlite3'),json.loads(a.manifest.read_text()))))
if __name__=='__main__':main()
