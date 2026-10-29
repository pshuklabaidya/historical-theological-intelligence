"""Readonly historical scenarios over existing typed evidence dependencies.

Scenario results describe support under a hypothetical intervention, not facts.
The dependency view below references native domains; it creates no universal graph.
"""
from __future__ import annotations
import copy, hashlib, json
from dataclasses import replace
from .historical_infrastructure import Infrastructure, need, no_numbers
from .cartography import shape, text, ids, table, fingerprint
from .novelty import Novelty
from .dependency_uncertainty import DependencyUncertaintyAnalysis, UncertaintyRoot

SCHEMA='hti-historical-sensitivity-1'
DOMAINS=frozenset({'PROPOSITION','REPRESENTATION','PRG_RELATION','HISTORICAL_EDGE',
 'EXPLANATION','MAP','NOVELTY','NETWORK_RECORD','ACCESS_PATH','HISTORICAL_BINDING','ENTITY'})
OPERATIONS=frozenset({'REMOVE','DOWNGRADE','INACCESSIBLE','TRANSLATION_CREATED','COLLAPSE_DERIVATIVE','CHRONOLOGY_DOWNGRADE','ATTRIBUTION_DOWNGRADE'})

class Sensitivity:
 def __init__(self,value):
  shape(value,'schema_version infrastructure novelty scenario','sensitivity document')
  need(value['schema_version']==SCHEMA,'SENSITIVITY_SCHEMA');no_numbers(value)
  self.raw=copy.deepcopy(value);self.network=Infrastructure(self.raw['infrastructure']);self.evidence=self.network.evidence
  self.novelty=Novelty(self.raw['novelty']) if self.raw['novelty'] is not None else None
  if self.novelty is not None:need(self.novelty.raw['evidence']==self.evidence.raw,'SENSITIVITY_NOVELTY_SUBSTRATE')
  self.scenario=shape(self.raw['scenario'],'id work_id interventions targets rationale snapshot','scenario')
  text(self.scenario['id'],'scenario id');text(self.scenario['rationale'],'scenario rationale')
  self.interventions=table(self.scenario['interventions'],'interventions');need(bool(self.interventions),'INTERVENTIONS_REQUIRED')
  self.targets=self.scenario['targets'];need(isinstance(self.targets,list) and bool(self.targets),'TARGETS_REQUIRED')
  self.views={};self.active=[]
  for i in self.interventions.values():self.intervention(i)
  for t in self.targets:self.reference(t)
  for t in self.targets:
   k=self.key(t);need(k not in self.views,'DUPLICATE_TARGET');self.views[k]=self.evaluate(t)
  self.snapshot=fingerprint({'canonical':self.network.raw,'novelty':self.raw['novelty'],'scenario':{k:v for k,v in self.scenario.items() if k!='snapshot'}})
  need(self.scenario['snapshot']==self.snapshot,'SCENARIO_REVALIDATION_REQUIRED')

 @staticmethod
 def key(t):return (t['domain'],t['dataset_id'],t['id'],t['sub_id'])
 def reference(self,t,comparison=False):
  shape(t,'domain dataset_id id sub_id','typed reference');need(t['domain'] in DOMAINS,'REFERENCE_DOMAIN')
  domain,key,id_,sub=self.key(t)
  if domain in {'NETWORK_RECORD','ACCESS_PATH','HISTORICAL_BINDING','ENTITY'}:
   maps={'NETWORK_RECORD':self.network.records,'ACCESS_PATH':self.network.paths,'HISTORICAL_BINDING':self.network.bindings,'ENTITY':self.network.entities};need(id_ in maps[domain] and sub is None,'NETWORK_REFERENCE')
   r=maps[domain][id_];expected=r.get('anchor_dataset_id',r.get('dataset_id'));need(key==expected,'REFERENCE_WORK')
  elif domain=='NOVELTY':
   need(self.novelty is not None and id_ in self.novelty.claims and sub is None,'NOVELTY_REFERENCE')
   c=self.novelty.claims[id_];need(c['status']=='CURRENT','NOVELTY_CURRENT_REQUIRED');need(self.novelty.objects[c['object_id']]['dataset_id']==key,'NOVELTY_REFERENCE_WORK')
  else:
   need(key in self.evidence.datasets,'REFERENCE_DATASET');r=self.evidence.registries[key];d=self.evidence.dossiers[key]
   if domain=='PROPOSITION':r.argument.permit_proposition(id_);need(sub is None,'REFERENCE_SUB_ID')
   elif domain=='REPRESENTATION':need(id_ in r.nodes and not r.stale(id_) and sub is None,'SOURCE_REFERENCE')
   elif domain=='PRG_RELATION':need(id_ in {x.relation_id for x in d.relations} and sub is None,'RELATION_REFERENCE')
   elif domain=='HISTORICAL_EDGE':need(key in self.evidence.graphs and self.evidence.graphs[key].edge(id_).active and sub is None,'HISTORICAL_EDGE_REFERENCE')
   elif domain=='EXPLANATION':need(id_ in r.argument.consumers and 'historical_explanation' in r.argument.consumers[id_] and r.argument.consumer_current(id_) and sub is None,'EXPLANATION_REFERENCE')
   elif domain=='MAP':
    need(id_ in self.evidence.maps and sub in self.evidence.claims[id_] and self.evidence.claims[id_][sub]['status']=='CURRENT','MAP_REFERENCE')
    need(self.evidence.registries[key].work_id==self.evidence.corpora[self.evidence.maps[id_]['corpus_id']]['work_id'],'MAP_REFERENCE_WORK')
  if domain!='ENTITY' and not comparison:
   need(key in self.evidence.datasets and self.evidence.registries[key].work_id==self.scenario['work_id'],'SCENARIO_WORK_ISOLATION')

 def intervention(self,i):
  shape(i,'id target operation related_target rationale','intervention');text(i['rationale'],'intervention rationale');self.reference(i['target'],comparison=True)
  domain=i['target']['domain'];op=i['operation'];need(op in OPERATIONS,'SCENARIO_OPERATION')
  need(domain in {'PROPOSITION','REPRESENTATION','PRG_RELATION','HISTORICAL_EDGE','NETWORK_RECORD','ENTITY'},'INTERVENTION_DOMAIN')
  if op in {'INACCESSIBLE','CHRONOLOGY_DOWNGRADE'}:need(domain in {'NETWORK_RECORD','ENTITY'},'ACCESS_INTERVENTION_DOMAIN')
  if op=='TRANSLATION_CREATED':need(domain=='REPRESENTATION','TRANSLATION_INTERVENTION_DOMAIN')
  if op=='ATTRIBUTION_DOWNGRADE':need(domain in {'PROPOSITION','REPRESENTATION','HISTORICAL_EDGE'},'ATTRIBUTION_INTERVENTION_DOMAIN')
  if op=='COLLAPSE_DERIVATIVE':
   need(domain=='REPRESENTATION' and i['related_target'] is not None,'DERIVATIVE_REFERENCE_REQUIRED');self.reference(i['related_target'],comparison=True);need(i['related_target']['domain']=='REPRESENTATION','DERIVATIVE_REFERENCE_DOMAIN');need(self.key(i['target'])!=self.key(i['related_target']),'DERIVATIVE_SELF_REFERENCE')
  else:need(i['related_target'] is None,'UNEXPECTED_RELATED_TARGET')

 def dependencies(self,t,visited=None):
  """Typed dependency references recovered from accepted native records only."""
  seen=set() if visited is None else set(visited);k=self.key(t)
  if k in seen:return set()
  seen.add(k);domain,key,id_,sub=k;out={k}
  def add(d,key,id_,sub=None):
   ref={'domain':d,'dataset_id':key,'id':id_,'sub_id':sub};out.update(self.dependencies(ref,seen))
  def source_refs(refs):
   for r in refs:
    reg=self.evidence.registries[r['dataset_id']];n=r['ref']['representation_id']
    # Representation dependencies stay ancestry-bound, not merely similar labels.
    for a in reg.dependency_scope(n):out.add(('REPRESENTATION',r['dataset_id'],a,None))
  if domain=='PROPOSITION':
   r=self.evidence.registries[key];p=r.argument.props[id_];n=p['representation_id']
   for a in r.dependency_scope(n):out.add(('REPRESENTATION',key,a,None))
   for arc in self.evidence.analyses[key]._context_arcs(None):
    if arc.downstream_proposition_id==id_ and arc.effect!='NON_PROPAGATING':
     add('PRG_RELATION',key,arc.relation_id)
     add('PROPOSITION',key,arc.upstream_proposition_id)
  elif domain=='PRG_RELATION':
   edge=next(x for x in self.evidence.dossiers[key].relations if x.relation_id==id_)
   add('PROPOSITION',key,edge.source_proposition_id);add('PROPOSITION',key,edge.target_proposition_id)
  elif domain=='EXPLANATION':
   r=self.evidence.registries[key];c=r.argument.consumers[id_]
   def consumer(c):
    for dep in c['dependencies']:
     if dep['kind']=='proposition':add('PROPOSITION',key,dep['id'])
     elif dep['kind']=='consumer':consumer(r.argument.consumers[dep['id']])
    p=c.get('historical_explanation')
    if p:
     for e in p.get('evidence',[])+p.get('counterevidence',[]):
      # Stage8 source evidence uses native refs in the existing consumer.
      for field in ['source_refs','evidence_refs']:
       if field in e:source_refs([{'dataset_id':key,'ref':v} for v in e[field]])
   consumer(c)
   provenance=c['historical_explanation']['access'].get('provenance',{})
   if provenance.get('origin')=='source_bound_network':add('NETWORK_RECORD',key,provenance['locator'])
  elif domain=='MAP':
   m=self.evidence.maps[id_];c=self.evidence.claims[id_][sub]
   for o in m['observations']:
    if o['id'] not in c['observation_ids']:continue
    for p in o['proposition_ids']:add('PROPOSITION',o['dataset_id'],p)
    for rel in o['relation_ids']:add('PRG_RELATION',o['dataset_id'],rel)
    source_refs(o['source_refs'])
    for h in o['historical_refs']:
     # Native cartography historical references are retained without inventing edges.
     if h['kind']=='HISTORICAL_EDGE':add('HISTORICAL_EDGE',o['dataset_id'],h['id'])
     elif h['kind']=='HISTORICAL_EXPLANATION':add('EXPLANATION',o['dataset_id'],h['id'])
  elif domain=='NOVELTY':
   c=self.novelty.claims[id_];o=self.novelty.objects[c['object_id']];u=self.novelty.universes[c['universe_id']]
   for p in o['proposition_ids']:add('PROPOSITION',o['dataset_id'],p)
   for rel in o['relation_ids']:add('PRG_RELATION',o['dataset_id'],rel)
   source_refs(o['source_refs'])
   for ref in o['cartography_refs']:add('MAP',key,ref['map_id'],ref['claim_id'])
   for unit in self.novelty.units[u['id']].values():source_refs(unit['record']['source_refs'])
  elif domain=='NETWORK_RECORD':
   r=self.network.records[id_]
   for p in r['anchor_proposition_ids']:add('PROPOSITION',key,p)
   source_refs([v for e in r['evidence']+r['counterevidence'] for v in e['source_refs']])
   for entity in ['source_entity_id','target_entity_id']:
    e=self.network.entities[r[entity]];out.add(('ENTITY',e['dataset_id'],e['id'],None));source_refs(e['evidence'])
   for c in r['temporal']['constraints']:source_refs(c['evidence'])
  elif domain=='ACCESS_PATH':
   for r in self.network.paths[id_]['record_ids']:add('NETWORK_RECORD',key,r)
  elif domain=='HISTORICAL_BINDING':
   b=self.network.bindings[id_];add('HISTORICAL_EDGE',key,b['historical_edge_id'])
   for p in b['path_ids']:add('ACCESS_PATH',key,p)
  elif domain=='HISTORICAL_EDGE':
   g=self.evidence.graphs[key];edge=g.edge(id_)
   for nodeid in [edge.source_node_id,edge.target_node_id]:
    node=g.node(nodeid)
    for ds,dossier in self.evidence.dossiers.items():
     if dossier.dossier_id==node.dossier_id and node.proposition_id:add('PROPOSITION',ds,node.proposition_id)
   for b in self.network.bindings.values():
    if b['anchor_dataset_id']==key and b['historical_edge_id']==id_:
     for p in b['path_ids']:add('ACCESS_PATH',key,p)
  return out

 def analysis(self,key):
  d=self.evidence.dossiers[key]
  for i in self.interventions.values():
   t=i['target'];domain,ds,id_,_=self.key(t)
   if ds!=key or i['operation']!='COLLAPSE_DERIVATIVE':continue
   old=self.evidence.registries[ds].roots(id_);other=i['related_target'];new=self.evidence.registries[other['dataset_id']].roots(other['id'])
   d=replace(d,propositions=tuple(replace(p,source_links=tuple(replace(link,evidence_roots=tuple(sorted((set(link.evidence_roots)-old)|new))) if set(link.evidence_roots)&old else link for link in p.source_links)) for p in d.propositions))
  roots=[UncertaintyRoot.from_dict(root.to_dict(),d) for root in self.evidence.analyses[key].roots]
  for i in self.interventions.values():
   t=i['target'];domain,ds,id_,_=self.key(t)
   if ds!=key or domain not in {'PROPOSITION','REPRESENTATION','PRG_RELATION'} or i['operation']=='COLLAPSE_DERIVATIVE':continue
   origin='SOURCE_ATTRIBUTION' if i['operation']=='ATTRIBUTION_DOWNGRADE' else 'TRANSLATION' if i['operation']=='TRANSLATION_CREATED' else 'OTHER'
   root={'root_id':'scenario:'+i['id'],'dossier_id':d.dossier_id,'subject_kind':{'PRG_RELATION':'RELATION'}.get(domain,domain),'subject_id':id_,'origin_type':origin,'rationale':i['rationale'],'provenance':{'origin':'hypothetical_scenario','locator':self.scenario['id']}}
   roots.append(UncertaintyRoot.from_dict(root,d))
  return DependencyUncertaintyAnalysis(d,roots)

 def source_dependencies(self,refs):
  out=set()
  for ref in refs:
   key=ref['dataset_id'];reg=self.evidence.registries[key]
   out.update(('REPRESENTATION',key,a,None) for a in reg.dependency_scope(ref['ref']['representation_id']))
  return out

 def network_effect(self,id_,affected):
  """Preserve separately documented support without treating it as a vote count."""
  r=self.network.records[id_];before=self.network.record_result(id_)
  protected=set()
  for pid in r['anchor_proposition_ids']:
   protected.update(self.dependencies({'domain':'PROPOSITION','dataset_id':r['anchor_dataset_id'],'id':pid,'sub_id':None}))
  for name in ['source_entity_id','target_entity_id']:
   e=self.network.entities[r[name]];protected.add(('ENTITY',e['dataset_id'],e['id'],None));protected.update(self.source_dependencies(e['evidence']))
  for c in r['temporal']['constraints']:protected.update(self.source_dependencies(c['evidence']))
  if any(self.key(i['target']) in protected or i['target']['domain']!='REPRESENTATION' for i in affected):
   return ('COLLAPSES' if any(i['operation']=='REMOVE' for i in affected) else 'UNRESOLVED'),'UNRESOLVED_ACCESS'
  # Only documentary corroboration is affected. Every surviving item must still
  # meet the original inspection/verification contract. Derivative roots are not
  # separate paths and no number of weak items substitutes for inspected content.
  survivors=[]
  for e in self.network.bases[id_]['positive']:
   deps=self.source_dependencies(e['record']['source_refs'])
   if e['qualifies'] and not any(self.key(i['target']) in deps and i['operation']!='COLLAPSE_DERIVATIVE' for i in affected):survivors.append(e)
  kinds={e['record']['kind'] for e in survivors};after=copy.deepcopy(before)
  after['roots']=sorted({root for e in survivors for ref in e['sources'] for root in ref['roots']})
  for i in affected:
   if i['operation']=='COLLAPSE_DERIVATIVE':
    t=i['target'];other=i['related_target'];old=self.evidence.registries[t['dataset_id']].roots(t['id']);new=self.evidence.registries[other['dataset_id']].roots(other['id'])
    after['roots']=sorted((set(after['roots'])-old)|new)
  required={'NETWORK_DOCUMENTATION'} if before['documented_network'] else set()
  if before['access']['state']=='ESTABLISHED':required.add('ACCESS_DOCUMENTATION')
  if before['possession']=='DOCUMENTED_POSSESSION':required.add('POSSESSION_DOCUMENTATION')
  if before['use']=='EVIDENCE_OF_ACTUAL_USE':required.add('USE_DOCUMENTATION')
  missing=required-kinds
  if not missing:return ('REMAINS_SECURE' if all(i['operation']=='REMOVE' for i in affected) else 'WEAKENS'),after
  if 'NETWORK_DOCUMENTATION' in missing:
   after['documented_network']=False;after['access']['state']='UNRESOLVED'
  elif 'ACCESS_DOCUMENTATION' in missing:after['access']['state']='PLAUSIBLE'
  if 'POSSESSION_DOCUMENTATION' in missing:after['possession']='NOT_ESTABLISHED'
  if 'USE_DOCUMENTATION' in missing:after['use']='NOT_ESTABLISHED'
  return ('COLLAPSES' if any(i['operation']=='REMOVE' for i in affected) else 'UNRESOLVED') if 'NETWORK_DOCUMENTATION' in missing else 'WEAKENS',after

 def evaluate(self,t):
  domain,key,id_,sub=self.key(t);deps=self.dependencies(t);affected=[i for i in self.interventions.values() if self.key(i['target']) in deps]
  before=None;paths=[];outcome='REMAINS_SECURE';after=None
  if domain=='PROPOSITION':
   baseline=self.evidence.analyses[key].analyze(id_).to_dict();result=self.analysis(key).analyze(id_).to_dict();before=baseline['state'];after=result['state'];paths=result['root_impacts']
   relevant=[p for p in paths if p['effect']!='IRRELEVANT'];affected=[i for i in self.interventions.values() if any(p['root_id']=='scenario:'+i['id'] for p in relevant)]
   removed={i['id'] for i in affected if i['operation'] in {'REMOVE','INACCESSIBLE'}}
   if after=='UNAFFECTED':outcome='REMAINS_SECURE' if before=='UNAFFECTED' else 'REMAINS_AS_BASELINE'
   elif after=='MATERIALLY_UNCERTAIN':
    critical=any(p['effect']=='CRITICAL' and p['root_id'].split(':',1)[-1] in removed for p in relevant)
    own_removed=any(i['target']==t and i['operation']=='REMOVE' for i in affected)
    outcome='COLLAPSES' if critical or own_removed else 'UNRESOLVED'
   elif after=='WEAKENED':outcome='REMAINS_SECURE' if removed and result['surviving_independent_support'] and all(i['operation']=='REMOVE' for i in affected) else 'WEAKENS'
   elif after=='QUALIFIED':outcome='WEAKENS'
   else:outcome='UNRESOLVED'
   if any(i['target']==t and i['operation']=='REMOVE' for i in affected):outcome='COLLAPSES'
   paths=[{'native_uncertainty':result}]
  elif domain in {'NETWORK_RECORD','ACCESS_PATH','HISTORICAL_BINDING','HISTORICAL_EDGE'}:
   if domain=='NETWORK_RECORD':before=self.network.record_result(id_)
   elif domain=='ACCESS_PATH':before=self.network.path_bases[id_]['result']
   elif domain=='HISTORICAL_BINDING':before=self.network.binding_bases[id_]['result']
   else:before=self.evidence.graphs[key].edge(id_).relation_type
   after=before
   if affected:
    if domain=='NETWORK_RECORD':outcome,after=self.network_effect(id_,affected)
    elif domain=='ACCESS_PATH':
     effects=[]
     for rid in self.network.paths[id_]['record_ids']:
      rt={'domain':'NETWORK_RECORD','dataset_id':key,'id':rid,'sub_id':None};deps_r=self.dependencies(rt)
      local=[i for i in affected if self.key(i['target']) in deps_r]
      if local:effects.append(self.network_effect(rid,local)[0])
     outcome='COLLAPSES' if 'COLLAPSES' in effects or any(i['operation']=='INACCESSIBLE' for i in affected) else 'REMAINS_SECURE' if all(e=='REMAINS_SECURE' for e in effects) else 'WEAKENS'
     after=before if outcome=='REMAINS_SECURE' else 'IMPOSSIBLE' if outcome=='COLLAPSES' else 'UNRESOLVED'
    else:
     bound=[b for b in self.network.bindings.values() if b['anchor_dataset_id']==key and (b['id']==id_ if domain=='HISTORICAL_BINDING' else b['historical_edge_id']==id_)]
     surviving=[]
     for b in bound:
      for pid in b['path_ids']:
       pt={'domain':'ACCESS_PATH','dataset_id':key,'id':pid,'sub_id':None}
       if self.evaluate(pt)['outcome'] in {'REMAINS_SECURE','REMAINS_AS_BASELINE'} and self.network.path_bases[pid]['result'] in {'POSSIBLE_ACCESS','SUPPORTED_ACCESS'}:surviving.append(pid)
     native_deps=set()
     for b in bound:
      graph=self.evidence.graphs[key];edge=graph.edge(b['historical_edge_id']);native_deps.add(('HISTORICAL_EDGE',key,edge.edge_id,None))
      for nid in [edge.source_node_id,edge.target_node_id]:
       node=graph.node(nid)
       for ds,dossier in self.evidence.dossiers.items():
        if dossier.dossier_id==node.dossier_id and node.proposition_id:native_deps.update(self.dependencies({'domain':'PROPOSITION','dataset_id':ds,'id':node.proposition_id,'sub_id':None}))
     only_path=all(self.key(i['target']) not in native_deps for i in affected)
     if surviving and only_path:outcome='REMAINS_SECURE'
     elif any(i['target']==t and i['operation']=='REMOVE' for i in affected):outcome='COLLAPSES';after='UNRESOLVED'
     else:outcome='RELATION_TYPE_CHANGES';after='UNRESOLVED'
  elif affected:outcome='UNRESOLVED';after='REVALIDATION_REQUIRED'
  # Other native consumers have no universal importance rule. Material affected
  # evidence requires re-adjudication rather than invented macro classifications.
  if domain in {'MAP','NOVELTY','EXPLANATION'} and affected:
   outcome='UNRESOLVED';after='REVALIDATION_REQUIRED'
  confidence='secure'
  if domain=='NETWORK_RECORD':confidence=self.network.records[id_]['confidence']
  elif domain=='ACCESS_PATH':confidence='secure' if before=='SUPPORTED_ACCESS' else 'possible' if before=='POSSIBLE_ACCESS' else 'unresolved'
  elif domain in {'HISTORICAL_EDGE','HISTORICAL_BINDING'}:
   edge_id=id_ if domain=='HISTORICAL_EDGE' else self.network.bindings[id_]['historical_edge_id'];confidence=self.evidence.graphs[key].edge(edge_id).confidence if domain=='HISTORICAL_EDGE' else self.network.binding_bases[id_]['confidence']
  elif domain=='EXPLANATION':confidence=self.evidence.registries[key].argument.consumers[id_]['historical_explanation']['confidence']
  elif domain=='MAP':confidence=self.evidence.claims[id_][sub]['confidence']
  elif domain=='NOVELTY':confidence=self.novelty.claims[id_]['confidence']
  if outcome=='REMAINS_SECURE' and confidence!='secure':outcome='REMAINS_AS_BASELINE'
  return {'target':copy.deepcopy(t),'outcome':outcome,'before':before,'after':after,'affected_intervention_ids':[i['id'] for i in affected],'dependency_path':[list(k) for k in sorted(deps,key=str) if k!=self.key(t)],'native_paths':paths,'hypothetical':True,'evidence_confidence_before':confidence,'confidence_promoted':False,'interpretation':'Support under the stated scenario; no historical fact or canonical correction is established.'}

 def results(self):return copy.deepcopy(list(self.views.values()))
 def render(self):
  lines=['Hypothetical historical sensitivity scenario. Canonical evidence remains unchanged.',self.scenario['rationale']]
  for i in self.interventions.values():lines.append('Suppose '+i['operation'].replace('_',' ').lower()+': '+i['rationale'])
  for r in self.results():lines.append(r['target']['domain'].replace('_',' ').capitalize()+' '+r['target']['id']+': '+r['outcome'].replace('_',' ').lower()+'. Affected interventions: '+(', '.join(r['affected_intervention_ids']) or 'none')+'.')
  lines.append('These results test support under hypothetical conditions. Actual evidence corrections require ordinary canonical revision and revalidation.')
  return '\n\n'.join(lines)

def prepare_scenario(value):
 out=copy.deepcopy(value);s=out['scenario'];s['snapshot']=fingerprint({'canonical':out['infrastructure'],'novelty':out['novelty'],'scenario':{k:v for k,v in s.items() if k!='snapshot'}})
 Sensitivity(out);return out

def validate_completion(directory,checkpoint,rendered_text,registry):
 from pathlib import Path
 import task_state
 p=Path(directory)/'hti-historical-sensitivity.json';claims=[c for c in checkpoint.get('claims',[]) if c.get('claim_type')=='historical_sensitivity']
 from evidence_audit import selected_domain_ids, selected_domain_claims
 selected=selected_domain_ids(checkpoint,"historical_sensitivity");claims=selected_domain_claims(checkpoint,"historical_sensitivity")
 if not selected:return
 need(p.is_file(),'SENSITIVITY_INPUT_REQUIRED')
 need(not p.is_symlink(),'SENSITIVITY_INPUT_SYMLINK');pub=task_state.require_ready(directory)
 need(p.name in task_state.current_draft(directory,pub)['inputs'],'SENSITIVITY_CURRENT_STAGING_REQUIRED')
 obj=Sensitivity(json.loads(p.read_text()));need(obj.scenario['work_id']==checkpoint.get('work_id'),'SENSITIVITY_CURRENT_WORK')
 need(any(d['integrity']==registry.raw and obj.evidence.registries[k].work_id==checkpoint.get('work_id') for k,d in obj.evidence.datasets.items()),'SENSITIVITY_CURRENT_TASK_SOURCE')
 network_path=Path(directory)/'hti-historical-infrastructure.json';need(network_path.exists() and json.loads(network_path.read_text())==obj.network.raw,'SENSITIVITY_CANONICAL_INPUT_BINDING')
 need(selected=={obj.scenario['id']} and len(claims)==1 and claims[0].get('sensitivity_id')==obj.scenario['id'],'SENSITIVITY_OUTPUT_BINDING')
 output=obj.render();need(claims[0].get('sensitivity_sha256')==hashlib.sha256(output.encode()).hexdigest(),'SENSITIVITY_OUTPUT_HASH');need(output in rendered_text,'SENSITIVITY_OUTPUT_NOT_VISIBLE')
