"""Declarative specialization domain. No storage, discovery or executable content."""
from __future__ import annotations
import copy
import hashlib
import json
import re
from pathlib import Path
import evidence_audit

SCHEMA = 'hti-specialization-1'
LEVELS = {'WORK': 'WORK_ESTABLISHED', 'EDITION': 'EDITION_ESTABLISHED', 'EXEMPLAR': 'EXEMPLAR_ESTABLISHED'}
SURFACES = {
 'WORK': {'bibliography','argument_research','source_findings','terminology','witness_relations','research_index','work_facts'},
 'EDITION': {'edition_bibliography','pagination','signatures','variants','paratext','typography','comparators','edition_witness_relations'},
 'EXEMPLAR': {'photographed_leaves','annotations','underlining','defects','condition','binding_observation','page_order','image_state','physical_history'},
}
STATUSES = {'CURRENT','STALE','INVALIDATED','SUPERSEDED','RETIRED'}
FORBIDDEN_ORIGINS = {'specialization','specialization_fact','specialization_inference','storage_locator','model_memory','remembered_content'}

class SpecializationError(ValueError):
    pass

def require(ok, code):
    if not ok: raise SpecializationError(code)

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def identifier(value):
    return isinstance(value,str) and bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}',value))

def revision(value):
    return type(value) is int and value > 0

def sha(value):
    return isinstance(value,str) and bool(re.fullmatch('[a-f0-9]{64}',value))

def scope(value, level=None):
    require(isinstance(value,dict) and set(value)=={'work_id','edition_id','exemplar_id'},'SCOPE_SHAPE')
    require(identifier(value['work_id']),'WORK_SCOPE_REQUIRED')
    require(value['edition_id'] is None or identifier(value['edition_id']),'EDITION_SCOPE_INVALID')
    require(value['exemplar_id'] is None or identifier(value['exemplar_id']),'EXEMPLAR_SCOPE_INVALID')
    require(value['exemplar_id'] is None or value['edition_id'] is not None,'EXEMPLAR_REQUIRES_EDITION')
    if level:
        require((value['edition_id'] is not None)==(level in {'EDITION','EXEMPLAR'}),'LEVEL_EDITION_SCOPE')
        require((value['exemplar_id'] is not None)==(level=='EXEMPLAR'),'LEVEL_EXEMPLAR_SCOPE')

def matches(required, actual):
    scope(required);scope(actual)
    return all(v is None or actual[k]==v for k,v in required.items())

def manifest(value):
    fields={'schema_version','specialization_id','level','scope','required_identity_state','activation_predicates','permitted_surfaces','resources','capabilities','update_rules','invalidation_dependencies','compatibility'}
    require(isinstance(value,dict) and set(value)==fields,'MANIFEST_FIELDS')
    require(value['schema_version']==SCHEMA and value['compatibility']==[SCHEMA],'SCHEMA_INCOMPATIBLE')
    level=value['level'];require(level in LEVELS,'SPECIALIZATION_LEVEL')
    scope(value['scope'],level)
    require(identifier(value['specialization_id']) and ':' not in value['specialization_id'],'SPECIALIZATION_ID')
    require(value['required_identity_state']==LEVELS[level],'IDENTITY_THRESHOLD')
    predicates=['EXACT_WORK']+(['EXACT_EDITION'] if level!='WORK' else [])+(['EXACT_EXEMPLAR'] if level=='EXEMPLAR' else [])
    require(value['activation_predicates']==predicates,'ACTIVATION_PREDICATES')
    surfaces=value['permitted_surfaces']
    require(isinstance(surfaces,list) and len(surfaces)==len(set(surfaces)) and set(surfaces)<=SURFACES[level],'SURFACE_LEVEL_LEAK')
    require(value['capabilities']==['READ_LICENSED_STATE','REVISE_STATE','EXPORT_STATE'],'DECLARATIVE_CAPABILITIES')
    require(value['update_rules']=={'revision_guard':True,'hard_delete_required':False},'UPDATE_RULES')
    require(isinstance(value['invalidation_dependencies'],list) and all(identifier(x) for x in value['invalidation_dependencies']),'INVALIDATION_DEPENDENCIES')
    require(isinstance(value['resources'],list),'RESOURCE_SHAPE')
    for resource in value['resources']:
        require(isinstance(resource,dict) and set(resource)=={'resource_id','surface','locator','sha256'},'RESOURCE_DECLARATIVE')
        require(identifier(resource['resource_id']) and resource['surface'] in surfaces and isinstance(resource['locator'],str) and bool(resource['locator']) and sha(resource['sha256']),'RESOURCE_INVALID')
    return value

def new_manifest(sid,level,subject,surfaces=None):
    return manifest({'schema_version':SCHEMA,'specialization_id':sid,'level':level,'scope':copy.deepcopy(subject),'required_identity_state':LEVELS[level],'activation_predicates':['EXACT_WORK']+(['EXACT_EDITION'] if level!='WORK' else [])+(['EXACT_EXEMPLAR'] if level=='EXEMPLAR' else []),'permitted_surfaces':sorted(SURFACES[level] if surfaces is None else surfaces),'resources':[],'capabilities':['READ_LICENSED_STATE','REVISE_STATE','EXPORT_STATE'],'update_rules':{'revision_guard':True,'hard_delete_required':False},'invalidation_dependencies':[],'compatibility':[SCHEMA]})

def new_registry(registry_id,namespace,account_scope):
    require(all(identifier(x) for x in (registry_id,namespace,account_scope)),'REGISTRY_IDENTITY')
    return {'schema_version':SCHEMA,'registry_id':registry_id,'namespace':namespace,'account_scope':account_scope,'revision':1,'state_version':1,'storage_binding':None,'anchors':{},'records':{},'audit':[]}

def provenance(value):
    require(isinstance(value,dict) and set(value)=={'origin','locator','evidence_refs'} and value['origin']=='general_evidence' and isinstance(value['locator'],str) and bool(value['locator']) and isinstance(value['evidence_refs'],list) and bool(value['evidence_refs']) and all(identifier(x) for x in value['evidence_refs']),'CLAIM_PROVENANCE')

def token(record_id,claim_id=None):
    return 'claim:'+record_id+':'+claim_id if claim_id else 'record:'+record_id

def nodes(reg):
    # Recovery material is authenticated by registry/envelope integrity, but
    # attaching it alone is not a correction to the semantic evidence root.
    result={aid:{k:v for k,v in a.items() if k!='evidence_history'} for aid,a in reg['anchors'].items()}
    for rid,r in reg['records'].items():
        result[token(rid)]={'revision':r['revision'],'status':r['status'],'sha256':digest({'manifest':r['manifest'],'license':r['license'],'dependencies':r['dependencies'],'claims':r['claims']})}
        for cid,c in r['claims'].items():result[token(rid,cid)]={'revision':c['revision'],'status':c['status'],'sha256':digest({k:v for k,v in c.items() if k not in {'revision','status'}})}
    return result

def snapshot(node):
    return digest(node)

def validate(reg):
    require(isinstance(reg,dict) and set(reg)=={'schema_version','registry_id','namespace','account_scope','revision','state_version','storage_binding','anchors','records','audit'},'REGISTRY_FIELDS')
    require(reg['schema_version']==SCHEMA,'SCHEMA_INCOMPATIBLE')
    require(all(identifier(reg[x]) for x in ('registry_id','namespace','account_scope')) and revision(reg['revision']) and revision(reg['state_version']),'REGISTRY_IDENTITY')
    require(isinstance(reg['anchors'],dict) and isinstance(reg['records'],dict) and isinstance(reg['audit'],list),'REGISTRY_SHAPE')
    if reg['storage_binding'] is not None:
        from specialization_storage import validate_binding
        validate_binding(reg['storage_binding'],reg['account_scope'],reg['namespace'])
    for aid,a in reg['anchors'].items():
        require(identifier(aid) and aid.startswith(('evidence:','identity:')),'ANCHOR_ID')
        require(isinstance(a,dict) and set(a) in ({'revision','status','sha256','provenance','source_ref'},{'revision','status','sha256','provenance','source_ref','evidence_history'}),'ANCHOR_FIELDS')
        require(revision(a['revision']) and a['status'] in STATUSES and sha(a['sha256']),'ANCHOR_STATE');provenance(a['provenance'])
        if 'evidence_history' in a:
            from specialization_evidence import validate_history
            validate_history(aid,a['evidence_history'])
        if a['source_ref'] is not None:
            x=a['source_ref'];require(isinstance(x,dict) and set(x)=={'representation_id','span_ids','snapshot','purpose','proposition_id','proposition_snapshot'} and identifier(x['representation_id']) and isinstance(x['span_ids'],list) and bool(x['span_ids']) and all(identifier(s) for s in x['span_ids']) and sha(x['snapshot']) and x['purpose'] in {'REPRESENTED_ARGUMENT','VISIBLE_CONTENT','EXACT_ORIGINAL_WORDING','TRANSCRIBED_WORDING','SECURE_PROPOSITION_OWNERSHIP','SECURE_AUTHOR_POSITION'} and ((x['proposition_id'] is None and x['proposition_snapshot'] is None) or (identifier(x['proposition_id']) and sha(x['proposition_snapshot']))),'SOURCE_REFERENCE')
    for rid,r in reg['records'].items():
        require(identifier(rid) and isinstance(r,dict) and set(r)=={'manifest','revision','state_version','created_revision','updated_revision','status','supersedes','license','dependencies','claims'},'RECORD_FIELDS')
        m=manifest(r['manifest']);require(rid==m['specialization_id'],'RECORD_ID_MISMATCH')
        require(all(revision(r[x]) for x in ('revision','state_version','created_revision','updated_revision')) and r['created_revision']<=r['updated_revision']<=reg['revision'],'RECORD_REVISION')
        require(r['status'] in STATUSES and isinstance(r['dependencies'],dict) and isinstance(r['claims'],dict),'RECORD_STATE')
        require(set(m['invalidation_dependencies'])<=set(r['dependencies']),'MANIFEST_DEPENDENCIES_REQUIRED')
        require(r['supersedes'] is None or r['supersedes'] in reg['records'],'SUPERSESSION_REFERENCE')
        if r['license'] is not None:validate_license(r['license'],m)
        for cid,c in r['claims'].items():
            require(identifier(cid) and ':' not in cid and isinstance(c,dict) and set(c)=={'surface','value','status','revision','provenance','dependencies','physical_license'},'CLAIM_FIELDS')
            require(c['surface'] in m['permitted_surfaces'] and c['status'] in STATUSES and revision(c['revision']) and isinstance(c['dependencies'],dict) and bool(c['dependencies']),'CLAIM_STATE')
            if c['status']=='CURRENT':require(r['status']=='CURRENT' and r['license'] is not None,'CLAIM_REQUIRES_LICENSE')
            canonical(c['value']);provenance(c['provenance'])
            require(c['physical_license'] is None or isinstance(c['physical_license'],dict),'PHYSICAL_LICENSE_SHAPE')
            if c['surface']=='physical_history':
                p=c['physical_license'];require(isinstance(p,dict) and set(p)=={'claim_id','checkpoint_sha256','evidence_ids'} and identifier(p['claim_id']) and sha(p['checkpoint_sha256']) and isinstance(p['evidence_ids'],list) and bool(p['evidence_ids']) and all(identifier(x) for x in p['evidence_ids']),'PHYSICAL_HISTORY_UNLICENSED')
    n=nodes(reg);edges={}
    for rid,r in reg['records'].items():
        owners={token(rid):r['dependencies'],**{token(rid,cid):c['dependencies'] for cid,c in r['claims'].items()}}
        for owner,deps in owners.items():
            edges[owner]=list(deps)
            for dep,expected in deps.items():
                require(dep in n and sha(expected),'DEPENDENCY_REFERENCE')
                if dep.startswith(('record:','claim:')):
                    drid=dep.split(':')[1];require(matches(reg['records'][drid]['manifest']['scope'],r['manifest']['scope']),'CROSS_SCOPE_DEPENDENCY')
                status=r['status'] if owner==token(rid) else r['claims'][owner.split(':')[2]]['status']
                if status=='CURRENT':require(n[dep]['status']=='CURRENT' and expected==snapshot(n[dep]),'DEPENDENCY_STALE')
    visiting=set();done=set()
    def walk(key):
        require(key not in visiting,'DEPENDENCY_CYCLE')
        if key in done:return
        visiting.add(key)
        for dep in edges.get(key,[]):walk(dep)
        visiting.remove(key);done.add(key)
    for key in edges:walk(key)
    for index,event in enumerate(reg['audit']):
        require(isinstance(event,dict) and set(event)=={'revision','operation','reason','before_sha256','previous_event_sha256'},'AUDIT_FIELDS')
        require(revision(event['revision']) and event['revision']<=reg['revision'] and isinstance(event['operation'],str) and bool(event['reason']) and sha(event['before_sha256']),'AUDIT_STATE')
        require(event['previous_event_sha256']==(digest(reg['audit'][index-1]) if index else None),'AUDIT_CHAIN')
    return reg

def mutate(reg,expected,operation,reason,fn):
    validate(reg);require(reg['revision']==expected,'REVISION_CONFLICT');require(isinstance(reason,str) and bool(reason.strip()),'AUDIT_REASON_REQUIRED')
    out=copy.deepcopy(reg);out['revision']+=1;out['state_version']+=1
    fn(out)
    for rid,r in out['records'].items():
        old=reg['records'].get(rid)
        if old is not None and r!=old:
            r['revision']=max(r['revision'],old['revision']+1);r['state_version']=old['state_version']+1;r['updated_revision']=out['revision']
    propagate(out)
    out['audit'].append({'revision':out['revision'],'operation':operation,'reason':reason,'before_sha256':digest(reg),'previous_event_sha256':digest(reg['audit'][-1]) if reg['audit'] else None})
    validate(out);return out

def propagate(reg):
    changed=True;affected=[]
    while changed:
        changed=False;n=nodes(reg)
        for rid,r in reg['records'].items():
            entries=[(token(rid),r)]+[(token(rid,cid),c) for cid,c in r['claims'].items()]
            for key,item in entries:
                if item['status']=='CURRENT' and any(n[d]['status']!='CURRENT' or s!=snapshot(n[d]) for d,s in item['dependencies'].items()):
                    item['status']='STALE';item['revision']+=1;changed=True;affected.append(key)
                    r['updated_revision']=reg['revision']
            if r['status']!='CURRENT':
                for cid,c in r['claims'].items():
                    if c['status']=='CURRENT':c['status']='STALE';c['revision']+=1;changed=True;affected.append(token(rid,cid))
    return affected

def set_anchor(reg,aid,value,expected,reason):
    def edit(out):
        old=out['anchors'].get(aid);require(not old or value['revision']>old['revision'],'ANCHOR_REVISION_CONFLICT')
        out['anchors'][aid]=copy.deepcopy(value);propagate(out)
    return mutate(reg,expected,'SET_ANCHOR',reason,edit)

def add_record(reg,m,expected,reason,dependencies=None):
    manifest(m)
    def edit(out):
        rid=m['specialization_id'];require(rid not in out['records'],'RECORD_EXISTS')
        deps=dependencies or {};n=nodes(out)
        require(set(m['invalidation_dependencies'])<=set(deps),'MANIFEST_DEPENDENCIES_REQUIRED')
        out['records'][rid]={'manifest':copy.deepcopy(m),'revision':1,'state_version':1,'created_revision':out['revision'],'updated_revision':out['revision'],'status':'CURRENT','supersedes':None,'license':None,'dependencies':{d:snapshot(n[d]) for d in deps},'claims':{}}
    return mutate(reg,expected,'CREATE_RECORD',reason,edit)

def validate_license(license,m):
    require(isinstance(license,dict) and set(license)=={'checkpoint_sha256','binding_sha256','identity_state','claim_ids','scope'},'LICENSE_FIELDS')
    require(sha(license['checkpoint_sha256']) and sha(license['binding_sha256']) and license['identity_state'] in evidence_audit.IDENTITY_STATES and evidence_audit.IDENTITY_STATES.index(license['identity_state'])>=evidence_audit.IDENTITY_STATES.index(m['required_identity_state']) and isinstance(license['claim_ids'],list) and bool(license['claim_ids']) and all(identifier(x) for x in license['claim_ids']) and matches(m['scope'],license['scope']),'LICENSE_INVALID')

def admit_established_premise(evidence, binding, claims):
    """Typed user-source work admission; the original evidence is never relabelled."""
    provenance = evidence.get('provenance')
    require(isinstance(provenance, dict) and provenance.get('source') == 'user_supplied_bibliographic_premise', 'USER_PREMISE_SOURCE')
    premise = provenance.get('established_premise')
    require(isinstance(premise, dict) and set(premise) == {'status','level','subject_id','proposition'}, 'USER_PREMISE_TYPE')
    require(premise['status'] == 'ESTABLISHED' and premise['level'] == 'WORK'
            and evidence.get('evidence_class') == 'bibliography' and evidence.get('kind') == 'explicit_author_title', 'USER_PREMISE_LEVEL')
    selected = claims.get(binding['claims'].get('work_id'))
    require(selected is not None and premise['subject_id'] == binding['scope']['work_id'] == selected.get('subject_id')
            and isinstance(premise['proposition'], str) and premise['proposition'].strip()
            and premise['proposition'] == selected.get('value'), 'USER_PREMISE_SUBJECT')


def derive_binding(checkpoint):
    """Select exact asserted general identities before any installed discovery."""
    errors = evidence_audit.audit_checkpoint(checkpoint)
    require(not errors, 'GENERAL_IDENTITY_AUDIT: ' + '; '.join(errors))
    state = checkpoint.get('identity_state')
    require(state in evidence_audit.IDENTITY_STATES, 'IDENTITY_STATE')
    rank = evidence_audit.IDENTITY_STATES.index(state)
    if rank < 2:
        return None
    subject = {'work_id': checkpoint.get('work_id'), 'edition_id': None, 'exemplar_id': None}
    binding = {'scope': subject, 'claims': {}}
    for threshold, key in enumerate(subject, 2):
        if rank < threshold:
            continue
        selected = [c for c in checkpoint.get('claims', [])
                    if c.get('claim_type') == key.replace('_id','_identity')
                    and c.get('claim_id') in checkpoint.get('selected_claim_ids', []) and evidence_audit.is_asserted(c)]
        require(len(selected) == 1, 'AMBIGUOUS_IDENTITY_BINDING')
        require(selected[0].get('origin') == 'general_identity' and identifier(selected[0].get('subject_id')), 'IDENTITY_SUBJECT_MISMATCH')
        subject[key] = selected[0]['subject_id']
        binding['claims'][key] = selected[0]['claim_id']
    identity_license(checkpoint, binding)
    return binding


PRIMARY_FIELDS = {'schema_version','storage_state','registry','identity_binding','uses','registry_sha256','storage_receipt'}


def primary_context(context):
    require(isinstance(context, dict) and set(context) in (PRIMARY_FIELDS, PRIMARY_FIELDS | {'installed_readiness'}), 'SPECIALIZATION_CONTEXT_FIELDS')
    require(context['schema_version'] == SCHEMA and isinstance(context['uses'], list), 'SPECIALIZATION_CONTEXT_SHAPE')
    return {k: copy.deepcopy(context[k]) for k in PRIMARY_FIELDS}


def validate_primary(context, checkpoint, root=None):
    from specialization_storage import validate_context_storage
    view = primary_context(context)
    validate_context_storage(view)
    if view['registry'] is None:
        require(not view['uses'], 'SPECIALIZATION_STATE_UNAVAILABLE')
    else:
        validate(view['registry'])
        require(digest(view['registry']) == view['registry_sha256'], 'REGISTRY_INTEGRITY')
    binding = view['identity_binding']
    if binding is None:
        require(not view['uses'], 'SPECIALIZATION_ACTIVE_BINDING_REQUIRED')
        return view
    current = identity_license(checkpoint, binding)
    require(binding == derive_binding(checkpoint), 'SPECIALIZATION_ACTIVE_BINDING_STALE')
    if view['registry'] is not None:
        active = []
        for rid, record in view['registry']['records'].items():
            m = record['manifest']
            if record['status'] == 'CURRENT' and record['license'] is not None and matches(m['scope'], current['scope']):
                activate(view['registry'], rid, checkpoint, binding)
                active.append(rid)
        if view['storage_state'] == 'INSTALLED_READ_ONLY':
            from specialization_resources import validate_context, ROOT
            # Active unused scopes are checked too, not only claimed output.
            validate_context(view, checkpoint, ROOT if root is None else root,
                             records=sorted(set(active) | {u.get('record_id') for u in view['uses']}))
    return view


def identity_license(checkpoint,binding):
    """Fresh general identity checkpoint alone grants a scope. No cached facts."""
    require(isinstance(checkpoint,dict) and isinstance(binding,dict) and set(binding)=={'scope','claims'},'IDENTITY_BINDING')
    scope(binding['scope']);require(checkpoint.get('work_id')==binding['scope']['work_id'],'IDENTITY_SUBJECT_MISMATCH');state=checkpoint.get('identity_state');require(state in evidence_audit.IDENTITY_STATES,'IDENTITY_STATE')
    errors=evidence_audit.audit_checkpoint(checkpoint);require(not errors,'GENERAL_IDENTITY_AUDIT: '+'; '.join(errors))
    claims={c['claim_id']:c for c in checkpoint.get('claims',[])};emap={e['evidence_id']:e for e in checkpoint.get('evidence',[])}
    require(isinstance(binding['claims'],dict),'IDENTITY_CLAIM_BINDING')
    ids=[];snapshots={};seen=set();visiting=set()
    def noncircular(value):
        if isinstance(value,dict):
            require(not (set(value)&{'specialization_ref','specialization_id','storage_binding'}),'CIRCULAR_IDENTITY_REFERENCE')
            for key,item in value.items():
                if key=='origin':require(item not in FORBIDDEN_ORIGINS,'CIRCULAR_IDENTITY_PROVENANCE')
                noncircular(item)
        elif isinstance(value,list):
            for item in value:noncircular(item)
    def evidence(eid):
        require(eid in emap,'IDENTITY_ANCESTRY_MISSING');require(eid not in visiting,'IDENTITY_ANCESTRY_CYCLE')
        if eid in seen:return
        e=emap[eid];visiting.add(eid);noncircular(e)
        require(e.get('origin') in {'general_evidence','user_stipulated'} and e.get('kind')!='storage_locator' and e.get('identity_admissible') is True,'CIRCULAR_IDENTITY_EVIDENCE')
        if e.get('origin')=='user_stipulated':
            admit_established_premise(e, binding, claims)
        require(e.get('status','CURRENT')=='CURRENT','IDENTITY_EVIDENCE_STALE')
        parents=e.get('ancestor_evidence_ids');require(isinstance(parents,list),'IDENTITY_ANCESTRY_REQUIRED')
        for parent in parents:evidence(parent)
        visiting.remove(eid);seen.add(eid)
    rank=evidence_audit.IDENTITY_STATES.index(state)
    for i,key in enumerate(('work_id','edition_id','exemplar_id'),2):
        subject=binding['scope'][key];cid=binding['claims'].get(key)
        if rank<i:
            require(subject is None if key!='work_id' else True,'UNLICENSED_SUBJECT_BINDING');require(cid is None,'UNLICENSED_CLAIM_BINDING');continue
        require(identifier(subject) and cid in checkpoint.get('selected_claim_ids',[]) and cid in claims,'IDENTITY_SELECTED_BINDING')
        c=claims[cid];noncircular(c);ctype=key.replace('_id','_identity')
        require(c.get('claim_type')==ctype and evidence_audit.is_asserted(c) and c.get('subject_id')==subject,'IDENTITY_SUBJECT_MISMATCH')
        require(c.get('origin')=='general_identity' and bool(c.get('evidence_ids')),'CIRCULAR_IDENTITY_CLAIM')
        selected=[q for q in claims.values() if q.get('claim_type')==ctype and q.get('claim_id') in checkpoint.get('selected_claim_ids',[]) and evidence_audit.is_asserted(q)]
        require(len(selected)==1 and selected[0]['claim_id']==cid,'AMBIGUOUS_IDENTITY_BINDING')
        for eid in c['evidence_ids']:evidence(eid)
        ancestry=set()
        def collect(eid):
            if eid in ancestry:return
            ancestry.add(eid)
            for parent in emap[eid]['ancestor_evidence_ids']:collect(parent)
        for eid in c['evidence_ids']:collect(eid)
        snapshots[key]={'claim':copy.deepcopy(c),'evidence':{eid:copy.deepcopy(emap[eid]) for eid in sorted(ancestry)}}
        ids.append(cid)
    require(set(binding['claims'])<=set(binding['scope']),'IDENTITY_BINDING_FIELDS')
    return {'checkpoint_sha256':digest(snapshots),'binding_sha256':digest(binding),'identity_state':state,'claim_ids':ids,'scope':copy.deepcopy(binding['scope']),'identity_snapshots':snapshots}

def scoped_license(license,m):
    keys=['work_id']+(['edition_id'] if m['level']!='WORK' else [])+(['exemplar_id'] if m['level']=='EXEMPLAR' else [])
    snapshots={k:license['identity_snapshots'][k] for k in keys}
    bound={k:license['scope'][k] if k in keys else None for k in license['scope']}
    return {'checkpoint_sha256':digest(snapshots),'binding_sha256':digest(bound),'identity_state':m['required_identity_state'],'claim_ids':[snapshots[k]['claim']['claim_id'] for k in keys],'scope':bound}

def activate(reg,rid,checkpoint,binding):
    validate(reg);require(rid in reg['records'],'RECORD_UNAVAILABLE');r=reg['records'][rid];m=r['manifest']
    license=identity_license(checkpoint,binding)
    require(r['status']=='CURRENT','SPECIALIZATION_STATE_'+r['status'])
    require(evidence_audit.IDENTITY_STATES.index(license['identity_state'])>=evidence_audit.IDENTITY_STATES.index(m['required_identity_state']),'SPECIALIZATION_UNLICENSED')
    require(matches(m['scope'],license['scope']),'SPECIALIZATION_WRONG_SUBJECT')
    licensed=scoped_license(license,m)
    if r['license'] is not None:require(r['license']==licensed,'LICENSE_REVALIDATION_REQUIRED')
    return licensed

def route(reg,checkpoint,binding):
    validate(reg);identity_license(checkpoint,binding);result=[]
    for rid in reg['records']:
        try:activate(reg,rid,checkpoint,binding);result.append(rid)
        except SpecializationError:continue
    # Two current manifests for the exact same level/scope require explicit conflict resolution.
    scopes=[digest([reg['records'][rid]['manifest']['level'],reg['records'][rid]['manifest']['scope']]) for rid in result]
    require(len(scopes)==len(set(scopes)),'AMBIGUOUS_SPECIALIZATION_ROUTE')
    return result

def license_record(reg,rid,checkpoint,binding,expected,reason):
    license=activate(reg,rid,checkpoint,binding)
    def edit(out):
        r=out['records'][rid];r['license']=license;r['revision']+=1;r['state_version']+=1;r['updated_revision']=out['revision'];propagate(out)
    return mutate(reg,expected,'LICENSE_RECORD',reason,edit)

def put_claim(reg,rid,cid,claim,expected,reason):
    def edit(out):
        require(rid in out['records'],'RECORD_UNAVAILABLE');r=out['records'][rid];require(r['status']=='CURRENT' and r['license'] is not None,'CLAIM_REQUIRES_LICENSE')
        old=r['claims'].get(cid);require(claim['revision']==(old['revision']+1 if old else 1),'CLAIM_REVISION_CONFLICT')
        r['claims'][cid]=copy.deepcopy(claim);r['state_version']+=1;r['updated_revision']=out['revision'];propagate(out)
    return mutate(reg,expected,'UPDATE_CLAIM',reason,edit)

def revise_record(reg,rid,m,expected,reason):
    manifest(m)
    def edit(out):
        require(rid in out['records'] and m['specialization_id']==rid,'RECORD_UNAVAILABLE');r=out['records'][rid]
        require(m['scope']==r['manifest']['scope'] and m['level']==r['manifest']['level'],'REPLACEMENT_SUBJECT_CHANGE')
        r['manifest']=copy.deepcopy(m);r['license']=None;r['revision']+=1;r['state_version']+=1;r['updated_revision']=out['revision'];r['status']='STALE';propagate(out)
    return mutate(reg,expected,'REPLACE_RECORD',reason,edit)

def mark(reg,key,status,expected,reason):
    require(status in STATUSES-{'CURRENT'},'INVALIDATION_STATUS')
    def edit(out):
        if key in out['anchors']:item=out['anchors'][key]
        elif key.startswith('record:'):item=out['records'][key.split(':')[1]]
        elif key.startswith('claim:'):
            parts=key.split(':');item=out['records'][parts[1]]['claims'][parts[2]]
        else:raise SpecializationError('INVALIDATION_TARGET')
        item['status']=status;item['revision']+=1
        for r in out['records'].values():
            if item is r or any(item is c for c in r['claims'].values()):r['updated_revision']=out['revision']
        propagate(out)
    return mutate(reg,expected,'MARK_'+status,reason,edit)

def supersede(reg,old_id,new_manifest_value,expected,reason):
    m=manifest(new_manifest_value)
    def edit(out):
        require(old_id in out['records'] and m['specialization_id'] not in out['records'],'SUPERSESSION_TARGET')
        old=out['records'][old_id];require(old['manifest']['scope']==m['scope'] and old['manifest']['level']==m['level'],'SUPERSESSION_SUBJECT')
        old['status']='SUPERSEDED';old['revision']+=1;old['updated_revision']=out['revision']
        out['records'][m['specialization_id']]={'manifest':copy.deepcopy(m),'revision':1,'state_version':1,'created_revision':out['revision'],'updated_revision':out['revision'],'status':'CURRENT','supersedes':old_id,'license':None,'dependencies':{d:snapshot(nodes(out)[d]) for d in m['invalidation_dependencies']},'claims':{}};propagate(out)
    return mutate(reg,expected,'SUPERSEDE_RECORD',reason,edit)

def reconcile_identity(reg,checkpoint,binding,expected,reason,previous_scope=None):
    current=identity_license(checkpoint,binding)
    affected_scope=previous_scope or binding['scope'];scope(affected_scope)
    def edit(out):
        for rid,r in out['records'].items():
            if r['license'] is None or r['status']!='CURRENT':continue
            m=r['manifest'];old=r['license']
            # Unrelated scopes are outside this identity correction operation.
            if old['scope']['work_id']!=affected_scope['work_id']:continue
            rank=evidence_audit.IDENTITY_STATES.index(current['identity_state'])
            threshold=evidence_audit.IDENTITY_STATES.index(m['required_identity_state'])
            affected=rank<threshold or not matches(m['scope'],current['scope'])
            if affected:r['status']='INVALIDATED';r['revision']+=1;r['updated_revision']=out['revision']
            elif old!=scoped_license(current,m):
                # Bind only licensing claims/evidence, not unrelated checkpoint text.
                r['status']='STALE';r['revision']+=1;r['updated_revision']=out['revision']
        propagate(out)
    return mutate(reg,expected,'RECONCILE_IDENTITY',reason,edit)

def revalidate_record(reg,rid,checkpoint,binding,expected,reason):
    # Revalidation requires fresh general identity evidence, fresh dependency snapshots,
    # and separately revalidated claims. It does not revive prior conclusions.
    license=identity_license(checkpoint,binding)
    def edit(out):
        r=out['records'][rid];m=r['manifest'];
        require(evidence_audit.IDENTITY_STATES.index(license['identity_state'])>=evidence_audit.IDENTITY_STATES.index(m['required_identity_state']),'SPECIALIZATION_UNLICENSED')
        scoped=scoped_license(license,m);validate_license(scoped,m)
        require(r['status'] not in {'RETIRED','SUPERSEDED'},'REVALIDATION_RETIRED')
        n=nodes(out);require(all(n[d]['status']=='CURRENT' for d in r['dependencies']),'REVALIDATION_DEPENDENCY')
        r['dependencies']={d:snapshot(n[d]) for d in r['dependencies']};r['license']=scoped;r['status']='CURRENT';r['revision']+=1;r['state_version']+=1;r['updated_revision']=out['revision'];propagate(out)
    return mutate(reg,expected,'REVALIDATE_RECORD',reason,edit)

def read_claim(reg,rid,cid,checkpoint,binding,integrity=None):
    activate(reg,rid,checkpoint,binding);r=reg['records'][rid];c=r['claims'].get(cid)
    require(r['license'] is not None,'CLAIM_REQUIRES_LICENSE')
    require(c is not None and c['status']=='CURRENT','CLAIM_UNAVAILABLE_OR_STALE')
    # Caller must rebind corrected licensing evidence before consuming accumulated facts.
    current=scoped_license(identity_license(checkpoint,binding),r['manifest'])
    require(r['license']==current,'LICENSE_REVALIDATION_REQUIRED')
    if c['surface']=='physical_history':
        pl=c['physical_license'];require(pl==physical_license(checkpoint,pl['claim_id']) and any(q['claim_id']==pl['claim_id'] and q.get('value')==c['value'] for q in checkpoint['claims']),'PHYSICAL_HISTORY_REVALIDATION')
    def inspect(dep,seen):
        if dep in seen:return
        seen.add(dep)
        if dep in reg['anchors']:
            ref=reg['anchors'][dep]['source_ref']
            if ref:
                require(integrity is not None,'SPECIALIZATION_SOURCE_CONTEXT_REQUIRED')
                require(integrity.parent_snapshot(ref['representation_id'],ref['span_ids'])==ref['snapshot'],'SPECIALIZATION_SOURCE_STALE')
                integrity.permit(ref['representation_id'],ref['purpose'],ref['span_ids'])
                if ref['proposition_id'] is not None:
                    require(integrity.argument.proposition_snapshot(ref['proposition_id'])==ref['proposition_snapshot'],'SPECIALIZATION_PROPOSITION_STALE')
                    integrity.argument.permit_proposition(ref['proposition_id'],ref['purpose']=='SECURE_AUTHOR_POSITION')
        else:
            parts=dep.split(':');r=reg['records'][parts[1]];obj=r if parts[0]=='record' else r['claims'][parts[2]]
            for d in obj['dependencies']:inspect(d,seen)
    for dep in c['dependencies']:inspect(dep,set())
    return copy.deepcopy(c)

def reconcile_sources(reg,integrity,expected,reason):
    def edit(out):
        for a in out['anchors'].values():
            ref=a['source_ref']
            if ref is None:continue
            try:now=integrity.parent_snapshot(ref['representation_id'],ref['span_ids'])
            except (ValueError,KeyError):now=None
            if ref['proposition_id'] is not None:
                try:
                    if integrity.argument.proposition_snapshot(ref['proposition_id'])!=ref['proposition_snapshot']:now=None
                except (ValueError,KeyError):now=None
            if now!=ref['snapshot'] and a['status']=='CURRENT':a['status']='STALE';a['revision']+=1
        propagate(out)
    return mutate(reg,expected,'RECONCILE_SOURCES',reason,edit)

def physical_license(checkpoint,claim_id):
    errors=evidence_audit.audit_checkpoint(checkpoint);require(not errors,'GENERAL_PHYSICAL_AUDIT: '+'; '.join(errors))
    claim=next((c for c in checkpoint.get('claims',[]) if c['claim_id']==claim_id),None)
    require(claim is not None and evidence_audit.is_asserted(claim) and evidence_audit.physical_history_kind(claim) is not None and claim.get('origin')=='general_evidence','PHYSICAL_HISTORY_GENERAL_LICENSE')
    emap={e['evidence_id']:e for e in checkpoint['evidence']}
    require(bool(claim.get('evidence_ids')) and all(emap[e].get('origin')=='general_evidence' for e in claim['evidence_ids']),'PHYSICAL_HISTORY_EVIDENCE_ORIGIN')
    return {'claim_id':claim_id,'checkpoint_sha256':digest({'claim':claim,'evidence':{e:emap[e] for e in claim['evidence_ids']}}),'evidence_ids':claim['evidence_ids']}

PROFILE = 'source-linked-user-correction-1'

def correction_projection(value):
    """One publication-only profile; storage admission remains unchanged."""
    require(isinstance(value,dict) and set(value)=={'claim','scope','correction','depends_on_wording','witness_comparison'},'SPECIALIZATION_PROJECTION_SHAPE')
    c=value['correction'];w=value['depends_on_wording'];n=value['witness_comparison']
    require(isinstance(c,dict) and set(c)=={'kind','applies_to','replaced','with','supersedes_claim'},'SPECIALIZATION_PROJECTION_CORRECTION')
    require(isinstance(w,dict) and set(w)=={'phrase','reading','representation_id','representation_revision','span_id'},'SPECIALIZATION_PROJECTION_WORDING')
    require(isinstance(n,dict) and set(n)=={'status','note'},'SPECIALIZATION_PROJECTION_WITNESS')
    a=c['applies_to']
    require(isinstance(a,dict) and set(a)=={'representation_id','revision','span_id'},'SPECIALIZATION_PROJECTION_LOCATION')
    require(c['kind']=='EXPLICIT_USER_CORRECTION' and n['status']=='USER_CORRECTION_NOT_WITNESS_REPAIR','SPECIALIZATION_PROJECTION_STATUS')
    texts=[value['claim'],value['scope'],c['replaced'],c['with'],w['phrase'],w['reading'],n['note']]
    require(all(isinstance(t,str) and bool(t.strip()) and not any(ord(ch)<32 or ch in '<>`*_~' or 0x202a<=ord(ch)<=0x202e or 0x2066<=ord(ch)<=0x2069 for ch in t) for t in texts),'SPECIALIZATION_PROJECTION_TEXT')
    require(all(identifier(x) for x in [a['representation_id'],a['span_id'],c['supersedes_claim']]) and ':' not in c['supersedes_claim'],'SPECIALIZATION_PROJECTION_ID')
    require(revision(a['revision']) and a['revision']>1 and type(w['representation_revision']) is int and w['representation_revision']==a['revision'] and w['representation_id']==a['representation_id'] and w['span_id']==a['span_id'],'SPECIALIZATION_PROJECTION_LOCATION_BINDING')
    require(c['replaced']!=c['with'] and c['with'] in w['phrase'] and w['reading'] in c['with'],'SPECIALIZATION_PROJECTION_READING')
    # Fixed labels preserve the distinction even if free-text scope is brief.
    return ('Claim: '+value['claim']+'\nScope: '+value['scope']+
            '\nEvidence scope: supplied corrected representation only; no edition, exemplar or original-wording claim.'+
            '\nCorrection status: EXPLICIT_USER_CORRECTION (USER correction; NOT a witness repair).'+
            '\nReplaced wording: '+c['replaced']+'\nCorrected wording: '+c['with']+
            '\nSource location: representation '+a['representation_id']+'; revision '+str(a['revision'])+'; span '+a['span_id']+
            '\nWording dependency: '+w['phrase']+'\nReading: '+w['reading']+
            '\nWitness status: USER_CORRECTION_NOT_WITNESS_REPAIR.'+
            '\nWitness limitation: '+n['note'])

def governed_correction_projection(reg,rid,cid,checkpoint,binding,integrity):
    """Bind the projection to authentic cumulative evidence and a current license."""
    from specialization_evidence import recover_claim,current_capsule,validate_capsule
    from hti_core.specialization_onboarding import check_ref
    claim=read_claim(reg,rid,cid,checkpoint,binding,integrity)
    text=correction_projection(claim['value']);r=reg['records'][rid];m=r['manifest'];v=claim['value'];a=v['correction']['applies_to'];w=v['depends_on_wording']
    require(m['level']=='WORK' and claim['surface']=='research_index','SPECIALIZATION_PROJECTION_SCOPE')
    recovered=recover_claim(reg,rid,cid)
    require(recovered['integrity'] is not None and recovered['work_id']==checkpoint['work_id']==integrity.work_id,'SPECIALIZATION_PROJECTION_CLOSURE')
    general=[p for p in recovered['general_material'] if p['claim'].get('claim_id')==cid and p['claim'].get('value')==v]
    require(len(general)==1,'SPECIALIZATION_PROJECTION_GENERAL')
    g=general[0]['claim']
    require(g.get('claim_type')=='research_claim' and g.get('onboarding_field')=='research_ledger' and g.get('scope')==m['scope'] and g.get('status') in {'asserted','verified','secure'},'SPECIALIZATION_PROJECTION_GENERAL')
    require(all(e.get('kind')=='explicit_user_correction' and e.get('identity_admissible') is False and e.get('status')=='CURRENT' for e in general[0]['evidence'].values()),'SPECIALIZATION_PROJECTION_USER_EVIDENCE')
    sid=a['representation_id'];span=a['span_id']
    require(sid in integrity.nodes and sid in recovered['integrity'].nodes,'SPECIALIZATION_PROJECTION_SOURCE')
    node=integrity.nodes[sid];captured=recovered['integrity'].nodes[sid]
    require(digest(node)==digest(captured) and node['revision']==a['revision'] and node['type']=='NORMALIZED_TRANSCRIPTION' and node['supply_status']=='SUPPLIED','SPECIALIZATION_PROJECTION_SOURCE_BINDING')
    spans=integrity.spans(sid);require(span in spans and spans[span]['state']=='VISIBLE' and w['phrase'] in spans[span]['text'],'SPECIALIZATION_PROJECTION_SPAN')
    provenance=node['provenance'];corr=provenance.get('correction',{})
    require(corr.get('kind')==v['correction']['kind'] and corr.get('replaced')==v['correction']['replaced'] and corr.get('with')==v['correction']['with'] and corr.get('witness_repair') is False and corr.get('other_wording_changed') is False,'SPECIALIZATION_PROJECTION_SOURCE_CORRECTION')
    oldid=v['correction']['supersedes_claim'];old=r['claims'].get(oldid)
    require(oldid!=cid and old is not None and old['status'] in {'STALE','INVALIDATED','SUPERSEDED'} and old['surface']=='research_index','SPECIALIZATION_PROJECTION_LINEAGE')
    oldv=old['value'];ow=oldv.get('depends_on_wording',{}) if isinstance(oldv,dict) else {}
    require(ow.get('representation_id')==sid and ow.get('span_id')==span and isinstance(ow.get('reading'),str) and ow['reading'] in v['correction']['replaced'],'SPECIALIZATION_PROJECTION_LINEAGE')
    old_general=[]
    for dep in old['dependencies']:
        anchor=reg['anchors'].get(dep)
        if not anchor or anchor['source_ref'] is not None:continue
        for capsule in anchor.get('evidence_history',[]):
            validate_capsule(capsule,dep)
            if capsule['kind']=='GENERAL':
                g=capsule['payload']['claim']
                if g.get('claim_id')==oldid and g.get('value')==oldv and g.get('scope')==m['scope'] and g.get('onboarding_field')=='research_ledger':old_general.append(capsule['sha256'])
    require(bool(old_general),'SPECIALIZATION_PROJECTION_LINEAGE_GENERAL')
    previous=[]
    for dep in old['dependencies']:
        anchor=reg['anchors'].get(dep)
        if not anchor or anchor['source_ref'] is None:continue
        for capsule in anchor.get('evidence_history',[]):
            validate_capsule(capsule,dep)
            if capsule['kind']!='SOURCE':continue
            p=capsule['payload'];ref=p['ref'];raw=p['integrity']
            if ref['representation_id']!=sid or span not in ref['span_ids'] or raw['work_id']!=m['scope']['work_id']:continue
            from source_integrity import IntegrityRegistry
            historical=IntegrityRegistry(raw);check_ref(historical,ref);hn=historical.nodes[sid]
            if hn['revision']!=provenance.get('revised_from_revision') or hn['revision']>=node['revision']:continue
            hs=historical.spans(sid)[span]['text']
            if hs.count(v['correction']['replaced'])==1 and hs.replace(v['correction']['replaced'],v['correction']['with'],1)==spans[span]['text'] and isinstance(ow.get('phrase'),str) and ow['phrase'] in hs:
                previous.append(capsule['sha256'])
    require(bool(previous),'SPECIALIZATION_PROJECTION_LINEAGE_SOURCE')
    return text


def validate_completion(directory: Path,checkpoint: dict,rendered_text=None):
    """Current installed readiness and independently owned specialized output."""
    import task_state
    from specialization_resources import validate_readiness
    path = directory/'specialization-context.json'
    require(path.is_file() and not path.is_symlink(), 'INSTALLED_READINESS_REQUIRED')
    context = json.loads(path.read_text())
    primary = validate_primary(context, checkpoint)
    publication = task_state.require_ready(directory)
    draft = task_state.current_draft(directory, publication)
    require(draft is not None and draft['inputs'].get(path.name) == hashlib.sha256(path.read_bytes()).hexdigest(), 'INSTALLED_READINESS_NOT_STAGED')
    installed = validate_readiness(directory, context, checkpoint)
    used = [c for c in checkpoint.get('claims', []) if c.get('origin') in {'specialization','specialization_fact','specialization_inference'}]
    require(len({c['claim_id'] for c in used}) == len(used), 'DUPLICATE_SPECIALIZATION_OUTPUT')
    views = [primary] + ([installed] if installed is not None else [])
    owned = [(view, use) for view in views for use in view['uses']]
    require(all(isinstance(u, dict) and set(u) == {'record_id','claim_id','output_claim_id','claim_sha256'} for _,u in owned), 'SPECIALIZATION_USE_FIELDS')
    require(len({u['output_claim_id'] for _,u in owned}) == len(owned), 'DUPLICATE_SPECIALIZATION_USE')
    require({u['output_claim_id'] for _,u in owned} == {c['claim_id'] for c in used}, 'SPECIALIZATION_USE_UNBOUND')
    import source_integrity
    integrity=source_integrity.IntegrityRegistry(json.loads((directory/'source-integrity.json').read_text()))
    referenced_claims=set()
    for owner, use in owned:
        reg = owner['registry']; binding = owner['identity_binding']
        require(owner['storage_state'] in {'NATIVE_BOUND','PORTABLE_IMPORTED','INSTALLED_READ_ONLY'} and reg is not None, 'SPECIALIZATION_STATE_UNAVAILABLE')
        require(set(use)=={'record_id','claim_id','output_claim_id','claim_sha256'},'SPECIALIZATION_USE_FIELDS')
        claim=read_claim(reg,use['record_id'],use['claim_id'],checkpoint,binding,integrity)
        require(digest(claim)==use['claim_sha256'],'SPECIALIZATION_CLAIM_INTEGRITY')
        output=next((c for c in used if c['claim_id']==use['output_claim_id']),None)
        require(output is not None and output.get('specialization_ref')=={'record_id':use['record_id'],'claim_id':use['claim_id']} and output.get('value')==claim['value'],'SPECIALIZATION_OUTPUT_BINDING')
        if not isinstance(claim['value'],str):
            projection=governed_correction_projection(reg,use['record_id'],use['claim_id'],checkpoint,binding,integrity)
            if rendered_text is not None:
                # Reuse the same renderer against the current staged plan. Caller
                # prose or forged span metadata cannot substitute for projection.
                import finalize_response
                plan=json.loads((directory/'final-response-plan.json').read_text())
                finalized,expected_text=finalize_response.finalize(checkpoint,plan)
                require(rendered_text==expected_text,'SPECIALIZATION_PROJECTION_RENDERER_BINDING')
                spans=finalized['output']['final_response']['spans']
                projected=[s for s in spans if s.get('claim_id')==output['claim_id'] and s.get('projection_profile')==PROFILE]
                require(bool(projected) and all(s.get('specialization_ref')==output['specialization_ref'] and s.get('value_sha256')==digest(claim['value']) and s['text']==projection and rendered_text[s['start']:s['end']]==projection for s in projected),'SPECIALIZATION_CLAIM_NOT_VISIBLE')
        elif rendered_text is not None:
            require(claim['value'] in rendered_text,'SPECIALIZATION_CLAIM_NOT_VISIBLE')
        referenced_claims.add(output['claim_id'])
    require(referenced_claims=={c['claim_id'] for c in used},'SPECIALIZATION_USE_UNBOUND')
