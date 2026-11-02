"""Local stdio MCP sharing the human workbench database. No review/publish tools."""
import argparse,json,os,sys
from pathlib import Path
from .core import Store
from .curation import skill_context

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
def call(store,name,args):
    if name not in SPECS:raise ValueError('UNKNOWN_TOOL')
    props,required,_=SPECS[name]
    if not isinstance(args,dict) or set(args)-set(props) or set(required)-set(args):raise ValueError('INVALID_ARGUMENTS')
    for k,v in args.items():
        typ=props[k]['type']
        if (typ=='string' and not isinstance(v,str)) or (typ=='integer' and type(v)!=int) or (typ=='boolean' and type(v)!=bool) or (typ=='array' and not isinstance(v,list)) or (typ=='object' and not isinstance(v,dict)):
            raise ValueError('INVALID_ARGUMENTS')
    if name=='get_module_context':return dict(skill_context=skill_context(),workflow=['register_source','search_sources','get_source','create_curation','submit_curation','validate_curation','human workbench: save, review, export'],boundary='Local stdio; caller snapshots; no automatic review or publication.')
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
        except ValueError:continue
        if not isinstance(q,dict) or 'id' not in q:continue
        method=q.get('method');params=q.get('params',{});response={'jsonrpc':'2.0','id':q['id']}
        if method=='initialize':
            result={'protocolVersion':params.get('protocolVersion','2024-11-05'),'serverInfo':{'name':'shilu-studio','version':'0.2.0'},'capabilities':{'tools':{}}}
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
