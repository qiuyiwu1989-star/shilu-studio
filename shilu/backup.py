"""Consistent SQLite backup and non-overwriting restore."""
import argparse,os,sqlite3
from pathlib import Path
from contextlib import closing

def copy_database(source,target):
    source=Path(source).resolve();target=Path(target)
    if not source.is_file():raise ValueError('SOURCE_MISSING')
    fd=os.open(str(target),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
    try:
        with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as src,closing(sqlite3.connect(str(target))) as dst:
            src.backup(dst)
            if dst.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('INTEGRITY_FAILED')
    except Exception:
        target.unlink(missing_ok=True);raise
    return target

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['backup','restore']);p.add_argument('--source',required=True);p.add_argument('--target',required=True);a=p.parse_args()
    print(copy_database(a.source,a.target))
if __name__=='__main__':main()
