"""Versioned source bundles and typed paragraphs for local curation jobs."""
import json,re,uuid
from urllib.parse import urlsplit
import hashlib
def encode(value): return json.dumps(value,ensure_ascii=False,sort_keys=True)
def digest(value): return hashlib.sha256(value.encode()).hexdigest()

def fail(message): raise ValueError(message)
def fields(value,required,optional=()):
    if not isinstance(value,dict) or set(value)-set(required)-set(optional) or set(required)-set(value):
        fail('INVALID_FIELDS')
def string(value):
    if not isinstance(value,str) or not value.strip():fail('INVALID_STRING')
def normalize(text):return re.sub(r'\s+','',text)

def source_bundle(sources):
    if not isinstance(sources,list) or not sources:fail('MISSING_SOURCES')
    if len(sources)>100:fail('TOO_MANY_SOURCES')
    result=[];ids=set();urls=set()
    for source in sources:
        fields(source,['id','url','title','date','occasion','sections'])
        for k in ['id','url','title']:string(source[k])
        for k in ['date','occasion']:
            if not isinstance(source[k],str):fail('INVALID_METADATA')
        u=urlsplit(source['url'])
        if u.scheme not in ['http','https'] or not u.netloc or u.fragment:fail('INVALID_SOURCE_URL')
        if source['id'] in ids or source['url'] in urls:fail('DUPLICATE_SOURCE')
        ids.add(source['id']);urls.add(source['url'])
        if not isinstance(source['sections'],list) or not source['sections']:fail('MISSING_SOURCE_SECTIONS')
        if len(encode(source))>2_000_000:fail('SOURCE_TOO_LARGE')
        anchors=set()
        for section in source['sections']:
            fields(section,['anchor','text'])
            string(section['anchor']);string(section['text'])
            if section['anchor'] in anchors:fail('DUPLICATE_ANCHOR')
            anchors.add(section['anchor'])
        result.append(dict(source,version=digest(encode(source))))
    return result

def check_blocks(blocks,sources):
    if not isinstance(blocks,list) or not blocks:fail('MISSING_BLOCKS')
    if len(blocks)>1000 or len(encode(blocks))>2_000_000:fail('CONTENT_TOO_LARGE')
    lookup={s['id']:s for s in sources};ids=set();citations={};numbers={};refs=[]
    for b in blocks:
        fields(b,['id','type','text'],['source_id','anchor','source_version','citation'])
        string(b['id']);string(b['text'])
        if b['id'] in ids:fail('DUPLICATE_BLOCK')
        ids.add(b['id'])
        if b['type']=='heading' and b['text'].strip()=='原文出处':fail('REFERENCES_ARE_GENERATED')
        if b['type'] not in ['heading','original','editorial']:fail('INVALID_BLOCK_TYPE')
        if b['type']!='original':
            if set(b)&{'source_id','anchor','source_version','citation'}:fail('EDITORIAL_HAS_SOURCE_CLAIM')
            continue
        fields(b,['id','type','text','source_id','anchor','source_version','citation'])
        if type(b['citation']) is not int or b['citation']<1:fail('INVALID_CITATION')
        src=lookup.get(b['source_id'])
        if not src:fail('UNKNOWN_SOURCE')
        if src['version']!=b['source_version']:fail('STALE_SOURCE_VERSION')
        section=next((x for x in src['sections'] if x['anchor']==b['anchor']),None)
        if section is None:fail('ANCHOR_NOT_FOUND')
        if normalize(b['text']) not in normalize(section['text']):fail('QUOTE_NOT_IN_SOURCE_SECTION')
        key=(src['url'],b['anchor']);n=b['citation']
        if key in citations and citations[key]!=n:fail('DUPLICATE_SOURCE_NUMBER')
        if n in numbers and numbers[n]!=key:fail('CITATION_COLLISION')
        if key not in citations:
            refs.append(dict(number=n,source_id=src['id'],url=src['url']+'#'+b['anchor'],title=src['title'],date=src['date'],occasion=src['occasion'],source_version=src['version']))
        citations[key]=n;numbers[n]=key
    if not refs:fail('MISSING_PROVENANCE')
    if [r['number'] for r in refs]!=list(range(1,len(refs)+1)):fail('CITATION_ORDER')
    return refs

def render(title,blocks,refs):
    parts=['# '+title]
    for b in blocks:
        if b['type']=='heading':parts.append('## '+b['text'])
        elif b['type']=='original':parts.append(b['text']+' ['+str(b['citation'])+']')
        else:parts.append(b['text'])
    parts.append('## 原文出处')
    parts.extend(f"[{r['number']}] {r['title']} · {r['date']} ({r['url']})" for r in refs)
    return '\n\n'.join(parts)


def skill_context():
    from pathlib import Path
    text=(Path(__file__).parent/'skills/cross-event-writing/SKILL.md').read_text(encoding='utf-8')
    return {'name':'cross-event-writing','text':text,'version':digest(text)}

def review_payload(p):
    value=[p['config'],p['human']]
    if p.get('kind')=='curation':
        value.extend([p['human_blocks'],p['source_bundle'],p['skill_context']['version']])
    return value

class CurationStore:
    """Shares Store's SQLite connection, project revisions and review gate."""
    def register_source(self,source):
        snapshot=source_bundle([source])[0]
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('CREATE TABLE IF NOT EXISTS source_versions (id TEXT, version TEXT, payload TEXT, PRIMARY KEY(id,version))')
            db.execute('CREATE TABLE IF NOT EXISTS source_heads (id TEXT PRIMARY KEY, version TEXT)')
            db.execute('INSERT OR IGNORE INTO source_versions VALUES(?,?,?)',(snapshot['id'],snapshot['version'],encode(snapshot)))
            db.execute('INSERT OR REPLACE INTO source_heads VALUES(?,?)',(snapshot['id'],snapshot['version']))
        return snapshot

    def get_source(self,source_id,version=None):
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='source_heads'").fetchone():raise KeyError('Source not found')
            if version is None:
                row=db.execute('SELECT version FROM source_heads WHERE id=?',(source_id,)).fetchone()
                if not row:raise KeyError('Source not found')
                version=row[0]
            row=db.execute('SELECT payload FROM source_versions WHERE id=? AND version=?',(source_id,version)).fetchone()
            if not row:raise KeyError('Source not found')
            return json.loads(row[0])

    def list_sources(self):
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='source_heads'").fetchone():return []
            return [json.loads(r[0]) for r in db.execute('SELECT v.payload FROM source_versions v JOIN source_heads h ON v.id=h.id AND v.version=h.version ORDER BY v.id')]

    def search_sources(self,query,limit=10):
        string(query)
        if type(limit)!=int or not 1<=limit<=30:fail('INVALID_LIMIT')
        hits=[]
        for source in self.list_sources():
            for section in source['sections']:
                count=section['text'].lower().count(query.lower())
                if count:
                    at=section['text'].lower().find(query.lower())
                    hits.append(dict(source_id=source['id'],version=source['version'],anchor=section['anchor'],title=source['title'],excerpt=section['text'][max(0,at-60):at+240],score=count))
        return {'mode':'keyword','hits':sorted(hits,key=lambda h:h['score'],reverse=True)[:limit]}

    def create_curation(self,config,source_ids):
        from .core import validate_config,now
        config=validate_config(config)
        if not isinstance(source_ids,list) or not source_ids or len(source_ids)!=len(set(source_ids)):fail('INVALID_SOURCE_IDS')
        bundle=[self.get_source(i) for i in source_ids]
        p=dict(schema_version=1,kind='curation',id=uuid.uuid4().hex,revision=1,config=config,
               transcript='',sources=[dict(id=s['id']+'#'+sec['anchor'],text=sec['text']) for s in bundle for sec in s['sections']],
               source_bundle=bundle,skill_context=skill_context(),human_blocks=[],engine=None,human=[],review=None,
               exports=[],history=[],candidate_history=[],created_at=now(),updated_at=now())
        with self.connect() as db:db.execute('INSERT INTO projects VALUES(?,?)',(p['id'],encode(p)))
        return p

    def validate_curation(self,p,blocks=None):
        if p.get('kind')!='curation':fail('CURATION_REQUIRED')
        errors=[];changes=[]
        for old in p['source_bundle']:
            try:current=self.get_source(old['id'])
            except KeyError:current=None
            if current is None or current['version']!=old['version']:
                changes.append({'source_id':old['id'],'affected_blocks':[b['id'] for b in (blocks if blocks is not None else p['human_blocks']) if b.get('source_id')==old['id']]})
        if changes:errors.append('STALE_SOURCES')
        if skill_context()['version']!=p['skill_context']['version']:errors.append('RULES_CHANGED')
        try:check_blocks(blocks if blocks is not None else p['human_blocks'],p['source_bundle'])
        except ValueError as e:errors.append(str(e))
        return dict(machine_passed=not errors,errors=errors,source_changes=changes,
                    review_status='recorded' if p.get('review') else 'pending',
                    release_ready=False,scope='Caller-registered snapshots; no claim of online freshness or semantic fidelity.')

    def submit_curation(self,pid,revision,blocks):
        from .core import now
        def change(p):
            report=self.validate_curation(p,blocks)
            if not report['machine_passed']:fail(','.join(report['errors']))
            if p['engine']:p['candidate_history'].append(p['engine'])
            p['engine']=dict(mode='agent',blocks=blocks,at=now(),sections=display_sections(blocks))
        return self.mutate(pid,revision,change)

    def save_curation(self,pid,revision,config,blocks):
        from .core import now,validate_config
        def change(p):
            report=self.validate_curation(p,blocks)
            if not report['machine_passed']:fail(','.join(report['errors']))
            c=validate_config(config)
            if p['human']:p['history'].append(dict(at=now(),config=p['config'],sections=p['human'],blocks=p['human_blocks']))
            p.update(config=c,human_blocks=blocks,human=display_sections(blocks),review=None)
        return self.mutate(pid,revision,change)

    def adopt_curation(self,pid,revision):
        from .core import now
        def change(p):
            if p.get('kind')!='curation' or not p.get('engine'):fail('CURATION_CANDIDATE_REQUIRED')
            blocks=p['engine']['blocks']
            report=self.validate_curation(p,blocks)
            if not report['machine_passed']:fail(','.join(report['errors']))
            if p['human']:p['history'].append(dict(at=now(),config=p['config'],sections=p['human'],blocks=p['human_blocks']))
            p['human_blocks']=blocks
            p['human']=display_sections(blocks)
            p['review']=None
        return self.mutate(pid,revision,change)

    def import_curation(self,imported):
        from .core import now,validate_config
        if imported.get('schema_version')!=1:fail('UNSUPPORTED_SCHEMA')
        # Preserve locked snapshots without moving registry heads backwards.
        bundle=source_bundle([{k:v for k,v in s.items() if k!='version'} for s in imported['source_bundle']])
        for s,old in zip(bundle,imported['source_bundle']):
            if s['version']!=old.get('version'):fail('INVALID_SOURCE_VERSION')
        blocks=imported.get('human_blocks',[])
        if blocks:check_blocks(blocks,bundle)
        for src in bundle:
            try:self.get_source(src['id'])
            except KeyError:self.register_source({k:v for k,v in src.items() if k!='version'})
        p=dict(schema_version=1,kind='curation',id=uuid.uuid4().hex,revision=1,config=validate_config(imported['config']),
               transcript='',sources=[dict(id=s['id']+'#'+sec['anchor'],text=sec['text']) for s in bundle for sec in s['sections']],
               source_bundle=bundle,skill_context=skill_context(),human_blocks=blocks,human=display_sections(blocks),
               engine=None,review=None,exports=[],history=[],candidate_history=[],created_at=now(),updated_at=now())
        with self.connect() as db:db.execute('INSERT INTO projects VALUES(?,?)',(p['id'],encode(p)))
        return p

def display_sections(blocks):
    return [dict(title={'original':'实录原话','editorial':'编辑衔接','heading':'章节'}[b['type']],body=b['text'],
                 source_ids=[b['source_id']+'#'+b['anchor']] if b['type']=='original' else []) for b in blocks]

def public_document(p):
    refs=check_blocks(p['human_blocks'],p['source_bundle'])
    # No full source snapshots, hashes, internal rules or reviewer identities in public exports.
    return dict(schema_version=1,kind='curation',title=p['config']['title'],author=p['config']['author'],
                blocks=[{k:v for k,v in b.items() if k in ['type','text','citation']} for b in p['human_blocks']],
                citations=[{k:v for k,v in r.items() if k in ['number','url','title','date','occasion']} for r in refs])

def curation_markdown(p):
    return render(p['config']['title'],p['human_blocks'],check_blocks(p['human_blocks'],p['source_bundle']))

def curation_html(p):
    import html
    e=html.escape;doc=public_document(p);refs={r['number']:r for r in doc['citations']};parts=[]
    for b in doc['blocks']:
        if b['type']=='heading':parts.append('<h2>'+e(b['text'])+'</h2>');continue
        ref=''
        if b['type']=='original':
            r=refs[b['citation']];label=e(r['title']+' · '+r['date']+' · '+r['occasion'])
            ref=f'<sup class="cite"><a href="#source-{r["number"]}" aria-describedby="cite-{len(parts)}">[{r["number"]}]</a><span role="tooltip" id="cite-{len(parts)}">{label} <a href="{e(r["url"],quote=True)}">阅读原文</a></span></sup>'
        parts.append('<p class="'+b['type']+'">'+e(b['text'])+ref+'</p>')
    foot='<section class="references"><h2>原文出处</h2><ol>'+''.join(f'<li id="source-{r["number"]}"><a href="{e(r["url"],quote=True)}">{e(r["title"])} · {e(r["date"])}</a></li>' for r in refs.values())+'</ol></section>'
    return '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>'''+e(doc['title'])+'''</title><style>
:root{color-scheme:light dark}body{font:18px/1.9 Georgia,"Songti SC",serif;max-width:800px;margin:48px auto;padding:0 24px}h1{line-height:1.3}h2{margin-top:2em}p{white-space:pre-wrap}.editorial{opacity:.7;font-size:.9em}.references{border-top:1px solid #8886;margin-top:32px}.cite{position:relative;font:12px system-ui;margin-left:4px}.cite span{display:none;position:absolute;bottom:100%;right:0;width:min(260px,65vw);padding:12px;background:Canvas;color:CanvasText;border:1px solid #888;border-radius:6px;z-index:2}.cite:hover span,.cite:focus-within span{display:block}a{color:inherit}@media print{.cite span{display:none!important}}
</style><h1>'''+e(doc['title'])+'</h1><p>'+e(doc['author'])+'</p><p class="editorial">灰色文字为编辑衔接；数字引用可查看原始出处。</p><article>'+''.join(parts)+foot+'</article></html>'
