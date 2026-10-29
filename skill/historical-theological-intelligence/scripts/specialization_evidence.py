"""Recoverable specialization evidence over existing anchors and validators.

Recovery supplies historical research context, never current-source identity.
Storage remains the existing guarded registry envelope or explicit bundle.
"""
from __future__ import annotations
import copy
import specialization_core as core

SCHEMA='hti-specialization-evidence-1'

def capsule(work,kind,payload):
    body={'schema_version':SCHEMA,'work_id':work,'kind':kind,'payload':copy.deepcopy(payload)}
    return {**body,'sha256':core.digest(body)}

def validate_capsule(value,aid):
    from source_integrity import IntegrityRegistry
    from hti_core.specialization_onboarding import check_ref,general_evidence,anchor_prefix
    core.require(isinstance(value,dict) and set(value)=={'schema_version','work_id','kind','payload','sha256'},'EVIDENCE_CLOSURE_FIELDS')
    core.require(value['schema_version']==SCHEMA,'EVIDENCE_CLOSURE_SCHEMA')
    core.require(core.identifier(value['work_id']) and aid.startswith(anchor_prefix(value['work_id'])),'EVIDENCE_CLOSURE_WORK')
    core.require(value['sha256']==core.digest({k:v for k,v in value.items() if k!='sha256'}),'EVIDENCE_CLOSURE_HASH')
    p=value['payload']
    if value['kind']=='SOURCE':
        core.require(isinstance(p,dict) and set(p)=={'integrity','ref'},'EVIDENCE_CLOSURE_SOURCE')
        registry=IntegrityRegistry(p['integrity'])
        core.require(registry.work_id==value['work_id'],'EVIDENCE_CLOSURE_WORK')
        check_ref(registry,p['ref'])
    elif value['kind']=='GENERAL':
        core.require(isinstance(p,dict) and set(p)=={'claim','evidence'},'EVIDENCE_CLOSURE_GENERAL')
        c=p['claim'];core.scope(c['scope'])
        core.require(c['scope']['work_id']==value['work_id'] and c.get('origin')=='general_evidence' and not any(k in c for k in ('specialization_ref','specialization_id','storage_binding')),'EVIDENCE_CLOSURE_GENERAL_ORIGIN')
        core.require(isinstance(p['evidence'],dict),'EVIDENCE_CLOSURE_GENERAL')
        ev=general_evidence({'evidence':list(p['evidence'].values())},c['evidence_ids'])
        core.require(ev==p['evidence'],'EVIDENCE_CLOSURE_ANCESTRY')
    else:core.require(False,'EVIDENCE_CLOSURE_KIND')
    return value

def semantic_hash(value):
    p=value['payload']
    return core.digest(p['ref'] if value['kind']=='SOURCE' else p)

def validate_history(aid,history):
    core.require(isinstance(history,list) and bool(history),'EVIDENCE_CLOSURE_HISTORY')
    seen=set()
    for value in history:
        validate_capsule(value,aid)
        core.require(value['sha256'] not in seen,'EVIDENCE_CLOSURE_DUPLICATE')
        seen.add(value['sha256'])

def append(reg,aid,value,expected,reason):
    """Attach authentic reviewed context without asserting a source correction."""
    core.validate(reg);core.require(aid in reg['anchors'],'EVIDENCE_CLOSURE_ANCHOR')
    validate_capsule(value,aid);a=reg['anchors'][aid]
    core.require(semantic_hash(value)==a['sha256'],'EVIDENCE_CLOSURE_BINDING')
    core.require((value['kind']=='SOURCE')==(a['source_ref'] is not None),'EVIDENCE_CLOSURE_ANCHOR_KIND')
    if value['kind']=='SOURCE':core.require(value['payload']['ref']==a['source_ref'],'EVIDENCE_CLOSURE_BINDING')
    if any(v['sha256']==value['sha256'] for v in a.get('evidence_history',[])):return reg
    def edit(out):out['anchors'][aid].setdefault('evidence_history',[]).append(copy.deepcopy(value))
    return core.mutate(reg,expected,'APPEND_EVIDENCE_CLOSURE',reason,edit)

def current_capsule(reg,aid,work):
    a=reg['anchors'][aid]
    core.require(a['status']=='CURRENT','EVIDENCE_CLOSURE_STALE')
    for value in reversed(a.get('evidence_history',[])):
        if value['work_id']==work and semantic_hash(value)==a['sha256']:
            if value['kind']=='SOURCE' and value['payload']['ref']!=a['source_ref']:continue
            return value
    core.require(False,'LEGACY_EVIDENCE_CLOSURE_MISSING')

def recover_claim(reg,rid,cid):
    """Return validated context for one current claim; grants no activation.

    Call stock read_claim with independent current identity and the returned
    integrity. Missing legacy context remains unavailable, never synthesized.
    """
    from source_integrity import IntegrityRegistry
    from hti_core.specialization_onboarding import check_ref
    core.validate(reg);r=reg['records'][rid];c=r['claims'][cid]
    core.require(r['status']=='CURRENT' and c['status']=='CURRENT','EVIDENCE_CLOSURE_STALE')
    work=r['manifest']['scope']['work_id'];sources=[];general=[];seen=set()
    def visit(dep):
        if dep in seen:return
        seen.add(dep)
        if dep not in reg['anchors']:
            parts=dep.split(':');record=reg['records'][parts[1]]
            core.require(record['manifest']['scope']['work_id']==work,'EVIDENCE_CLOSURE_WORK')
            obj=record if parts[0]=='record' else record['claims'][parts[2]]
            for d in obj['dependencies']:visit(d)
            return
        a=reg['anchors'][dep]
        if a['source_ref'] is None:
            if a.get('evidence_history'):general.append(copy.deepcopy(current_capsule(reg,dep,work)['payload']))
            return
        sources.append(current_capsule(reg,dep,work)['payload'])
    for dep in c['dependencies']:visit(dep)
    integrity=None
    if sources:
        # A claim's captured complete source registry must cover all its source
        # dependencies. Conflicting historical contexts require reviewed update.
        for source in sources:
            candidate=IntegrityRegistry(source['integrity'])
            try:
                for item in sources:check_ref(candidate,item['ref'])
            except (ValueError,KeyError,TypeError):continue
            integrity=candidate;break
        core.require(integrity is not None,'EVIDENCE_CLOSURE_CONTEXT_REVIEW_REQUIRED')
    return {'integrity':integrity,'general_material':general,'work_id':work,'activation_granted':False}
