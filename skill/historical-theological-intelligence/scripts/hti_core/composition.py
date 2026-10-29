"""Kernel-owned, registry-bound capability composition for one installed Skill."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[2]
SCHEMA='hti-composition-1'
def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def filehash(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def need(ok,code,detail=''):
 if not ok:raise ValueError('COMPOSITION_'+code+': '+str(detail))
def load():
 p=ROOT/'registry/capabilities.json';r=json.loads(p.read_text());lock=json.loads((ROOT/'registry/lock.json').read_text())
 need(r['schema_version']=='hti-capabilities-1' and lock['candidate_version']==r['candidate_version'],'VERSION')
 for rel,h in lock['files'].items():
  f=ROOT/'registry'/rel;need(not f.is_symlink() and f.is_file() and filehash(f)==h,'PACKAGE_INTEGRITY',rel)
 return r

def dependencies(op,selected,facts,r):
 entry=r['operations'][op];deps=list(entry['requires_operations'])
 for condition in entry['conditional_requires']:
  predicate=condition['predicate']
  if predicate=='ALL_OTHER_SELECTED':deps += [x for x in selected if x!=op]
  elif predicate=='TRANSLATION_SELECTED':deps += [x for x in condition['operations'] if x in selected][:1]
  elif facts.get(predicate,False):deps+=condition['operations']
 return list(dict.fromkeys(deps))
def closure(requested,facts=None,r=None):
 r=r or load();facts=facts or {};need(set(facts)<= {'ASSERTS_DEPENDENCE','HRG_TARGET_BOUND'} and all(type(v)==bool for v in facts.values()),'FACTS')
 selected=list(dict.fromkeys(requested));need(bool(selected) and set(selected)<=set(r['operations']),'UNKNOWN_OPERATION')
 while True:
  expanded=list(selected)
  for op in selected:
   for dep in dependencies(op,selected,facts,r):
    if dep not in expanded:expanded.append(dep)
  if expanded==selected:break
  selected=expanded
 result=[];visiting=set()
 def visit(op):
  if op in result:return
  need(op not in visiting,'CYCLE',op);visiting.add(op)
  for d in dependencies(op,selected,facts,r):visit(d)
  visiting.remove(op);result.append(op)
 for op in selected:visit(op)
 return result

def augment_steps(steps,anchor,direction,phase_owner,step_class,op_class,direction_class,facts=None):
 r=load();requested=[s.operation.value for s in steps];ops=closure(requested,facts,r);by={s.operation.value:s for s in steps};ids={op:f"op-{i+1:02d}-{op.lower().replace('_','-')}" for i,op in enumerate(ops)}
 return tuple(step_class(step_id=ids[op],operation=op_class(op),depends_on=tuple(ids[d] for d in dependencies(op,ops,facts or {},r)),anchor_id=anchor,direction=(direction if direction!=direction_class.NONE else direction_class.BIDIRECTIONAL) if op=='TRACE_LINEAGE' else direction_class.NONE,phase_owner=phase_owner.get(op_class(op),'v0.1'),prerequisite_only=by[op].prerequisite_only if op in by else True) for op in ops)

def request_operations(text):
 from .natural_language_routing import _candidate_intents,_operation_for,IntentFamily,_negative_constraints
 intents=_candidate_intents(' '.join(text.casefold().split()));constraints=_negative_constraints(text.casefold())
 # Honor the existing explicit opt-outs without removing their indispensable
 # prerequisites from a surviving dependent operation.
 excluded=set()
 if 'NO_GENEALOGY' in constraints:excluded|={'ASSESS_HISTORICAL_RELATION','TRACE_LINEAGE','ANALYZE_SOURCE_TRANSMISSION','ADJUDICATE_IMMEDIATE_SOURCE'}
 if 'NO_ONBOARDING' in constraints:excluded.add('ONBOARD_SPECIALIZATION')
 for flag,ops in {'NO_ACCESS_NETWORK':['ASSESS_ACCESS_NETWORK'],'NO_SENSITIVITY':['TEST_HISTORICAL_SENSITIVITY'],'NO_NOVELTY':['ASSESS_NOVELTY','ADJUDICATE_ORIGINALITY','AUDIT_NOVELTY_LEDGER'],'NO_IDENTITY_EXPANSION':['IDENTIFY_WORK'],'NO_CARTOGRAPHY':['MAP_WHOLE_WORK','MAP_DEVELOPMENT','COMPARE_WORK_MAPS'],'NO_WHOLE_WORK_CARTOGRAPHY':['MAP_WHOLE_WORK'],'NO_DEVELOPMENTAL_CARTOGRAPHY':['MAP_DEVELOPMENT'],'NO_COMPARATIVE_CARTOGRAPHY':['COMPARE_WORK_MAPS']}.items():
  if flag in constraints:excluded.update(ops)
 requested=list(dict.fromkeys(_operation_for(i).value for i in intents if i!=IntentFamily.COMPOSITE_REQUEST));return [x for x in requested if x not in excluded],excluded

def describe(plan,facts=None):
 r=load();facts=facts or {};selected=[s['operation'] for s in plan['operations']];need(len(selected)==len(set(selected)),'DUPLICATE_OPERATION')
 requested,excluded=request_operations(plan['request_text']);requested=list(dict.fromkeys(requested+[s['operation'] for s in plan['operations'] if not s.get('prerequisite_only',False)]))
 expected=closure(requested,facts,r);need(set(expected)<=set(selected),'MISSING_CLOSURE',sorted(set(expected)-set(selected)))
 full=closure(selected,facts,r);need(set(full)==set(selected),'MISSING_CLOSURE',sorted(set(full)-set(selected)))
 by={s['operation']:s for s in plan['operations']}
 for op in selected:need({by[d]['step_id'] for d in dependencies(op,selected,facts,r)}<=set(by[op]['depends_on']),'DEPENDENCY_BINDING',op)
 modules={'kernel'}|{r['operations'][op]['owner'] for op in selected}
 if 'SCHOLARLY_TRANSLATE' in selected:modules.add('sources')
 if any(op in selected for op in ['ANALYZE_SOURCE_TRANSMISSION','ADJUDICATE_IMMEDIATE_SOURCE','ASSESS_NOVELTY','ADJUDICATE_ORIGINALITY','ASSESS_ACCESS_NETWORK','TEST_HISTORICAL_SENSITIVITY']):modules.add('sources')
 verify_selected_package(modules,r)
 module_rows=[{'id':m,'version':r['modules'][m]['version'],'contract_sha256':filehash(ROOT/r['modules'][m]['contract'])} for m in sorted(modules)]
 instruction_paths=set(r['modules']['kernel']['instructions'])|{p for op in selected for p in r['operations'][op]['instructions']}
 reading={p:filehash(ROOT/p) for p in sorted(instruction_paths)}
 manifest=ROOT/'SHA256SUMS.txt';need(manifest.is_file() and not manifest.is_symlink(),'MANIFEST')
 obj={'schema':SCHEMA,'registry_sha256':filehash(ROOT/'registry/capabilities.json'),'package_manifest_sha256':filehash(manifest),'candidate_version':r['candidate_version'],'requested':requested,'closure':full,'closure_sha256':digest(full),'modules':module_rows,'facts':facts,'excluded_operations':sorted(excluded),'blocked_by_opt_out':sorted(set(full)&excluded),'required_state':sorted({x for op in full for x in r['operations'][op]['requires_state']}),'validators_required':sorted({r['operations'][op]['validator'] for op in full}|{r['operations'][op]['additional_validator'] for op in full if r['operations'][op]['additional_validator']}),'reading_manifest':reading,'external_requirements':{op:r['operations'][op]['external_requirements'] for op in full}}
 return obj

def validate_binding(pub):
 need(pub.get('composition')==describe(pub['operation_plan'],pub.get('composition',{}).get('facts',{})),'STALE_BINDING')

def validate_state(directory,checkpoint,pub):
 validate_binding(pub);r=load();bound=pub['composition'];outcomes={o['id']:o for o in checkpoint['publication_contract']['outcomes']};objects={};satisfaction={}
 for step in pub['operation_plan']['operations']:
  op=step['operation'];out=outcomes[step['step_id']];status=out['status'];satisfaction[step['step_id']]=status
  if op in bound['blocked_by_opt_out']:need(status in {'UNRESOLVED','BLOCKED'},'USER_OPT_OUT',op)
  if any(outcomes[d]['status'] in {'BLOCKED','UNRESOLVED'} for d in step['depends_on']):need(status in {'BLOCKED','UNRESOLVED'},'PREREQUISITE_UNAVAILABLE',op)
  if status not in {'COMPLETED','PARTIAL'}:continue
  for key in r['operations'][op]['requires_state']:
   spec=r['state_objects'][key];p=directory/spec['path'];need(p.is_file() and not p.is_symlink(),'STATE_REQUIRED',key);raw=json.loads(p.read_text())
   need(raw.get(spec['schema_field']) in spec['versions'],'REVALIDATION_REQUIRED',key)
   if 'work_id' in raw:need(raw['work_id']==checkpoint['work_id'],'WORK_MISMATCH',key)
   if 'task_directory' in raw:need(raw['task_directory']==str(directory.resolve()),'TASK_MISMATCH',key)
   objects[key]={'path':spec['path'],'schema_id':key,'schema_version':raw[spec['schema_field']],'producer_module':spec['producer_module'],'producer_version':r['modules'][spec['producer_module']]['version'],'work_id':checkpoint['work_id'],'task_directory':str(directory.resolve()),'snapshot':filehash(p),'currentness':'NATIVE_VALIDATORS_REQUIRED'}
 # A new asserted dependence requires a composition declared before research;
 # changing these facts cannot mutate an existing publication.
 for a in checkpoint['publication_contract']['assertions']:
  if a.get('facets',{}).get('historical_dependence'):need(bound['facts'].get('ASSERTS_DEPENDENCE') or 'ASSESS_HISTORICAL_RELATION' in bound['closure'],'FRESH_DEPENDENCE_COMPOSITION_REQUIRED')
 return {'objects':objects,'satisfaction':satisfaction}

_VALIDATORS_RUN=[]
def begin_validation():_VALIDATORS_RUN.clear()
def record_validator(name):
 if name not in _VALIDATORS_RUN:_VALIDATORS_RUN.append(name)
def verify_selected_package(module_ids,r=None):
 r=r or load();manifest=ROOT/'SHA256SUMS.txt';entries={n:h for h,n in (line.split('  ',1) for line in manifest.read_text().splitlines())}
 paths={p for m in module_ids for p in r['modules'][m]['code_paths']+r['modules'][m]['instructions']}
 paths|={'registry/capabilities.json','registry/lock.json'}|{r['modules'][m]['contract'] for m in module_ids}
 for rel in paths:
  p=ROOT/rel;need(rel in entries and p.is_file() and not p.is_symlink() and filehash(p)==entries[rel],'PACKAGE_INTEGRITY',rel)
def dispatch_validators(directory,checkpoint,rendered_text,registry):
 import importlib,task_state
 from evidence_audit import selected_domain_ids
 r=load();pub=task_state.descriptor(directory);operations=pub['composition']['closure'] if pub.get('composition') else [s['operation'] for s in pub['operation_plan']['operations']]
 domains={r['operations'][op]['domain'] for op in operations if r['operations'][op]['domain']}
 domains|={d for d in r['domain_fields'] if selected_domain_ids(checkpoint,d)}
 for domain in r['validator_dispatch_order']:
  if domain not in domains:continue
  entry=next(v for v in r['operations'].values() if v['domain']==domain);verify_selected_package([entry['owner']],r)
  validator=entry['additional_validator'];module,name=validator.split(':')
  try:fn=getattr(importlib.import_module(module),name)
  except (ImportError,SyntaxError,AttributeError) as e:raise ValueError('COMPOSITION_PACKAGE_INTEGRITY: '+module) from e
  fn(directory,checkpoint,rendered_text,registry);record_validator(validator)
def composition_receipt(directory,checkpoint,pub):
 validate_binding(pub);state=validate_state(directory,checkpoint,pub);base=dict(pub['composition']);need(set(base['validators_required'])<=set(_VALIDATORS_RUN),'VALIDATOR_OMISSION')
 satisfaction={k:('EXECUTED' if v in {'COMPLETED','PARTIAL'} else v) for k,v in state['satisfaction'].items()}
 # Existing same-task retained publications are never trusted by label alone.
 # Native validators above still rerun over the current bytes.
 prior=pub.get('previous');retained=checkpoint['publication_contract']['scope']['retained']
 if prior and retained:
  history=directory/'publication-history'/prior['history_id'];receipt=history/'completion-receipt.json'
  if receipt.is_file() and not receipt.is_symlink():
   old=json.loads(receipt.read_text());old_comp=old.get('composition',{});eligible=any(v['publication_id']==prior['history_id'] and v['receipt_sha256']==filehash(receipt) for v in retained)
   if eligible and old.get('task_directory')==str(directory.resolve()) and old_comp.get('candidate_version')==base['candidate_version'] and old_comp.get('modules')==base['modules']:
    for step in pub['operation_plan']['operations']:
     if not step.get('prerequisite_only'):continue
     keys=load()['operations'][step['operation']]['requires_state']
     if satisfaction[step['step_id']]=='EXECUTED' and keys and all(k in state['objects'] and state['objects'][k]==old_comp.get('state_objects',{}).get(k) for k in keys):satisfaction[step['step_id']]='RETAINED_BOUND'
 base.update(satisfaction=satisfaction,state_objects=state['objects'],validators_run=list(_VALIDATORS_RUN));base['receipt_binding_sha256']=digest(base);return base

def verify_receipt(directory,pub,receipt):
 comp=receipt.get('composition');need(isinstance(comp,dict),'RECEIPT_COMPOSITION')
 need(comp.get('receipt_binding_sha256')==digest({k:v for k,v in comp.items() if k!='receipt_binding_sha256'}),'RECEIPT_BINDING')
 bound=pub.get('composition');need(isinstance(bound,dict) and all(comp.get(k)==v for k,v in bound.items()),'RECEIPT_PUBLICATION')
 need(comp['closure_sha256']==digest(comp['closure']),'RECEIPT_CLOSURE');need(set(comp['validators_required'])<=set(comp['validators_run']),'RECEIPT_VALIDATORS')
 ids={s['step_id'] for s in pub['operation_plan']['operations']};need(set(comp['satisfaction'])==ids and set(comp['satisfaction'].values())<={'EXECUTED','RETAINED_BOUND','UNRESOLVED','BLOCKED'},'RECEIPT_SATISFACTION')
 checkpoint=json.loads((directory/'evidence-checkpoint.json').read_text())
 outcomes={o['id']:o for o in checkpoint['publication_contract']['outcomes']}
 for sid,mode in comp['satisfaction'].items():
  status=outcomes[sid]['status']
  need(mode in {'EXECUTED','RETAINED_BOUND'} if status in {'COMPLETED','PARTIAL'} else mode==status,'RECEIPT_OUTCOME',sid)
  if mode=='RETAINED_BOUND':
   prior=pub.get('previous');need(bool(prior),'RETAINED_HISTORY')
   history=directory/'publication-history'/prior['history_id'];oldp=history/'completion-receipt.json';need(oldp.is_file() and not oldp.is_symlink(),'RETAINED_RECEIPT')
   old=json.loads(oldp.read_text());need(old.get('task_directory')==str(directory.resolve()) and old.get('composition',{}).get('modules')==comp['modules'],'RETAINED_COMPATIBILITY')
 for key,obj in comp['state_objects'].items():
  need(obj['task_directory']==str(directory.resolve()) and obj['work_id']==checkpoint['work_id'],'RECEIPT_TASK_WORK',key)
  p=directory/obj['path'];need(Path(obj['path']).name==obj['path'] and p.is_file() and not p.is_symlink(),'RECEIPT_STATE_PATH',key)
  need(obj['snapshot']==filehash(p)==receipt['inputs'].get(obj['path']),'RECEIPT_STATE_SNAPSHOT',key)
 # Recovery binds the committed native state independently of a newer installation.


def compose_request(request,directory=None,facts=None):
 from .natural_language_routing import route_request,ConversationContext,ContextAnchor,AnchorKind,OperationID,Direction,OperationStep,_PHASE_OWNER
 context=None
 if directory:
  p=directory/'source-integrity.json'
  if p.exists():
   raw=json.loads(p.read_text());nodes=raw.get('representations',[])
   if nodes:context=ConversationContext(supplied_anchor=ContextAnchor(nodes[0]['id'],AnchorKind.PASSAGE,work_id=raw.get('work_id')))
 record=route_request(request,context=context)
 if facts:
  import dataclasses
  record=dataclasses.replace(record,operations=augment_steps(record.operations,record.anchor_id,record.scope.direction,_PHASE_OWNER,OperationStep,OperationID,Direction,facts))
 plan=record.to_dict();return {'operation_plan':plan,'composition_facts':facts or {},'composition':describe(plan,facts)}
