"""Source-bound historical access records; not a second Historical Relation Graph."""
from __future__ import annotations
import copy, hashlib, json
from .cartography import Cartography, shape, text, rows, ids, table, fingerprint
from .historical_relations import AccessAssessment, ChronologyAssessment
from .model import ValidationError

SCHEMA='hti-historical-infrastructure-1'
RELATIONS=frozenset({'TEACHER_STUDENT','UNIVERSITY_PRESENCE','LIBRARY_OWNERSHIP',
 'BOOK_POSSESSION','PRINT_DISTRIBUTION','CORRESPONDENCE','TRANSLATION_NETWORK','SYNODAL_ECCLESIAL_CONTACT'})
DISCRIMINATING=frozenset({'DISTINCTIVE_WORDING','UNUSUAL_ORDERING','SHARED_OMISSION',
 'SHARED_MISTRANSLATION','SHARED_ERRONEOUS_CITATION','SHARED_TEXTUAL_VARIANT',
 'DISTINCTIVE_ABBREVIATION','AUTHORITY_SEQUENCE','EDITION_FEATURE'})

def need(ok,code,detail=''):
 if not ok:raise ValidationError('INFRASTRUCTURE_'+code+': '+str(detail))

def no_numbers(value):
 if isinstance(value,dict):
  need(not set(value)&{'probability','score','percentage','confidence_score'},'NUMERICAL_CONFIDENCE')
  for v in value.values():no_numbers(v)
 elif isinstance(value,list):
  for v in value:no_numbers(v)

def state(record,snapshot):
 need(record['status'] in {'CURRENT','REVALIDATION_REQUIRED'},'STATUS')
 need(isinstance(record['snapshot'],str) and len(record['snapshot'])==64,'SNAPSHOT')
 if record['status']=='CURRENT':need(record['snapshot']==snapshot,'REVALIDATION_REQUIRED',record['id'])

class Infrastructure:
 def __init__(self,value):
  shape(value,'schema_version evidence entities records paths bindings','infrastructure')
  need(value['schema_version']==SCHEMA,'SCHEMA');no_numbers(value)
  self.raw=copy.deepcopy(value);self.evidence=Cartography(self.raw['evidence'])
  self.entities=table(self.raw['entities'],'entities');self.records=table(self.raw['records'],'records')
  self.paths=table(self.raw['paths'],'paths');self.bindings=table(self.raw['bindings'],'bindings')
  self.bases={};self.path_bases={};self.binding_bases={}
  for e in self.entities.values():self.entity(e)
  for r in self.records.values():self.record(r)
  self.explanation_access()
  for p in self.paths.values():self.path(p)
  for b in self.bindings.values():self.binding(b)

 def anchor(self,key,props):
  need(key in self.evidence.datasets,'ANCHOR_DATASET');a=self.evidence.registries[key].argument
  for p in ids(props,'anchor propositions',True):a.permit_proposition(p,author_position=True)
  return {'work':self.evidence.licenses[key], 'propositions':{p:a.proposition_snapshot(p) for p in props},
          'uncertainty':[self.evidence.analyses[key].analyze(p).to_dict() for p in props],
          'date':self.evidence.datasets[key]['metadata']['date']}

 def entity(self,e):
  shape(e,'id kind name dataset_id evidence','entity');text(e['name'],'entity name')
  need(e['kind'] in {'ANCHOR_AUTHOR','SOURCE_WORK','INTERMEDIARY','PERSON','INSTITUTION','BOOK','PRINTER'},'ENTITY_KIND')
  self.evidence.source_refs(e['evidence'])
  if e['dataset_id'] is not None:need(e['dataset_id'] in self.evidence.datasets,'ENTITY_DATASET')
  if e['kind']=='ANCHOR_AUTHOR':
   need(e['dataset_id'] is not None and e['id']==self.evidence.datasets[e['dataset_id']]['metadata']['author_id'],'AUTHOR_IDENTITY')
  if e['kind']=='SOURCE_WORK':
   need(e['dataset_id'] is not None and e['id']==self.evidence.registries[e['dataset_id']].work_id,'SOURCE_WORK_IDENTITY')

 def evidence_item(self,e):
  shape(e,'id kind inspection verification source_refs assertion rationale','network evidence')
  need(e['kind'] in {'NETWORK_DOCUMENTATION','ACCESS_DOCUMENTATION','POSSESSION_DOCUMENTATION','USE_DOCUMENTATION','CHRONOLOGY','COUNTEREVIDENCE'},'EVIDENCE_KIND')
  need(e['inspection'] in {'PRIMARY_PASSAGE','PRIMARY_METADATA','SECONDARY_REPORT','OCR_LOCATOR','UNINSPECTED'},'INSPECTION')
  need(e['verification'] in {'VERIFIED','PROVISIONAL','UNRESOLVED','CONTRADICTED'},'VERIFICATION')
  text(e['assertion'],'supported assertion');text(e['rationale'],'inspection rationale')
  refs=self.evidence.source_refs(e['source_refs'])
  # Original-document claims require original inspection, not a translation of a record.
  if e['verification']=='VERIFIED' and e['inspection'] in {'PRIMARY_PASSAGE','PRIMARY_METADATA'}:
   for ref in refs:self.evidence.registries[ref['dataset_id']].permit(ref['representation_id'],'EXACT_ORIGINAL_WORDING',ref['span_ids'])
  if e['kind']=='USE_DOCUMENTATION':need(e['inspection']=='PRIMARY_PASSAGE','USE_REQUIRES_CONTENT_INSPECTION')
  return {'record':e,'sources':refs,'qualifies':e['verification']=='VERIFIED' and e['inspection'] in {'PRIMARY_PASSAGE','PRIMARY_METADATA'}}

 def chronology(self,r):
  t=shape(r['temporal'],'constraints rationale','temporal');text(t['rationale'],'chronology rationale')
  constraints=table(t['constraints'],'temporal constraints');need(bool(constraints),'CHRONOLOGY_REQUIRED')
  target=self.evidence.datasets[r['anchor_dataset_id']]['metadata']['date'];uncertain=target['state']!='SECURE';impossible=False
  bounds=[]
  for c in constraints.values():
   shape(c,'id kind state earliest latest evidence rationale','date constraint')
   need(c['kind'] in {'SOURCE','RELATION','INSTITUTION','POSSESSION','PRINT_DISTRIBUTION','CORRESPONDENCE','TRANSLATION'},'DATE_KIND')
   need(c['state'] in {'SECURE','UNCERTAIN','UNAVAILABLE'},'DATE_STATE');text(c['rationale'],'date rationale')
   self.evidence.source_refs(c['evidence'],required=c['state']!='UNAVAILABLE')
   if c['state']=='UNAVAILABLE':need(c['earliest'] is None and c['latest'] is None,'UNAVAILABLE_DATE');uncertain=True;continue
   need(type(c['earliest']) is int and type(c['latest']) is int and c['earliest']<=c['latest'],'DATE_RANGE')
   if target['latest'] is not None and c['earliest']>target['latest']:impossible=True
   if target['earliest'] is None or c['latest']>target['earliest'] or c['state']!='SECURE':uncertain=True
   bounds.append(c['latest'])
  source=self.entities[r['source_entity_id']]
  if source['kind']=='SOURCE_WORK':
   sd=self.evidence.datasets[source['dataset_id']]['metadata']['date']
   need(any(c['kind']=='SOURCE' and all(c[n]==sd[n] for n in ['state','earliest','latest']) for c in constraints.values()),'SOURCE_DATE_BINDING')
  need(any(c['kind']=='RELATION' for c in constraints.values()),'RELATION_INTERVAL_REQUIRED')
  source_dates=[c for c in constraints.values() if c['kind']=='SOURCE' and c['state']!='UNAVAILABLE']
  for source_date in source_dates:
   for event in constraints.values():
    if event['kind']=='SOURCE' or event['state']=='UNAVAILABLE':continue
    if source_date['earliest']>event['latest']:impossible=True
    elif source_date['latest']>event['earliest']:uncertain=True
  result='CONTRADICTED' if impossible else 'UNRESOLVED' if uncertain else 'COMPATIBLE'
  # Adapt to the inherited typed assessment rather than adding another historical taxonomy.
  assessment=ChronologyAssessment.from_dict({'state':result,'antecedent_year':max(bounds) if bounds and not impossible else None,'recipient_year':target['earliest'],'rationale':t['rationale'],'provenance':{'origin':'source_bound_network','locator':r['id']}})
  return assessment.to_dict()

 def record(self,r):
  shape(r,'id anchor_dataset_id anchor_proposition_ids source_entity_id target_entity_id relation_type claim_level geographic_scope institutional_scope temporal evidence counterevidence alternatives confidence rationale status snapshot','network record')
  anchor=self.anchor(r['anchor_dataset_id'],r['anchor_proposition_ids'])
  need(r['source_entity_id'] in self.entities and r['target_entity_id'] in self.entities and r['source_entity_id']!=r['target_entity_id'],'ENTITY_REFERENCE')
  need(r['relation_type'] in RELATIONS,'RELATION_TYPE')
  need(r['claim_level'] in {'WORK','EDITION','EXEMPLAR'},'CLAIM_LEVEL')
  if r['claim_level']!='WORK':need(self.evidence.licenses[r['anchor_dataset_id']]['scope'][r['claim_level'].lower()+'_id'] is not None,'CLAIM_LEVEL_LICENSE')
  for name in ['geographic_scope','institutional_scope','rationale']:text(r[name],name)
  need(r['confidence'] in {'secure','probable','possible','unresolved'},'CONFIDENCE')
  ids(r['alternatives'],'unresolved alternatives')
  positive=[self.evidence_item(x) for x in table(r['evidence'],'positive evidence').values()]
  counter=[self.evidence_item(x) for x in table(r['counterevidence'],'counterevidence').values()]
  need(bool(positive),'POSITIVE_EVIDENCE_REQUIRED')
  chronology=self.chronology(r);qualified=[e for e in positive if e['qualifies']]
  documented=any(e['record']['kind']=='NETWORK_DOCUMENTATION' for e in qualified)
  need(r['confidence']!='secure' or documented,'UNDOCUMENTED_NETWORK')
  contradicted=bool([e for e in counter if e['qualifies']]) or any(e['record']['verification']=='CONTRADICTED' for e in positive)
  kinds={e['record']['kind'] for e in qualified}
  impossible=chronology['state']=='CONTRADICTED'
  access='IMPOSSIBLE' if impossible else 'UNRESOLVED' if contradicted or not documented else 'ESTABLISHED' if chronology['state']=='COMPATIBLE' and 'ACCESS_DOCUMENTATION' in kinds else 'PLAUSIBLE'
  possession=not impossible and not contradicted and chronology['state']=='COMPATIBLE' and 'POSSESSION_DOCUMENTATION' in kinds
  if possession:need(r['relation_type'] in {'LIBRARY_OWNERSHIP','BOOK_POSSESSION'},'POSSESSION_RELATION')
  use=not impossible and not contradicted and chronology['state']=='COMPATIBLE' and 'USE_DOCUMENTATION' in kinds
  roots=sorted({root for e in qualified for ref in e['sources'] for root in ref['roots']})
  result={'documented_network':documented,'chronology':chronology,'access':AccessAssessment.from_dict({'state':access,'channel':r['relation_type'],'rationale':r['rationale'],'provenance':{'origin':'source_bound_network','locator':r['id']}}).to_dict(),'possession':'DOCUMENTED_POSSESSION' if possession else 'NOT_ESTABLISHED','use':'EVIDENCE_OF_ACTUAL_USE' if use else 'NOT_ESTABLISHED','dependence':'NOT_ADJUDICATED','roots':roots}
  basis={'record':{k:v for k,v in r.items() if k not in {'status','snapshot'}},'anchor':anchor,'entities':[self.entities[r[k]] for k in ['source_entity_id','target_entity_id']], 'positive':positive,'counter':counter,'result':result}
  self.bases[r['id']]=basis;state(r,fingerprint(basis));return result

 def explanation_access(self):
  # Reuse the native typed AccessAssessment provenance as an explicit binding.
  # Unbound Stage8 claims acquire no network dependency.
  for key,registry in self.evidence.registries.items():
   for consumer in registry.argument.consumers.values():
    p=consumer.get('historical_explanation')
    if p is None:continue
    provenance=p['access'].get('provenance',{})
    if provenance.get('origin')!='source_bound_network':continue
    rid=provenance.get('locator');need(rid in self.records,'EXPLANATION_ACCESS_REFERENCE')
    r=self.records[rid]
    need(r['anchor_dataset_id']==key and set(p['anchor_proposition_ids'])<=set(r['anchor_proposition_ids']),'EXPLANATION_ACCESS_ANCHOR')
    if consumer['status']=='CURRENT':need(p['access']['state']==self.record_result(rid)['access']['state'],'EXPLANATION_NETWORK_REVALIDATION_REQUIRED',consumer['id'])

 def record_result(self,key):return copy.deepcopy(self.bases[key]['result'])
 def path(self,p):
  shape(p,'id anchor_dataset_id anchor_proposition_ids record_ids rationale status snapshot','path')
  anchor=self.anchor(p['anchor_dataset_id'],p['anchor_proposition_ids']);text(p['rationale'],'path rationale')
  keys=ids(p['record_ids'],'path records',True);need(set(keys)<=self.records.keys(),'PATH_RECORDS')
  chain=[self.records[k] for k in keys]
  need(all(r['anchor_dataset_id']==p['anchor_dataset_id'] and set(r['anchor_proposition_ids'])==set(p['anchor_proposition_ids']) for r in chain),'PATH_ANCHOR')
  need(all(a['target_entity_id']==b['source_entity_id'] for a,b in zip(chain,chain[1:])),'PATH_CONTINUITY')
  visited=[chain[0]['source_entity_id']]+[r['target_entity_id'] for r in chain];need(len(visited)==len(set(visited)),'PATH_CYCLE')
  end=self.entities[visited[-1]];need(end['kind']=='ANCHOR_AUTHOR' and end['dataset_id']==p['anchor_dataset_id'],'PATH_TARGET')
  result='IMPOSSIBLE' if any(self.record_result(k)['access']['state']=='IMPOSSIBLE' for k in keys) else 'UNRESOLVED' if any(self.record_result(k)['access']['state']=='UNRESOLVED' for k in keys) else 'SUPPORTED_ACCESS' if all(self.record_result(k)['access']['state']=='ESTABLISHED' for k in keys) else 'POSSIBLE_ACCESS'
  intervals=[next(c for c in r['temporal']['constraints'] if c['kind']=='RELATION') for r in chain]
  for earlier,later in zip(intervals,intervals[1:]):
   if earlier['state']=='UNAVAILABLE' or later['state']=='UNAVAILABLE':
    if result!='IMPOSSIBLE':result='UNRESOLVED'
   elif earlier['earliest']>later['latest']:result='IMPOSSIBLE'
   elif earlier['latest']>later['earliest'] and result!='IMPOSSIBLE':result='UNRESOLVED'
  basis={'path':{k:v for k,v in p.items() if k not in {'status','snapshot'}},'anchor':anchor,'records':[self.bases[k] for k in keys],'result':result};self.path_bases[p['id']]=basis;state(p,fingerprint(basis));return result

 def binding(self,b):
  shape(b,'id anchor_dataset_id anchor_proposition_ids historical_edge_id path_ids rationale status snapshot','historical binding')
  self.anchor(b['anchor_dataset_id'],b['anchor_proposition_ids']);text(b['rationale'],'binding rationale')
  key=b['anchor_dataset_id'];need(key in self.evidence.graphs,'HISTORICAL_GRAPH_REQUIRED')
  edge=self.evidence.graphs[key].edge(b['historical_edge_id'])
  need(edge.relation_type in {'DIRECT_DEPENDENCE','MEDIATED_DEPENDENCE','RECEPTION','DIRECT_QUOTATION'},'BINDING_RELATION')
  target=self.evidence.graphs[key].node(edge.target_node_id)
  need(target.dossier_id==self.evidence.dossiers[key].dossier_id and target.proposition_id in b['anchor_proposition_ids'],'HISTORICAL_ANCHOR')
  keys=ids(b['path_ids'],'bound access paths',True);need(set(keys)<=self.paths.keys(),'BINDING_PATHS')
  need(all(self.paths[k]['anchor_dataset_id']==key for k in keys),'BINDING_WORK')
  for k in keys:
   path=self.paths[k];source=self.entities[self.records[path['record_ids'][0]]['source_entity_id']]
   source_node=self.evidence.graphs[key].node(edge.source_node_id)
   need(source['kind']=='SOURCE_WORK' and source['dataset_id'] is not None and source_node.dossier_id==self.evidence.dossiers[source['dataset_id']].dossier_id,'PATH_SOURCE_BINDING')
  eraw=edge.to_dict()
  if edge.active and edge.relation_type in {'DIRECT_DEPENDENCE','MEDIATED_DEPENDENCE'}:
   need(any(e.kind in DISCRIMINATING and e.to_dict()['inspection_level']=='PRIMARY_PASSAGE' for e in edge.discriminating_features),'DISCRIMINATING_CORRESPONDENCE_REQUIRED')
  feasible=any(self.path_bases[k]['result'] in {'POSSIBLE_ACCESS','SUPPORTED_ACCESS'} for k in keys)
  if b['status']=='CURRENT' and not feasible:need(not edge.active,'CANONICAL_HISTORICAL_REVALIDATION_REQUIRED',b['historical_edge_id'])
  result=edge.relation_type if feasible and edge.active else 'UNRESOLVED'
  confidence=edge.confidence if any(self.path_bases[k]['result']=='SUPPORTED_ACCESS' for k in keys) else 'possible' if feasible else 'unresolved'
  basis={'record':{k:v for k,v in b.items() if k not in {'status','snapshot'}},'edge':eraw,'paths':[self.path_bases[k] for k in keys],'result':result,'confidence':confidence};self.binding_bases[b['id']]=basis;state(b,fingerprint(basis));return result

 def render(self,domain,key):
  maps={'NETWORK_RECORD':(self.records,self.bases),'ACCESS_PATH':(self.paths,self.path_bases),'HISTORICAL_BINDING':(self.bindings,self.binding_bases)}
  need(domain in maps,'OUTPUT_DOMAIN');records,bases=maps[domain];r=records[key];need(r['status']=='CURRENT','NOT_CURRENT')
  lines=[domain.replace('_',' ').capitalize()+': '+key+'.',r['rationale']]
  if domain=='NETWORK_RECORD':
   out=self.record_result(key);lines += ['Relation: '+r['relation_type'].replace('_',' ').lower()+'. Chronology: '+out['chronology']['state'].lower()+'.','Access: '+out['access']['state'].lower()+'. Possession: '+out['possession'].replace('_',' ').lower()+'. Use: '+out['use'].replace('_',' ').lower()+'.','Historical dependence: separately adjudicated; network alone supplies no dependence claim.','Confidence: '+r['confidence']+'. Claim level: '+r['claim_level'].lower()+'.','Geographic scope: '+r['geographic_scope']+'. Institutional scope: '+r['institutional_scope']+'.','Independent original evidence roots: '+', '.join(out['roots'])+'.']
   for e in r['evidence']+r['counterevidence']:lines.append(e['kind'].replace('_',' ').lower()+': '+e['assertion']+' ['+e['inspection'].replace('_',' ').lower()+'; '+e['verification'].lower()+'].')
   if r['alternatives']:lines.append('Unresolved alternatives: '+'; '.join(r['alternatives'])+'.')
  else:lines += ['Result: '+bases[key]['result'].replace('_',' ').lower()+'.','A plausible access path does not prove that it was used.']
  if domain=='HISTORICAL_BINDING':lines.append('Evidence confidence: '+bases[key]['confidence']+'. Access uncertainty remains separate from the native relation type.')
  return '\n\n'.join(lines)
 def current_outputs(self):
  return {d+':'+k:self.render(d,k) for d,rs in [('NETWORK_RECORD',self.records),('ACCESS_PATH',self.paths),('HISTORICAL_BINDING',self.bindings)] for k,r in rs.items() if r['status']=='CURRENT'}

def revalidate(value):
 out=copy.deepcopy(value)
 for name in ['records','paths','bindings']:
  for r in out[name]:r['status']='REVALIDATION_REQUIRED'
 obj=Infrastructure(out)
 for name,bases in [('records',obj.bases),('paths',obj.path_bases),('bindings',obj.binding_bases)]:
  for r in out[name]:r.update(status='CURRENT',snapshot=fingerprint(bases[r['id']]))
 Infrastructure(out);return out

def validate_completion(directory,checkpoint,rendered_text,registry):
 from pathlib import Path
 import task_state
 path=Path(directory)/'hti-historical-infrastructure.json';claims=[c for c in checkpoint.get('claims',[]) if c.get('claim_type')=='historical_infrastructure']
 from evidence_audit import selected_domain_ids, selected_domain_claims
 selected=selected_domain_ids(checkpoint,"historical_infrastructure");claims=selected_domain_claims(checkpoint,"historical_infrastructure")
 if not selected:return
 need(path.is_file(),'INPUT_REQUIRED')
 need(not path.is_symlink(),'INPUT_SYMLINK');pub=task_state.require_ready(directory)
 need(path.name in task_state.current_draft(directory,pub)['inputs'],'CURRENT_STAGING_REQUIRED')
 obj=Infrastructure(json.loads(path.read_text()));outputs=obj.current_outputs();need(bool(outputs),'CURRENT_OUTPUT_REQUIRED')
 current={k for k,d in obj.evidence.datasets.items() if d['integrity']==registry.raw and obj.evidence.registries[k].work_id==checkpoint.get('work_id')}
 for prefix,rs in [('NETWORK_RECORD',obj.records),('ACCESS_PATH',obj.paths),('HISTORICAL_BINDING',obj.bindings)]:
  for r in rs.values():
   if r['status']=='CURRENT' and prefix+':'+r['id'] in selected:need(r['anchor_dataset_id'] in current,'CURRENT_TASK_ANCHOR')
 need({c.get('infrastructure_id') for c in claims}==selected and selected<=set(outputs),'OUTPUT_BINDINGS')
 for c in claims:
  output=outputs[c['infrastructure_id']];need(c.get('infrastructure_sha256')==hashlib.sha256(output.encode()).hexdigest(),'OUTPUT_HASH');need(output in rendered_text,'OUTPUT_NOT_VISIBLE')
