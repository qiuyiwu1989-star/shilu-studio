"""Convert archived reading HTML to source-checked candidates without review."""
import json,re,html,sys,hashlib,argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from shilu.core import Store
from shilu.curation import check_blocks

def migrate(store,folder):
 with store.connect() as db:db.execute('CREATE TABLE IF NOT EXISTS curated_imports(slug TEXT PRIMARY KEY, hash TEXT, project_id TEXT)')
 lookup={s['url'].rstrip('/'):s for s in store.list_sources()};report=[]
 for f in sorted(folder.glob('*.json')):
  raw=f.read_text();d=json.loads(raw);sha=hashlib.sha256(raw.encode()).hexdigest()
  with store.connect() as db:old=db.execute('SELECT hash,project_id FROM curated_imports WHERE slug=?',(d['slug'],)).fetchone()
  if old:
   if old[0]!=sha:raise ValueError('IMPORT_CHANGED: '+d['slug'])
   report.append(dict(slug=d['slug'],project_id=old[1],status='existing'));continue
  blocks=[];sources={};issues=[];numbers={}
  for tag,attrs,content in re.findall(r'<(h2|p)\b([^>]*)>(.*?)</\1>',d['article_html'],re.S):
   if tag=='h2':kind='heading'
   elif 'story-original' in attrs:kind='original'
   elif 'story-bridge' in attrs:kind='editorial'
   else:continue
   text=html.unescape(re.sub('<[^>]+>','',re.sub(r'<sup>.*?</sup>','',content,flags=re.S))).strip()
   if text=='---':continue  # HTML contains a legacy Markdown separator, not speech.
   b=dict(id='b'+str(len(blocks)+1),type=kind,text=text)
   if kind=='original':
    m=re.search(r'data-cite="(\d+)"',content)
    if not m:
     matches=[(src,sec) for src in lookup.values() for sec in src['sections'] if re.sub(r'\s+','',text) in re.sub(r'\s+','',sec['text'])]
     if len(matches)!=1:
      issues.append(dict(block=b['id'],reason='MISSING_EXPLICIT_CITATION',matches=len(matches)));blocks.append(b);continue
     src,sec=matches[0];sources[src['id']]=src;key=(src['id'],sec['anchor']);numbers.setdefault(key,len(numbers)+1)
     b.update(source_id=src['id'],anchor=sec['anchor'],source_version=src['version'],citation=numbers[key]);blocks.append(b);continue
    n=int(m[1]);ref=d['citations'][n-1];url,anchor=ref['url'].split('#',1);src=lookup[url.rstrip('/')];sources[src['id']]=src
    key=(src['id'],anchor);numbers.setdefault(key,len(numbers)+1)
    b.update(source_id=src['id'],anchor=anchor,source_version=src['version'],citation=numbers[key])
   blocks.append(b)
  for b in blocks:
   if b['type']=='original' and 'source_id' in b:
    src=sources[b['source_id']];sec=next((s for s in src['sections'] if s['anchor']==b['anchor']),None)
    if not sec or re.sub(r'\s+','',b['text']) not in re.sub(r'\s+','',sec['text']):issues.append(dict(block=b['id'],reason='QUOTE_NOT_IN_SOURCE_SECTION',source_id=src['id'],anchor=b['anchor']))
  if issues:
   report.append(dict(slug=d['slug'],status='requires_reconciliation',issues=issues,blocks=blocks));continue
  check_blocks(blocks,list(sources.values()))
  p=store.create_curation(dict(title=d['title'],author='邱懿武'),list(sources));p=store.submit_curation(p['id'],p['revision'],blocks)
  with store.connect() as db:db.execute('INSERT INTO curated_imports VALUES(?,?,?)',(d['slug'],sha,p['id']))
  report.append(dict(slug=d['slug'],status='candidate_unreviewed',project_id=p['id'],blocks=len(blocks)))
 return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--db',type=Path,required=True);p.add_argument('--articles',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args();r=migrate(Store(a.db),a.articles);a.report.write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps([{k:v for k,v in x.items() if k not in ['blocks','issues']} for x in r],ensure_ascii=False))
