"""Prepare a private handoff bundle from an actually reviewed Store revision."""
import argparse,hashlib,json,os,shutil,tempfile
from pathlib import Path
from .core import Store
from .curation import public_document

def prepare(store,project_id,revision,output):
    output=Path(output)
    if output.exists():raise ValueError('OUTPUT_EXISTS')
    if not output.parent.is_dir():raise ValueError('OUTPUT_PARENT_MISSING')
    before=store.get(project_id)
    if before.get('kind')!='curation':raise ValueError('CURATION_REQUIRED')
    staging=Path(tempfile.mkdtemp(prefix='.release-',dir=str(output.parent)))
    try:
        p=store.export(project_id,revision) # Never create or replace human approval.
        payload=(json.dumps(public_document(p),ensure_ascii=False,indent=2)+'\n').encode()
        manifest={'schema_version':1,'private':True,'project_id':project_id,'reviewed_revision':revision,'export_revision':p['revision'],
                  'rules_hash':p['skill_context']['version'],'source_versions':{s['id']:s['version'] for s in p['source_bundle']},
                  'article_sha256':hashlib.sha256(payload).hexdigest(),'deploy_status':'not_started'}
        (staging/'article.json').write_bytes(payload)
        (staging/'release-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
        # Output is private; only article.json may enter the public site.
        os.chmod(staging,0o700)
        for f in staging.iterdir():os.chmod(f,0o600)
        staging.rename(output)
        return manifest
    finally:
        if staging.exists():shutil.rmtree(staging)

def main():
    p=argparse.ArgumentParser();p.add_argument('--data-dir',required=True);p.add_argument('--project-id',required=True);p.add_argument('--revision',required=True,type=int);p.add_argument('--output',required=True)
    a=p.parse_args();db=Path(a.data_dir)/'shilu.sqlite3'
    if not db.is_file():p.error('Database not found')
    print(json.dumps(prepare(Store(db),a.project_id,a.revision,a.output),ensure_ascii=False))
if __name__=='__main__':main()
