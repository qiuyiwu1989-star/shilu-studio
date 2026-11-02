"""Local stdio MCP sharing the human workbench database. No review/publish tools."""
import argparse,json,os,sys
from pathlib import Path
from .core import Store, validate_sections
from .curation import skill_context
from .sync_public import freshness

STR={'type':'string'}
SOURCE={'type':'object','properties':{**{k:STR for k in ['id','url','title','date','occasion']},
    'sections':{'type':'array','items':{'type':'object','properties':{'anchor':STR,'text':STR},'required':['anchor','text'],'additionalProperties':False}}},
    'required':['id','url','title','date','occasion','sections'],'additionalProperties':False}
BLOCK={'type':'object','properties':{**{k:STR for k in ['id','text','source_id','anchor','source_version']},
    'type':{'type':'string','enum':['original','editorial','heading']},'citation':{'type':'integer','minimum':1}},'required':['id','type','text'],'additionalProperties':False}
SPECS={
 'get_module_context':({},[],'Read writing skills and workflow before writing.'),
 'register_source':({'source':SOURCE},['source'],'Register a caller-provided source snapshot; does not claim online verification.'),
 'list_sources':({},[],'List registered source metadata and versions.'),
 'get_source':({'source_id':STR,'version':STR},['source_id'],'Read complete source sections, optionally a historical version.'),
 'search_sources':({'query':STR,'limit':{'type':'integer','minimum':1,'maximum':30}},['query'],'Keyword search over registered sources.'),
 'create_curation':({'config':{'type':'object','properties':{k:STR for k in ['title','author','date','occasion','audience','scope_note','anonymize_note']},'required':['title','author'],'additionalProperties':False},'source_ids':{'type':'array','items':STR}},['config','source_ids'],'Create a cross-event project, locking sources and returning mandatory skill_context.'),
 'get_project':({'project_id':STR},['project_id'],'Resume a project: source/rule snapshots, candidate, human draft and revision.'),
 'submit_curation':({'project_id':STR,'revision':{'type':'integer','minimum':1},'blocks':{'type':'array','items':BLOCK}},['project_id','revision','blocks'],'Submit candidate blocks with optimistic revision control; never overwrite human text.'),
 'validate_curation':({'project_id':STR,'candidate':{'type':'boolean'}},['project_id'],'Validate saved human blocks or candidate against current registered source heads and writing rules.')
}
CONFIG={'type':'object','properties':{k:STR for k in ['title','author','date','occasion','audience','scope_note','anonymize_note']},'required':['title','author'],'additionalProperties':False}
SECTION={'type':'object','properties':{'title':STR,'body':STR,'source_ids':{'type':'array','items':STR}},'required':['title','body','source_ids'],'additionalProperties':False}
SPECS.update({
 'create_recap':({'config':CONFIG,'transcript':STR},['config','transcript'],'Create a single-event recap from original transcript; read sources before drafting.'),
 'submit_recap':({'project_id':STR,'revision':{'type':'integer','minimum':1},'sections':{'type':'array','items':SECTION}},['project_id','revision','sections'],'Submit an Agent candidate only; human draft and review remain unchanged.'),
 'validate_recap':({'project_id':STR},['project_id'],'Validate candidate source identifiers; human fidelity review is still required.')
})
def recap_context():
    return {'skill':(Path(__file__).parent/'skills/single-event-recap/SKILL.md').read_text(), 'workflow':['create_recap','get_project','submit_recap','validate_recap','human workbench: adopt, save, review, export']}

def call(store,name,args):
    if name not in SPECS:raise ValueError('UNKNOWN_TOOL')
    props,required,_=SPECS[name]
    if not isinstance(args,dict) or set(args)-set(props) or set(required)-set(args):raise ValueError('INVALID_ARGUMENTS')
    for k,v in args.items():
        typ=props[k]['type']
        if (typ=='string' and not isinstance(v,str)) or (typ=='integer' and type(v)!=int) or (typ=='boolean' and type(v)!=bool) or (typ=='array' and not isinstance(v,list)) or (typ=='object' and not isinstance(v,dict)):
            raise ValueError('INVALID_ARGUMENTS')
    if name=='get_module_context':return dict(public_sync=freshness(store),recap=recap_context(),skill_context=skill_context(),workflow=['register_source','search_sources','get_source','create_curation','submit_curation','validate_curation','human workbench: save, review, export'],boundary='Local stdio; caller snapshots; no automatic review or publication.')
    if name=='create_recap':
        if set(args['config'])-set(CONFIG['properties']):raise ValueError('INVALID_ARGUMENTS')
        result=store.create(args['config'],args['transcript'])
        context=recap_context()
        context['rules_change_policy']='Snapshot retained; single-event rule changes do not currently block review/export.'
        return store.mutate(result['id'],result['revision'],lambda p:p.update(skill_context=context,candidate_history=[]))
    if name=='submit_recap':
        def change(p):
            if p.get('kind')=='curation':raise ValueError('Expected single-event recap')
            if any(not isinstance(s,dict) or set(s)-set(SECTION['properties']) for s in args['sections']):raise ValueError('INVALID_ARGUMENTS')
            sections=validate_sections(args['sections'],{x['id'] for x in p['sources']})
            if p.get('engine'):
                p.setdefault('candidate_history',[]).append({'revision':p['revision'],'candidate':p['engine']})
            p['engine']={'mode':'live','model':'external Agent (MCP candidate)','sections':sections}
        return store.mutate(args['project_id'],args['revision'],change)
    if name=='validate_recap':
        p=store.get(args['project_id'])
        if p.get('kind')=='curation':raise ValueError('Expected single-event recap')
        validate_sections((p.get('engine') or {}).get('sections',[]),{x['id'] for x in p['sources']})
        return {'machine_passed':True,'human_review_required':True,'release_ready':False,'scope':'Source IDs only; not semantic fidelity or fact verification. Single-event rule changes do not block review/export.'}
    if name=='register_source':return store.register_source(args['source'])
    if name=='list_sources':return [{k:s[k] for k in ['id','url','title','date','occasion','version']} for s in store.list_sources()]
    if name=='get_source':return store.get_source(**args)
    if name=='search_sources':return store.search_sources(**args)
    if name=='create_curation':return store.create_curation(**args)
    if name=='get_project':return store.get(args['project_id'])
    if name=='submit_curation':return store.submit_curation(args['project_id'],args['revision'],args['blocks'])
    if name=='validate_curation':
        p=store.get(args['project_id'])
        blocks=(p.get('engine') or {}).get('blocks',[]) if args.get('candidate') else None
        return store.validate_curation(p,blocks)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-dir',default=os.environ.get('SHILU_DATA_DIR','./workspace'))
    args=parser.parse_args();store=Store(Path(args.data_dir)/'shilu.sqlite3')
    for line in sys.stdin:
        try:q=json.loads(line)
        except ValueError:
            print(json.dumps({'jsonrpc':'2.0','id':None,'error':{'code':-32700,'message':'Parse error'}}),flush=True);continue
        if not isinstance(q,dict) or q.get('jsonrpc')!='2.0' or not isinstance(q.get('method'),str):
            print(json.dumps({'jsonrpc':'2.0','id':None,'error':{'code':-32600,'message':'Invalid request'}}),flush=True);continue
        if 'id' not in q:continue
        method=q.get('method');params=q.get('params',{});response={'jsonrpc':'2.0','id':q['id']}
        if not isinstance(params,dict):
            response['error']={'code':-32602,'message':'Invalid params'}
            print(json.dumps(response),flush=True);continue
        if method=='initialize':
            result={'protocolVersion':params.get('protocolVersion') if params.get('protocolVersion') in ('2024-11-05','2025-03-26','2025-06-18') else '2025-06-18','serverInfo':{'name':'shilu-studio','version':'0.2.0'},'capabilities':{'tools':{}}}
        elif method=='tools/list':
            result={'tools':[{'name':n,'description':spec[2],'inputSchema':{'type':'object','properties':spec[0],'required':spec[1],'additionalProperties':False}} for n,spec in SPECS.items()]}
        elif method=='tools/call':
            try:
                value=call(store,params['name'],params.get('arguments',{}))
                result={'content':[{'type':'text','text':json.dumps(value,ensure_ascii=False)}]}
            except (ValueError,KeyError,TypeError) as e:result={'isError':True,'content':[{'type':'text','text':str(e)}]}
            except Exception:result={'isError':True,'content':[{'type':'text','text':'Internal error; no sensitive details returned.'}]}
        elif method=='ping':result={}
        else:response['error']={'code':-32601,'message':'Method not found'};result=None
        if result is not None:response['result']=result
        print(json.dumps(response,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
