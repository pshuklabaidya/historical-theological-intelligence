"""Evidence-governed onboarding over the existing specialization and storage cores.

This coordinator contains no catalog facts, host tools, locator discovery, or
persistent filesystem backend. Native state lives behind the accepted adapter.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import evidence_audit as audit
import specialization_core as core
import specialization_storage as storage

SCHEMA = 'hti-specialization-onboarding-1'
FILE = 'hti-specialization-onboarding.json'
FIELDS = {
 'bibliographic_evidence': {'WORK':'bibliography','EDITION':'edition_bibliography'},
 'known_witnesses': {'WORK':'witness_relations','EDITION':'edition_witness_relations'},
 'historical_translations': {'WORK':'witness_relations'},
 'source_relationships': {'WORK':'source_findings'},
 'typography_notes': {'EDITION':'typography'},
 'physical_copy_observations': {'EXEMPLAR':'condition'},
 'physical_history': {'EXEMPLAR':'physical_history'},
 'argument_dossiers': {'WORK':'argument_research'},
 'whole_work_cartography': {'WORK':'argument_research'},
 'historical_relations': {'WORK':'source_findings'},
 'novelty_records': {'WORK':'source_findings'},
 'transmission_records': {'WORK':'source_findings'},
 'research_ledger': {'WORK':'research_index'},
}
PROPOSITION_FIELDS = {'argument_dossiers','historical_relations','whole_work_cartography','novelty_records','transmission_records'}
SOURCE_FIELDS = set(FIELDS)-{'bibliographic_evidence','research_ledger'}

def text(value):return isinstance(value,str) and bool(value.strip())
def clone(value):return copy.deepcopy(value)
def record_id(subject,level):return 'onboard-'+level.lower()+'-'+core.digest(subject)[:24]
def selected_record(reg,subject,level):
 candidates=[rid for rid,r in reg['records'].items() if r['manifest']['scope']==subject and r['manifest']['level']==level and r['status'] not in {'SUPERSEDED','RETIRED'}]
 core.require(len(candidates)<=1,'ONBOARD_AMBIGUOUS_SPECIALIZATION')
 return candidates[0] if candidates else record_id(subject,level)

def scoped(subject,level):
 return {k:v if k=='work_id' or k=='edition_id' and level!='WORK' or k=='exemplar_id' and level=='EXEMPLAR' else None for k,v in subject.items()}
def anchor_prefix(work):return 'evidence:onboard.'+core.digest(work)[:24]+'.'
def begin(id_,request,holding_report=None):
 core.require(core.identifier(id_) and text(request),'ONBOARD_INITIAL_INPUT')
 core.require(holding_report is None or text(holding_report),'HOLDING_REPORT')
 return {'schema_version':SCHEMA,'id':id_,'request':request,'holding':{'report':holding_report,'state':'USER_REPORTED' if holding_report else 'NOT_REPORTED','bibliographic_identity_evidence':False,'physical_history_verified':False},'identity_binding':None,'identity_sha256':None,'edition_candidates':[],'entries':[],'registry':None,'storage_state':'NO_PERSISTENT_STATE','storage_receipt':None,'needed_evidence':[]}

def shape(doc):
 core.require(isinstance(doc,dict) and set(doc)==set(begin('shape','shape')) and doc['schema_version']==SCHEMA,'ONBOARD_SCHEMA')
 core.require(core.identifier(doc['id']) and text(doc['request']),'ONBOARD_INPUT')
 h=doc['holding'];core.require(isinstance(h,dict) and set(h)=={'report','state','bibliographic_identity_evidence','physical_history_verified'} and h['state'] in {'USER_REPORTED','NOT_REPORTED'} and h['bibliographic_identity_evidence'] is False and h['physical_history_verified'] is False and ((h['state']=='USER_REPORTED' and text(h['report'])) or (h['state']=='NOT_REPORTED' and h['report'] is None)),'HOLDING_IS_REPORT_ONLY')
 core.require(isinstance(doc['entries'],list) and isinstance(doc['edition_candidates'],list) and isinstance(doc['needed_evidence'],list) and all(text(x) for x in doc['needed_evidence']),'ONBOARD_COLLECTIONS')
 core.require(len({(x['level'],x['claim_id']) for x in doc['entries']})==len(doc['entries']),'ONBOARD_DUPLICATE_ENTRY')
 for e in doc['entries']:
  core.require(isinstance(e,dict) and set(e)=={'field','level','scope','claim_id','source_refs','depends_on'} and e['field'] in FIELDS and e['level'] in FIELDS[e['field']] and core.identifier(e['claim_id']) and ':' not in e['claim_id'] and isinstance(e['source_refs'],list) and isinstance(e['depends_on'],list) and all(core.identifier(k) for k in e['depends_on']),'ONBOARD_ENTRY')
  core.scope(e['scope'],e['level'])
 for c in doc['edition_candidates']:
  core.require(isinstance(c,dict) and set(c)=={'edition_id','evidence_ids','note'} and core.identifier(c['edition_id']) and isinstance(c['evidence_ids'],list) and bool(c['evidence_ids']) and text(c['note']),'EDITION_CANDIDATE')
 return doc

def general_evidence(checkpoint,ids):
 emap={e['evidence_id']:e for e in checkpoint['evidence']};out={};visiting=set()
 def walk(eid):
  core.require(eid in emap and eid not in visiting,'ONBOARD_EVIDENCE_ANCESTRY')
  if eid in out:return
  e=emap[eid];core.require(e.get('origin')=='general_evidence' and e.get('status','CURRENT')=='CURRENT' and e.get('kind') not in {'storage_locator','model_memory','user_report','holding_report'} and e.get('identity_admissible') is not None,'ONBOARD_GENERAL_EVIDENCE')
  core.require(isinstance(e.get('ancestor_evidence_ids'),list),'ONBOARD_EVIDENCE_ANCESTRY')
  visiting.add(eid)
  for p in e['ancestor_evidence_ids']:walk(p)
  visiting.remove(eid);out[eid]=clone(e)
 for eid in ids:walk(eid)
 return out

def general_claim(checkpoint,cid,field,subject):
 c=next((c for c in checkpoint['claims'] if c['claim_id']==cid),None)
 core.require(c is not None and c.get('origin')=='general_evidence' and audit.is_asserted(c) and c.get('status') not in {'STALE','INVALIDATED'} and bool(c.get('evidence_ids')),'ONBOARD_GENERAL_CLAIM')
 core.require(c.get('onboarding_field')==field and c.get('scope')==subject and 'value' in c,'ONBOARD_CLAIM_SCOPE')
 core.require(not any(k in c for k in ('specialization_ref','specialization_id','storage_binding')),'ONBOARD_CIRCULAR_CLAIM')
 if field=='physical_history':core.physical_license(checkpoint,cid)
 if field=='physical_copy_observations':
  core.require(c.get('claim_layer')=='physical_observation' and not audit.physical_history_kind(c),'ONBOARD_PHYSICAL_OBSERVATION')
 validate_research_value(field,c['value'],subject)
 return c,general_evidence(checkpoint,c['evidence_ids'])

def validate_research_value(field,value,subject):
 work=subject['work_id']
 if field in {'known_witnesses','historical_translations','source_relationships'}:
  core.require(isinstance(value,dict) and value.get('work_id')==work,'ONBOARD_WITNESS_SCOPE')
  if field=='source_relationships':core.require(set(value)>={'edge_id','from','to','relationship'} and value['relationship'] in {'same_setting_as','derived_from','translation_of','quotes','corrects','unknown_relation'},'ONBOARD_WITNESS_EDGE')
  else:core.require(set(value)>={'witness_id','work_id','type','locator','access_status','independence_group'} and all(text(value[k]) for k in ['witness_id','type','locator','access_status','independence_group']),'ONBOARD_WITNESS_FIELDS')
 if field in {'argument_dossiers','historical_relations'}:
  from .cartography import Cartography
  core.require(isinstance(value,dict) and set(value)=={'dataset'} and value['dataset']['integrity']['work_id']==work,'ONBOARD_RESEARCH_SCOPE')
  Cartography({'schema_version':'hti-cartography-1','datasets':[value['dataset']],'corpora':[],'maps':[],'comparisons':[]})
  if field=='historical_relations':core.require(value['dataset']['historical_graph'] is not None,'ONBOARD_HISTORICAL_GRAPH')
 if field=='whole_work_cartography':
  from .cartography import Cartography
  obj=Cartography(value);core.require(bool(obj.raw['maps']) and all(c['work_id']==work for c in obj.raw['corpora']),'ONBOARD_RESEARCH_SCOPE')
 if field=='novelty_records':
  from .novelty import Novelty
  obj=Novelty(value);core.require(bool(obj.claims) and all(obj.evidence.registries[obj.objects[c['object_id']]['dataset_id']].work_id==work for c in obj.claims.values()),'ONBOARD_RESEARCH_SCOPE')
 if field=='transmission_records':
  from .historical_infrastructure import Infrastructure
  obj=Infrastructure(value);core.require(bool(obj.records) and all(obj.evidence.registries[c['anchor_dataset_id']].work_id==work for c in obj.records.values()),'ONBOARD_RESEARCH_SCOPE')

def physical_source_gate(entry,checkpoint,integrity):
 if entry['field']!='physical_copy_observations':return
 from source_integrity import IMAGE_TYPES
 c=next(c for c in checkpoint['claims'] if c['claim_id']==entry['claim_id']);ev=general_evidence(checkpoint,c['evidence_ids'])
 core.require(any(e.get('evidence_class')=='supplied_image_observation' for e in ev.values()) and integrity is not None and any(ref['purpose']=='VISIBLE_CONTENT' and integrity.nodes[ref['representation_id']]['type'] in IMAGE_TYPES for ref in entry['source_refs']),'ONBOARD_PHYSICAL_SOURCE_REQUIRED')

def entry_source_gate(entry,checkpoint):
 if entry['field'] in PROPOSITION_FIELDS:core.require(any(r.get('proposition_id') is not None for r in entry['source_refs']),'ONBOARD_PROPOSITION_ANCESTRY_REQUIRED')
 if entry['field'] not in {'argument_dossiers','historical_relations'}:return
 value=next(c for c in checkpoint['claims'] if c['claim_id']==entry['claim_id'])['value']
 propositions=value['dataset']['integrity']['argument_integrity']['propositions']
 provided={(r['proposition_id'],r['proposition_snapshot']) for r in entry['source_refs'] if r['proposition_id'] is not None}
 core.require(all((p['id'],p['snapshot']) in provided for p in propositions),'ONBOARD_DOSSIER_DEPENDENCIES_REQUIRED')

def check_ref(integrity,ref):
 core.require(integrity is not None and isinstance(ref,dict) and set(ref)=={'representation_id','span_ids','snapshot','purpose','proposition_id','proposition_snapshot'},'ONBOARD_SOURCE_REFERENCE')
 core.require(ref['snapshot']==integrity.parent_snapshot(ref['representation_id'],ref['span_ids']),'ONBOARD_SOURCE_STALE')
 integrity.permit(ref['representation_id'],ref['purpose'],ref['span_ids'])
 if ref['proposition_id'] is not None:
  core.require(integrity.argument is not None and integrity.argument.proposition_snapshot(ref['proposition_id'])==ref['proposition_snapshot'],'ONBOARD_PROPOSITION_STALE')
  integrity.argument.permit_proposition(ref['proposition_id'],ref['purpose']=='SECURE_AUTHOR_POSITION')
 elif ref['proposition_snapshot'] is not None:core.require(False,'ONBOARD_PROPOSITION_REFERENCE')

def entry_anchors(work,c,ev,refs):
 prefix=anchor_prefix(work);provenance={'origin':'general_evidence','locator':'general-checkpoint:'+c['claim_id'],'evidence_refs':list(ev)}
 values={prefix+'claim.'+core.digest(c['claim_id'])[:24]:{'revision':1,'status':'CURRENT','sha256':core.digest({'claim':c,'evidence':ev}),'provenance':provenance,'source_ref':None}}
 for ref in refs:
  values[prefix+'source.'+core.digest([ref['representation_id'],ref['span_ids'],ref['purpose'],ref['proposition_id']])[:24]]={'revision':1,'status':'CURRENT','sha256':core.digest(ref),'provenance':{'origin':'general_evidence','locator':'source:'+ref['representation_id'],'evidence_refs':[ref['representation_id']]},'source_ref':clone(ref)}
 return values

def validate(doc,checkpoint,integrity=None,consuming=False):
 shape(doc)
 core.require(not audit.audit_checkpoint(checkpoint),'ONBOARD_GENERAL_AUDIT')
 if doc['identity_binding'] is None:
  core.require(doc['identity_sha256'] is None and doc['registry'] is None and not doc['entries'] and not doc['edition_candidates'] and doc['storage_state']=='NO_PERSISTENT_STATE' and doc['storage_receipt'] is None,'ONBOARD_UNLICENSED_STATE');return doc
 license=core.identity_license(checkpoint,doc['identity_binding']);core.require(doc['identity_sha256']==core.digest(license),'ONBOARD_IDENTITY_STALE')
 work=license['scope']['work_id']
 if integrity is not None:core.require(integrity.work_id==work,'ONBOARD_SOURCE_WORK')
 for cand in doc['edition_candidates']:
  ev=general_evidence(checkpoint,cand['evidence_ids']);core.require(all(e.get('evidence_class') in {'bibliography','supplied_image_observation','other_witness'} and e.get('kind') not in {'user_report','holding_report'} for e in ev.values()),'ONBOARD_CANDIDATE_BIBLIOGRAPHY')
 reg=doc['registry']
 if reg is None:
  core.require(audit.IDENTITY_STATES.index(license['identity_state'])<2 and not doc['entries'],'ONBOARD_REGISTRY_REQUIRED')
 else:
  core.validate(reg)
  for rid,r in reg['records'].items():
   if r['manifest']['scope']['work_id']!=work:continue
   core.manifest(r['manifest'])
  for e in doc['entries']:
   subject=e['scope'];core.scope(subject,e['level']);rid=selected_record(reg,subject,e['level']);core.require(rid in reg['records'] and e['claim_id'] in reg['records'][rid]['claims'],'ONBOARD_ENTRY_RECORD')
   stored=reg['records'][rid]['claims'][e['claim_id']]
   # Retained stale entries are inspectable history; never current evidence.
   if stored['status']!='CURRENT':
    core.require(not consuming,'ONBOARD_STALE_ENTRY');continue
   core.require(subject==scoped(license['scope'],e['level']),'ONBOARD_CURRENT_ENTRY_SCOPE')
   c,ev=general_claim(checkpoint,e['claim_id'],e['field'],subject)
   core.require(stored['surface']==FIELDS[e['field']][e['level']] and stored['value']==c['value'],'ONBOARD_STORED_CLAIM_BINDING')
   core.require(e['field'] not in SOURCE_FIELDS or bool(e['source_refs']),'ONBOARD_SOURCE_ANCESTRY_REQUIRED')
   physical_source_gate(e,checkpoint,integrity)
   entry_source_gate(e,checkpoint)
   for ref in e['source_refs']:check_ref(integrity,ref)
   expected=entry_anchors(work,c,ev,e['source_refs']);core.require(set(expected)<=set(stored['dependencies']),'ONBOARD_EVIDENCE_DEPENDENCIES')
   for aid,a in expected.items():core.require(reg['anchors'][aid]['sha256']==a['sha256'] and reg['anchors'][aid]['source_ref']==a['source_ref'],'ONBOARD_GENERAL_EVIDENCE_STALE')
   core.read_claim(reg,rid,e['claim_id'],checkpoint,doc['identity_binding'],integrity)
 if doc['storage_state'] in {'NATIVE_BOUND','PORTABLE_IMPORTED'}:
  storage.validate_context_storage({'storage_state':doc['storage_state'],'registry':reg,'storage_receipt':doc['storage_receipt']})
 else:core.require(doc['storage_state'] in {'NO_PERSISTENT_STATE','NATIVE_UNBOUND','OPERATION_FAILURE','STALE_STATE','INVALIDATED_STATE'} and doc['storage_receipt'] is None,'ONBOARD_PERSISTENCE_STATE')
 return doc

def retain_holding(reg,doc,binding):
 if doc['holding']['state']!='USER_REPORTED':return reg
 subject=scoped(binding['scope'],'WORK');rid=selected_record(reg,subject,'WORK');cid='holding-'+core.digest(doc['id'])[:24];aid=anchor_prefix(subject['work_id'])+cid
 old=reg['anchors'].get(aid);value={'revision':old['revision']+1 if old else 1,'status':'CURRENT','sha256':core.digest(doc['holding']),'provenance':{'origin':'general_evidence','locator':'user-report:'+doc['id'],'evidence_refs':[doc['id']]},'source_ref':None}
 if not old or old['sha256']!=value['sha256']:reg=core.set_anchor(reg,aid,value,reg['revision'],'Retain user-reported holding context only')
 previous=reg['records'][rid]['claims'].get(cid)
 if not previous or previous['value']!=doc['holding']:
  claim={'surface':'work_facts','value':clone(doc['holding']),'status':'CURRENT','revision':previous['revision']+1 if previous else 1,'provenance':value['provenance'],'dependencies':{aid:core.snapshot(core.nodes(reg)[aid])},'physical_license':None}
  reg=core.put_claim(reg,rid,cid,claim,reg['revision'],'Store holding report without identity or physical promotion')
 return reg

def identify(doc,checkpoint,binding,registry=None,edition_candidates=None,needed_evidence=None,integrity=None):
 shape(doc);license=core.identity_license(checkpoint,binding);out=clone(doc)
 out.update(identity_binding=clone(binding),identity_sha256=core.digest(license),edition_candidates=clone(edition_candidates or []),needed_evidence=clone(needed_evidence or []),storage_state='NO_PERSISTENT_STATE',storage_receipt=None)
 if audit.IDENTITY_STATES.index(license['identity_state'])<2:
  core.require(registry is None and not out['entries'],'ONBOARD_PREMATURE_REGISTRATION');out['registry']=None
 else:
  core.require(registry is not None,'ONBOARD_EXPLICIT_REGISTRY_REQUIRED');reg=core.validate(clone(registry))
  for level,threshold in core.LEVELS.items():
   if audit.IDENTITY_STATES.index(license['identity_state'])<audit.IDENTITY_STATES.index(threshold):continue
   subject=scoped(license['scope'],level);rid=selected_record(reg,subject,level)
   if rid not in reg['records']:
    reg=core.add_record(reg,core.new_manifest(rid,level,subject),reg['revision'],'Independently licensed onboarding scope')
    reg=core.license_record(reg,rid,checkpoint,binding,reg['revision'],'Bind independent general identity evidence')
   else:
    r=reg['records'][rid]
    if r['license'] is None and r['status']=='CURRENT':reg=core.license_record(reg,rid,checkpoint,binding,reg['revision'],'Bind independent identity before extending existing specialization')
    elif r['status']=='STALE' or r['license']!=core.scoped_license(license,r['manifest']):
     reg=core.reconcile_identity(reg,checkpoint,binding,reg['revision'],'Review corrected independent identity before onboarding update')
     reg=core.revalidate_record(reg,rid,checkpoint,binding,reg['revision'],'Review identity license; stale claims remain unrevalidated')
    else:core.activate(reg,rid,checkpoint,binding)
  out['registry']=retain_holding(reg,out,binding)
 validate(out,checkpoint,integrity);return out

def put(doc,checkpoint,entry,integrity=None):
 """Material update; exact general claim and current dependency roots required."""
 validate(doc,checkpoint,integrity);out=clone(doc);out.update(storage_state='NO_PERSISTENT_STATE',storage_receipt=None)
 probe=clone(out);probe['entries']=[e for e in out['entries'] if (e['level'],e['claim_id'])!=(entry['level'],entry['claim_id'])]+[clone(entry)];shape(probe)
 license=core.identity_license(checkpoint,out['identity_binding']);subject=scoped(license['scope'],entry['level']);core.scope(subject,entry['level']);core.require(entry['scope']==subject,'ONBOARD_ENTRY_SCOPE');reg=out['registry'];core.require(reg is not None,'ONBOARD_LEVEL_UNLICENSED');rid=selected_record(reg,subject,entry['level']);core.require(reg is not None and rid in reg['records'],'ONBOARD_LEVEL_UNLICENSED');core.activate(reg,rid,checkpoint,out['identity_binding'])
 c,ev=general_claim(checkpoint,entry['claim_id'],entry['field'],subject)
 core.require(entry['field'] not in SOURCE_FIELDS or bool(entry['source_refs']),'ONBOARD_SOURCE_ANCESTRY_REQUIRED')
 physical_source_gate(entry,checkpoint,integrity)
 entry_source_gate(entry,checkpoint)
 for ref in entry['source_refs']:check_ref(integrity,ref)
 anchors=entry_anchors(subject['work_id'],c,ev,entry['source_refs'])
 for aid,value in anchors.items():
  old=reg['anchors'].get(aid)
  if old is not None and old['status']=='CURRENT' and all(old[k]==value[k] for k in ('sha256','source_ref','provenance')):continue
  if old:
   value['revision']=old['revision']+1
   if 'evidence_history' in old:value['evidence_history']=clone(old['evidence_history'])
  reg=core.set_anchor(reg,aid,value,reg['revision'],'Reviewed onboarding claim evidence update')
 # Existing envelopes/bundles carry complete anchors, including recoverable
 # evidence. Historical material never supplies current-source identity.
 from specialization_evidence import capsule,append
 for aid,value in anchors.items():
  source=value['source_ref']
  material={'integrity':integrity.raw,'ref':source} if source is not None else {'claim':c,'evidence':ev}
  reg=append(reg,aid,capsule(subject['work_id'],'SOURCE' if source is not None else 'GENERAL',material),reg['revision'],'Retain validated onboarding evidence closure')
 deps=list(anchors)+entry['depends_on'];n=core.nodes(reg)
 for d in entry['depends_on']:
  core.require(d in n and n[d]['status']=='CURRENT','ONBOARD_DEPENDENCY_CURRENT')
  # Evidence anchors in another work must never supply a current-work claim.
  if d in reg['anchors']:core.require(d.startswith(anchor_prefix(subject['work_id'])),'ONBOARD_CROSS_WORK_DEPENDENCY')
 old=reg['records'][rid]['claims'].get(entry['claim_id'])
 claim={'surface':FIELDS[entry['field']][entry['level']],'value':clone(c['value']),'status':'CURRENT','revision':old['revision']+1 if old else 1,'provenance':next(iter(anchors.values()))['provenance'],'dependencies':{d:core.snapshot(n[d]) for d in deps},'physical_license':core.physical_license(checkpoint,c['claim_id']) if entry['field']=='physical_history' else None}
 reg=core.put_claim(reg,rid,entry['claim_id'],claim,reg['revision'],'Reviewed onboarding research claim')
 out['registry']=reg;out['entries']=probe['entries'];validate(out,checkpoint,integrity);return out

def reconcile(doc,checkpoint,binding,integrity=None,reason='Actual upstream evidence correction'):
 """Canonical correction, distinct from inherited hypothetical sensitivity."""
 shape(doc);out=clone(doc);reg=core.validate(out['registry']);work=doc['identity_binding']['scope']['work_id']
 core.require(integrity is None or integrity.work_id==work,'ONBOARD_SOURCE_WORK')
 reg=core.reconcile_identity(reg,checkpoint,binding,reg['revision'],reason,previous_scope=doc['identity_binding']['scope'])
 claims={c['claim_id']:c for c in checkpoint['claims']}
 for aid,a in list(reg['anchors'].items()):
  if not aid.startswith(anchor_prefix(work)) or a['status']!='CURRENT':continue
  good=True
  try:
   if a['source_ref'] is not None:
    ref=a['source_ref']
    # Unloaded source/span/proposition context is not a canonical correction.
    if integrity is None or ref['representation_id'] not in integrity.nodes:continue
    if not set(ref['span_ids'])<=set(integrity.spans(ref['representation_id'])):continue
    if ref['proposition_id'] is not None and (integrity.argument is None or ref['proposition_id'] not in integrity.argument.props):continue
    check_ref(integrity,ref)
   elif a['provenance']['locator'].startswith('user-report:'):continue
   else:
    cid=a['provenance']['locator'].split(':',1)[1]
    if cid not in claims:continue
    c=claims[cid];emap={e['evidence_id']:e for e in checkpoint['evidence']};pending=list(c.get('evidence_ids',[]));seen=set();missing=False
    while pending:
     eid=pending.pop()
     if eid in seen:continue
     seen.add(eid)
     if eid not in emap:missing=True;break
     pending.extend(emap[eid].get('ancestor_evidence_ids',[]))
    if missing:continue
    ev=general_evidence(checkpoint,c['evidence_ids']);good=a['sha256']==core.digest({'claim':c,'evidence':ev})
  except (ValueError,KeyError,TypeError):good=False
  if not good:reg=core.mark(reg,aid,'STALE',reg['revision'],reason)
 out.update(registry=reg,identity_binding=clone(binding),identity_sha256=core.digest(core.identity_license(checkpoint,binding)),storage_state='NO_PERSISTENT_STATE',storage_receipt=None)
 return out

def manifest_view(doc):
 shape(doc);reg=doc['registry'];work=doc['identity_binding']['scope']['work_id'] if doc['identity_binding'] else None
 records={rid:clone(r) for rid,r in (reg['records'].items() if reg else []) if r['manifest']['scope']['work_id']==work}
 return {'work_identity':clone(doc['identity_binding']),'edition_candidates':clone(doc['edition_candidates']),'exemplar_identity':doc['identity_binding']['scope']['exemplar_id'] if doc['identity_binding'] else None,'levels':{level:{'manifests':[clone(r['manifest']) for r in records.values() if r['manifest']['level']==level],'fields':{f:[{'claim_id':cid,'status':c['status'],'value':clone(c['value']),'evidence_ancestry':clone(c['dependencies'])} for r in records.values() if r['manifest']['level']==level for cid,c in r['claims'].items() if c['surface']==surfaces.get(level) and any(e['claim_id']==cid and e['field']==f and e['level']==level for e in doc['entries'])] for f,surfaces in FIELDS.items() if level in surfaces}} for level in core.LEVELS},'verification_state':{rid:r['status'] for rid,r in records.items()},'revision_history':clone(reg['audit']) if reg else [],'dependency_roots':sorted({d for r in records.values() for c in r['claims'].values() for d in c['dependencies']})}

def research_objects(doc,checkpoint,integrity=None):
 """Project licensed current evidence into existing dossier/DWG schemas."""
 validate(doc,checkpoint,integrity);work=doc['identity_binding']['scope']['work_id'];license=core.identity_license(checkpoint,doc['identity_binding']);core.require(audit.IDENTITY_STATES.index(license['identity_state'])>=2,'ONBOARD_WORK_DOSSIER_UNLICENSED')
 dossier={'schema_version':'0.1','work_id':work,'identity_state':checkpoint['identity_state'],'selected_claim_ids':clone(checkpoint['selected_claim_ids']),'claims':clone(checkpoint['claims']),'evidence':clone(checkpoint['evidence']),'competing_candidates':clone(doc['edition_candidates']),'updated_at':None}
 graph={'schema_version':'0.1','work_id':work,'witnesses':[],'edges':[]}
 for e in doc['entries']:
  if e['field'] not in {'known_witnesses','historical_translations','source_relationships'}:continue
  subject=e['scope'];rid=selected_record(doc['registry'],subject,e['level']);c=doc['registry']['records'][rid]['claims'][e['claim_id']]
  if c['status']!='CURRENT':continue
  value=clone(c['value']);core.require(isinstance(value,dict) and value.get('work_id')==work,'ONBOARD_WITNESS_SCOPE')
  if e['field']=='source_relationships':
   core.require(set(value)>={'edge_id','from','to','relationship'} and value['relationship'] in {'same_setting_as','derived_from','translation_of','quotes','corrects','unknown_relation'},'ONBOARD_WITNESS_EDGE');graph['edges'].append(value)
  else:
   core.require(set(value)>={'witness_id','work_id','type','locator','access_status','independence_group'},'ONBOARD_WITNESS_FIELDS');value['source_ancestry']=clone(e['source_refs']);graph['witnesses'].append(value)
 ids=[w['witness_id'] for w in graph['witnesses']];core.require(len(ids)==len(set(ids)) and all(e['from'] in ids and e['to'] in ids for e in graph['edges']),'ONBOARD_WITNESS_ENDPOINTS')
 return {'work_dossier':dossier,'witness_graph':graph}

def persist(doc,checkpoint,adapter,integrity=None,create=False):
 validate(doc,checkpoint,integrity);core.require(doc['registry'] is not None,'ONBOARD_NOT_READY_TO_PERSIST');out=clone(doc)
 try:
  if create:result=adapter.create_registry(out['registry'])
  else:
   old=adapter.read_registry()['payload'];core.require(all(old[k]==out['registry'][k] for k in ('registry_id','namespace','account_scope')),'ONBOARD_STORAGE_PARTITION')
   if old==out['registry']:result=adapter.read_registry()
   else:
    core.require(set(old['records'])<=set(out['registry']['records']) and out['registry']['audit'][:len(old['audit'])]==old['audit'],'ONBOARD_STORAGE_HISTORY')
    for rid,r in old['records'].items():
     if r['manifest']['scope']['work_id']!=out['identity_binding']['scope']['work_id']:core.require(out['registry']['records'][rid]==r,'ONBOARD_STORAGE_WORK_ISOLATION')
    result=adapter.write_registry(out['registry'],old['revision'],core.digest(old))
  out.update(registry=result['payload'],storage_state=result['state'],storage_receipt=result['receipt'])
 except (ValueError,TypeError,KeyError):
  state=adapter.status()['state'];out.update(storage_state=state if state in {'NATIVE_UNBOUND','NO_PERSISTENT_STATE'} else 'OPERATION_FAILURE',storage_receipt=None)
 validate(out,checkpoint,integrity);return out

def retrieve(adapter):
 """Administrative recovery only; no identity, currentness or activation granted."""
 result=adapter.read_registry();return {'registry':core.validate(result['payload']),'storage_state':result['state'],'receipt':result['receipt'],'activation_granted':False}

def export(doc,subject):return storage.export_bundle(core.validate(doc['registry']),subject)
def import_bundle(bundle,subject,existing=None):return storage.import_bundle(bundle,subject,existing)
def activate(doc,checkpoint,binding):return core.route(core.validate(doc['registry']),checkpoint,binding)

def render(doc,checkpoint,integrity=None):
 validate(doc,checkpoint,integrity);level=checkpoint['identity_state'];lines=['Specialization onboarding.']
 if level in {'UNIDENTIFIED','WORK_CANDIDATE'}:lines.append('Work identity remains unresolved. No specialization has been registered.')
 else:
  active=core.route(doc['registry'],checkpoint,doc['identity_binding']) if doc['registry'] else []
  levels={doc['registry']['records'][rid]['manifest']['level'] for rid in active}
  lines.append('Work established; work specialization created or updated.' if 'WORK' in levels else 'Work established; specialization registration or revalidation is pending.')
  if level=='WORK_ESTABLISHED':lines.append('Edition candidates remain unresolved; no edition specialization is licensed.')
  else:lines.append('Edition independently established; edition specialization licensed.' if 'EDITION' in levels else 'Edition independently established; edition specialization registration or revalidation is pending.')
  if level=='EXEMPLAR_ESTABLISHED':lines.append('Exemplar identity independently established. Physical-history claims require their own evidence.' if 'EXEMPLAR' in levels else 'Exemplar identity independently established; exemplar specialization registration or revalidation is pending.')
  else:lines.append('Exemplar identity remains unresolved; no copy-specific specialization is licensed.')
 if doc['holding']['state']=='USER_REPORTED':lines.append('Your holding is recorded as a user report. It establishes no bibliographic identity, provenance or physical-history fact.')
 stale=sum(c['status']!='CURRENT' for r in (doc['registry']['records'].values() if doc['registry'] else []) if not doc['identity_binding'] or r['manifest']['scope']['work_id']==doc['identity_binding']['scope']['work_id'] for c in r['claims'].values())
 if stale:lines.append(str(stale)+' retained claims require revalidation and supply no current evidence.')
 if doc['storage_state']=='NATIVE_BOUND':lines.append('Persisted in the native document store with a confirmed receipt. Retain the returned registry document binding in your project or supply it in a later conversation; retrieval requires that exact binding.')
 elif doc['storage_state']=='PORTABLE_IMPORTED':lines.append('Recovered from an explicit portable bundle. This is non-native transfer, not native cross-conversation recovery.')
 else:
  reason={'NO_PERSISTENT_STATE':'No persistent storage has been confirmed','NATIVE_UNBOUND':'The native registry binding is missing','OPERATION_FAILURE':'The native operation failed','STALE_STATE':'Retained state is stale','INVALIDATED_STATE':'Retained state is invalidated'}[doc['storage_state']]
  lines.append('Not confirmed persisted. '+reason+'. General translation and research remain available. No prior registry is discovered automatically.')
 if doc['needed_evidence']:lines.append('Useful next evidence: '+'; '.join(doc['needed_evidence'])+'.')
 lines.append('Later activation requires independent identity evidence from the current source. Stored titles, dossiers and locators cannot establish it.')
 return '\n'.join(lines)

def validate_completion(directory: Path,checkpoint,rendered_text,integrity):
 path=directory/FILE;claims=[c for c in checkpoint.get('claims',[]) if c.get('claim_type')=='specialization_onboarding']
 from evidence_audit import selected_domain_ids, selected_domain_claims
 selected=selected_domain_ids(checkpoint,"specialization_onboarding");claims=selected_domain_claims(checkpoint,"specialization_onboarding")
 if not selected:return
 core.require(path.is_file() and not path.is_symlink(),'ONBOARD_COMPLETION_INPUT_REQUIRED')
 doc=json.loads(path.read_text());validate(doc,checkpoint,integrity)
 import task_state
 pub=task_state.descriptor(directory);core.require(pub is not None and pub['request']==doc['request'],'ONBOARD_PUBLICATION_REQUEST')
 core.require(any(s['operation']=='ONBOARD_SPECIALIZATION' for s in pub['operation_plan']['operations']),'ONBOARD_PUBLICATION_ROUTE')
 output=render(doc,checkpoint,integrity);core.require(selected=={doc['id']} and len(claims)==1 and claims[0].get('onboarding_id')==doc['id'] and claims[0].get('onboarding_sha256')==hashlib.sha256(output.encode()).hexdigest() and output in rendered_text,'ONBOARD_COMPLETION_OUTPUT_BINDING')
