"""Source-bound cartographic aggregation, separate from every evidence graph.

A task-local document embeds current lower-level evidence. No identity, historical
relation, authorial development, or significance is inferred from persistence.
"""
from __future__ import annotations
import copy
import hashlib
import json
import re
from .model import ValidationError
from .hashing import sha256_json
from .dependency_uncertainty import DependencyUncertaintyAnalysis
from .historical_relations import HistoricalRelationGraph

SCHEMA = 'hti-cartography-1'
DIMENSIONS = frozenset({'DOCTRINE','EXEGETICAL_METHOD','AUTHORITY','DISTINCTION',
    'SCRIPTURE_USE','THEOLOGICAL_STRUCTURE','INTERPRETIVE_HABIT','ARGUMENTATIVE_PATTERN',
    'STRUCTURAL_ROLE','PASTORAL_APPLICATION','POLITICAL_APPLICATION','POLEMICAL_CONCENTRATION',
    'SOURCE_TRANSMISSION','CONFESSIONAL_RELATION','TERMINOLOGY','DOCTRINAL_PLACEMENT'})
SIGNIFICANCE = frozenset({'DOCTRINAL_CENTRALITY','FORMULATION_FREQUENCY',
    'CONFIGURATION_FREQUENCY','STRUCTURAL_ROLE','LOCAL_POLEMICAL_INTENSITY','CROSS_LOCUS_INTEGRATION'})
ROLES = frozenset({'OCCURRENCE','STRUCTURAL_DEPENDENCY','INTEGRATION','TRANSITION',
    'LOCAL_INTENSITY','BOUNDED_DISTRIBUTION','BOUNDED_CONTRAST','PERIPHERAL_FUNCTION'})
LABELS = frozenset({'central','representative','exceptional','integrative','transitional','peripheral'})
CONFOUNDS = frozenset({'GENRE','AUDIENCE','LOCAL_CONTROVERSY','SOURCE_AVAILABILITY',
    'SOURCE_BASE','EDITION','TRANSLATOR','EDITOR','COVERAGE','OCCASION'})
DEVELOPMENT_DIMENSIONS = frozenset({'TERMINOLOGY','AUTHORITY','EXEGETICAL_METHOD',
    'DISTINCTION','DOCTRINAL_PLACEMENT','POLEMICAL_CONCENTRATION','ARGUMENTATIVE_PATTERN'})
CORPUS_STATES = frozenset({'SUFFICIENT_WHOLE_WORK','SECURE_PARTIAL','INCOMPLETE','UNRESOLVED_BOUNDARY'})


def need(ok, code, detail=''):
    if not ok: raise ValidationError('CARTOGRAPHY_'+code+': '+str(detail))


def shape(value, fields, name):
    need(isinstance(value,dict) and set(value)==set(fields.split()), 'FIELDS', name)
    return value


def text(value, name):
    need(isinstance(value,str) and value.strip(), 'TEXT', name)
    return value


def rows(value, name):
    need(isinstance(value,list),'LIST',name)
    return value


def ids(value, name, required=False):
    rows(value,name)
    for x in value: text(x,name)
    need(len(set(value))==len(value) and (bool(value) or not required),'IDS',name)
    return value


def table(value, name):
    out={}
    for item in rows(value,name):
        need(isinstance(item,dict),'OBJECT',name)
        key=text(item.get('id'),name)
        need(key not in out,'DUPLICATE_ID',key);out[key]=item
    return out


def fingerprint(value): return sha256_json(value)


class Cartography:
    """Audited datasets, scoped maps and dependent developmental/comparative claims."""
    def __init__(self,value):
        shape(value,'schema_version datasets corpora maps comparisons','document')
        need(value['schema_version']==SCHEMA,'SCHEMA',value['schema_version'])
        self.raw=copy.deepcopy(value)
        self.datasets=table(self.raw['datasets'],'datasets')
        self.corpora=table(self.raw['corpora'],'corpora')
        self.maps=table(self.raw['maps'],'maps')
        self.comparisons=table(self.raw['comparisons'],'comparisons')
        self.registries={};self.dossiers={};self.analyses={};self.licenses={};self.graphs={}
        self.observations={};self.claims={};self.coverage={};self._validate()

    def source_refs(self,refs,required=True):
        rows(refs,'source_refs');need(bool(refs) or not required,'SOURCE_REQUIRED')
        out=[]
        for item in refs:
            shape(item,'dataset_id ref','source reference')
            key=item['dataset_id'];need(key in self.registries,'DATASET_REFERENCE',key)
            a=self.registries[key].argument;n,spans=a.ref(item['ref'])
            need(a.ref_current(item['ref']) and a.source_current(n),'SOURCE_REVALIDATION',key)
            a.r.permit(n,'REPRESENTED_ARGUMENT',spans)
            out.append({'dataset_id':key,'representation_id':n,'span_ids':spans,
                        'current_snapshot':a.r.parent_snapshot(n,spans),'roots':sorted(a.r.roots(n))})
        return out

    def _validate_dataset(self,d):
        shape(d,'id identity_checkpoint identity_binding metadata integrity source_registry dossier uncertainty_request historical_graph','dataset')
        import source_integrity
        import specialization_core
        key=d['id'];r=source_integrity.IntegrityRegistry(d['integrity'])
        need(r.argument is not None,'ARGUMENT_REQUIRED',key)
        self.registries[key]=r
        license=specialization_core.identity_license(d['identity_checkpoint'],d['identity_binding'])
        need(license['identity_state'] in {'WORK_ESTABLISHED','EDITION_ESTABLISHED','EXEMPLAR_ESTABLISHED'},'IDENTITY_REQUIRED',key)
        need(license['scope']['work_id']==r.work_id,'WORK_IDENTITY',key)
        self.licenses[key]=license
        native=r.argument.validate_native(d['dossier'],d['source_registry'])
        self.dossiers[key]=native
        self.analyses[key]=DependencyUncertaintyAnalysis.from_dict(d['uncertainty_request'],native)

    def _validate_metadata(self,key,d):
        m=shape(d['metadata'],'author_id genre audience period source_form source_base availability date evidence','metadata')
        for name in ('author_id','genre','audience','period','source_form','source_base','availability'):text(m[name],name)
        need(self.licenses[key]['identity_snapshots']['work_id']['claim'].get('author_id')==m['author_id'],'AUTHOR_IDENTITY',key)
        need(m['source_form']==self.registries[key].nodes[d['dossier']['anchor_representation_id']]['type'],'SOURCE_FORM_METADATA',key)
        self.source_refs(m['evidence'])
        need(all(x['dataset_id']==key for x in m['evidence']),'METADATA_SOURCE_WORK',key)
        date=shape(m['date'],'state subject earliest latest evidence rationale','date')
        need(date['state'] in {'SECURE','UNCERTAIN','UNAVAILABLE'},'DATE_STATE',key)
        text(date['rationale'],'date rationale')
        need(date['subject'] in {'WORK_COMPOSITION','WORK_PUBLICATION','EDITION_PUBLICATION','TRANSLATION_PUBLICATION','UNRESOLVED'},'DATE_SUBJECT',key)
        if date['subject']=='EDITION_PUBLICATION':need(self.licenses[key]['scope']['edition_id'] is not None,'DATE_EDITION_LICENSE',key)
        if date['state']=='UNAVAILABLE':
            need(date['earliest'] is None and date['latest'] is None,'UNAVAILABLE_DATE',key)
        else:
            need(type(date['earliest']) is int and type(date['latest']) is int and date['earliest']<=date['latest'],'DATE_RANGE',key)
        self.source_refs(date['evidence'],required=date['state']!='UNAVAILABLE')
        need(all(x['dataset_id']==key for x in date['evidence']),'DATE_SOURCE_WORK',key)

    def _validate_corpus(self,c):
        shape(c,'id work_id state boundary inventory evidence rationale limitations','corpus')
        need(c['state'] in CORPUS_STATES,'CORPUS_STATE',c['id'])
        text(c['boundary'],'boundary');text(c['rationale'],'corpus rationale');ids(c['limitations'],'corpus limitations')
        self.source_refs(c['evidence'])
        need(all(self.registries[x['dataset_id']].work_id==c['work_id'] for x in c['evidence']),'CORPUS_EVIDENCE_WORK',c['id'])
        inventory=table(c['inventory'],'inventory');need(bool(inventory),'INVENTORY_REQUIRED',c['id'])
        for p in inventory.values():
            shape(p,'id status dataset_ids rationale','portion')
            need(p['status'] in {'INSPECTED','UNINSPECTED','UNAVAILABLE'},'PORTION_STATUS',p['id'])
            text(p['rationale'],'portion rationale');ids(p['dataset_ids'],'portion datasets')
            if p['status']=='INSPECTED':need(bool(p['dataset_ids']),'INSPECTED_DATASET_REQUIRED',p['id'])
            else:need(not p['dataset_ids'],'UNINSPECTED_AS_EVIDENCE',p['id'])
            for key in p['dataset_ids']:
                need(key in self.datasets and self.registries[key].work_id==c['work_id'],'CORPUS_WRONG_WORK',key)
        if c['state']=='SUFFICIENT_WHOLE_WORK':
            need(all(p['status']=='INSPECTED' for p in inventory.values()),'INCOMPLETE_WHOLE_WORK',c['id'])
        if c['state']!='SUFFICIENT_WHOLE_WORK':need(bool(c['limitations']),'INCOMPLETENESS_DISCLOSURE',c['id'])
        return inventory

    def observation(self,o,c,inventory):
        shape(o,'id dimension value role portion_id dataset_id proposition_ids relation_ids historical_refs source_refs rationale','observation')
        need(o['dimension'] in DIMENSIONS and o['role'] in ROLES,'OBSERVATION_TYPE',o['id'])
        text(o['value'],'observation value');text(o['rationale'],'observation rationale')
        key=o['dataset_id'];portion=inventory.get(o['portion_id'])
        need(portion is not None and portion['status']=='INSPECTED' and key in portion['dataset_ids'],'OBSERVATION_CORPUS',o['id'])
        r=self.registries[key];a=r.argument
        need(r.work_id==c['work_id'],'OBSERVATION_WRONG_WORK',o['id'])
        props=ids(o['proposition_ids'],'proposition ids',True)
        need(set(props)<=a.props.keys(),'PROPOSITION_REFERENCE',o['id'])
        for p in props:a.permit_proposition(p)
        refs=self.source_refs(o['source_refs'])
        need(all(x['dataset_id']==key for x in refs),'OBSERVATION_SOURCE_WORK',o['id'])
        if o['dimension']=='TERMINOLOGY':
            for source in refs:r.permit(source['representation_id'],'EXACT_ORIGINAL_WORDING',source['span_ids'])
        # Every proposition's actual source scope must intersect the cited source spans.
        for p in props:
            scopes=r.dependency_scope(a.props[p]['representation_id'])
            need(any(set(x['span_ids']) & scopes.get(x['representation_id'],set()) for x in refs),'PROPOSITION_SOURCE_ANCESTRY',p)
        relations={v.relation_id:v.to_dict() for v in self.dossiers[key].relations}
        selected=ids(o['relation_ids'],'relations')
        need(set(selected)<=relations.keys(),'RELATION_REFERENCE',o['id'])
        for n in selected:
            edge=relations[n]
            need({edge['source_proposition_id'],edge['target_proposition_id']}<=set(props),'RELATION_ENDPOINTS',n)
        if o['role'] in {'STRUCTURAL_DEPENDENCY','INTEGRATION','TRANSITION','PERIPHERAL_FUNCTION'}:
            need(bool(selected),'STRUCTURAL_RELATION_REQUIRED',o['id'])
            suitable={'STRUCTURAL_DEPENDENCY':{'DEPENDS_ON','REQUIRES','PRESUPPOSES','CONCLUDES_FROM','SUPPORTS'},
                      'INTEGRATION':{'INTERPRETS','QUALIFIES','DISTINGUISHES','SUPPORTS'},
                      'TRANSITION':{'CONCLUDES_FROM','INTERPRETS','QUALIFIES'},
                      'PERIPHERAL_FUNCTION':{'QUALIFIES','INTERPRETS'}}[o['role']]
            need(any(relations[n]['relation_type'] in suitable for n in selected),'STRUCTURAL_ROLE_BASIS',o['id'])
        history=[]
        for h in rows(o['historical_refs'],'historical refs'):
            shape(h,'kind id','historical ref')
            if h['kind']=='EXPLANATION':
                consumer=a.consumers.get(h['id'])
                need(consumer is not None and 'historical_explanation' in consumer and a.consumer_current(h['id']),'EXPLANATION_CURRENT',h['id'])
                from .historical_explanation import validate_consumer
                validate_consumer(a,consumer)
                # Local explanation supplies only its actual local intensity dimension.
                need(o['dimension']=='POLEMICAL_CONCENTRATION' and o['role']=='LOCAL_INTENSITY','PRESSURE_MACRO_INFLATION',o['id'])
                history.append({'kind':h['kind'],'id':h['id'],'snapshot':a.consumer_snapshot(h['id']),
                    'classification':consumer['historical_explanation'].get('classification'),
                    'confidence':consumer['historical_explanation']['confidence'],'limitations':consumer['historical_explanation']['limitations']})
            elif h['kind']=='HISTORICAL_EDGE':
                need(key in self.graphs,'HISTORICAL_GRAPH_REQUIRED',key)
                edges={e['edge_id']:e for e in self.graphs[key].to_dict()['edges']}
                need(h['id'] in edges and o['dimension']=='SOURCE_TRANSMISSION','HISTORICAL_REFERENCE',h['id'])
                nodes={n['node_id']:n for n in self.graphs[key].to_dict()['nodes']}
                edge=edges[h['id']]
                need(any(nodes[n]['dossier_id']==self.dossiers[key].dossier_id and
                         (nodes[n].get('proposition_id') in props or nodes[n]['node_kind']=='ARGUMENT')
                         for n in [edge['source_node_id'],edge['target_node_id']]),'HISTORICAL_ANCHOR',h['id'])
                history.append(edge)
            else:need(False,'DOMAIN_REFERENCE',h['kind'])
        origins=set()
        for p in props:
            scopes=r.dependency_scope(a.props[p]['representation_id'])
            for n,spans in scopes.items():
                if not r.nodes[n]['parents']:
                    origins.update((root,s) for root in r.roots(n) for s in spans)
        states={p:self.analyses[key].analyze(p).to_dict() for p in props}
        return {'record':o,'source':refs,'identity':self.licenses[key],
                'propositions':{p:a.proposition_snapshot(p) for p in props},
                'native_propositions':{p.proposition_id:p.to_dict() for p in self.dossiers[key].propositions if p.proposition_id in props},
                'relations':{n:relations[n] for n in selected},'uncertainty':states,'historical':history,
                'origins':sorted(origins),'dossier_id':self.dossiers[key].dossier_id}

    def _validate(self):
        need(bool(self.datasets),'DATASETS_REQUIRED')
        for d in self.datasets.values():self._validate_dataset(d)
        # Existing HRGs may span several independently validated work dossiers.
        known_dossiers={};known_analyses={}
        for key,native in self.dossiers.items():
            if native.dossier_id in known_dossiers:
                need(known_dossiers[native.dossier_id].sha256()==native.sha256() and
                     fingerprint(known_analyses[native.dossier_id].to_dict())==fingerprint(self.analyses[key].to_dict()),
                     'DOSSIER_REVISION_COLLISION',native.dossier_id)
            known_dossiers[native.dossier_id]=native;known_analyses[native.dossier_id]=self.analyses[key]
        from .historical_explanation import records
        for key,d in self.datasets.items():
            r=self.registries[key]
            if d['historical_graph'] is not None:
                self.graphs[key]=HistoricalRelationGraph.from_dict(d['historical_graph'],known_dossiers,known_analyses,r)
            explanatory=records(r.argument)
            if explanatory:
                need(key in self.graphs,'EXPLANATION_GRAPH_REQUIRED',key)
                bound={b['consumer_id'] for b in self.graphs[key].to_dict().get('explanation_bindings',[])}
                need(bound==set(explanatory),'EXPLANATION_BINDINGS',key)
        for key,d in self.datasets.items():self._validate_metadata(key,d)
        inventories={k:self._validate_corpus(c) for k,c in self.corpora.items()}
        for m in self.maps.values():
            shape(m,'id corpus_id dimensions observations claims','map')
            need(m['corpus_id'] in self.corpora,'MAP_CORPUS',m['id'])
            dimensions=table(m['dimensions'],'dimensions')
            for dim in dimensions.values():
                shape(dim,'id definition coverage rationale','dimension')
                need(dim['id'] in DIMENSIONS and dim['coverage'] in {'INSPECTED','NOT_INSPECTED','UNAVAILABLE'},'DIMENSION',dim['id'])
                text(dim['definition'],'dimension definition');text(dim['rationale'],'dimension rationale')
            c=self.corpora[m['corpus_id']];observations=table(m['observations'],'observations')
            self.coverage[m['id']]=dimensions;self.observations[m['id']]={}
            for k,o in observations.items():
                need(o['dimension'] in dimensions and dimensions[o['dimension']]['coverage']=='INSPECTED','DIMENSION_NOT_INSPECTED',k)
                self.observations[m['id']][k]=self.observation(o,c,inventories[c['id']])
            claims=table(m['claims'],'claims');self.claims[m['id']]=claims
            for claim in claims.values():self.validate_map_claim(m,claim)
        for comp in self.comparisons.values():self.validate_comparison(comp)

    def basis(self,m,claim):
        chosen=ids(claim['observation_ids'],'observation basis',True)
        need(set(chosen)<=self.observations[m['id']].keys(),'OBSERVATION_BASIS',claim['id'])
        return [self.observations[m['id']][key] for key in chosen]

    def map_snapshot(self,map_id,claim_id):
        m=self.maps[map_id];claim=self.claims[map_id][claim_id]
        return fingerprint({'corpus':self.corpora[m['corpus_id']],
            'dimensions':m['dimensions'],'basis':self.basis(m,claim),
            'claim':{k:v for k,v in claim.items() if k not in {'snapshot','status'}}})

    def _state(self,claim,current):
        need(claim['status'] in {'CURRENT','REVALIDATION_REQUIRED'},'CLAIM_STATUS',claim['id'])
        need(isinstance(claim['snapshot'],str) and re.fullmatch('[a-f0-9]{64}',claim['snapshot']),'SNAPSHOT',claim['id'])
        need(claim['confidence'] in {'secure','probable','possible','unresolved'},'QUALITATIVE_CONFIDENCE',claim['id'])
        ids(claim['limitations'],'claim limitations')
        text(claim['text'],'claim text')
        need(not re.search(r'earliest[- ]known|first occurrence|historically rare|apparently novel|novelty ledger|originality|unprecedented|historically unique',claim['text'],re.I),'STAGE10_BOUNDARY',claim['id'])
        if claim['status']=='CURRENT':need(claim['snapshot']==current,'MACRO_REVALIDATION_REQUIRED',claim['id'])

    def validate_map_claim(self,m,claim):
        shape(claim,'id dimension observation_ids scope label significance text confidence limitations status snapshot','map claim')
        need(claim['dimension'] in self.coverage[m['id']],'CLAIM_DIMENSION',claim['id'])
        basis=self.basis(m,claim);c=self.corpora[m['corpus_id']]
        need(all(o['record']['dimension']==claim['dimension'] for o in basis),'CLAIM_DIMENSION_BASIS',claim['id'])
        need(claim['scope'] in {'WHOLE_WORK','BOUNDED_CORPUS'},'CLAIM_SCOPE',claim['id'])
        if claim['status']=='CURRENT':
            if claim['scope']=='WHOLE_WORK':
                need(c['state']=='SUFFICIENT_WHOLE_WORK','PARTIAL_AS_WHOLE',claim['id'])
                need(len({o['record']['portion_id'] for o in basis})>1 and self.unique_occurrences(basis)>1,'ONE_PASSAGE_WHOLE_WORK',claim['id'])
            if c['state']=='UNRESOLVED_BOUNDARY':
                need(claim['confidence'] in {'possible','unresolved'} and claim['limitations'],'UNRESOLVED_CORPUS',claim['id'])
        significance=table(claim['significance'],'significance')
        for s in significance.values():
            shape(s,'id state observation_ids rationale','significance')
            need(s['id'] in SIGNIFICANCE and s['state'] in {'SUPPORTED','QUALIFIED','UNRESOLVED'},'SIGNIFICANCE',s['id'])
            text(s['rationale'],'significance rationale')
            found=ids(s['observation_ids'],'significance basis',True)
            need(set(found)<=set(claim['observation_ids']),'SIGNIFICANCE_BASIS',s['id'])
            supporting=[self.observations[m['id']][x] for x in found]
            if s['state']=='SUPPORTED':
                allowed={'DOCTRINAL_CENTRALITY':{'STRUCTURAL_DEPENDENCY','INTEGRATION'},
                    'FORMULATION_FREQUENCY':{'OCCURRENCE','BOUNDED_DISTRIBUTION'},
                    'CONFIGURATION_FREQUENCY':{'STRUCTURAL_DEPENDENCY','INTEGRATION','TRANSITION','PERIPHERAL_FUNCTION'},
                    'STRUCTURAL_ROLE':{'STRUCTURAL_DEPENDENCY','INTEGRATION','TRANSITION','PERIPHERAL_FUNCTION'},
                    'LOCAL_POLEMICAL_INTENSITY':{'LOCAL_INTENSITY'},'CROSS_LOCUS_INTEGRATION':{'INTEGRATION'}}[s['id']]
                need(all(o['record']['role'] in allowed for o in supporting),'SIGNIFICANCE_ROLE',s['id'])
                if s['id'] in {'DOCTRINAL_CENTRALITY','CROSS_LOCUS_INTEGRATION'}:
                    need(len({o['record']['portion_id'] for o in supporting})>1 and self.unique_occurrences(supporting)>1,'LOCAL_AS_CENTRAL',claim['id'])
        if claim['status']=='CURRENT' and any(s['state']!='SUPPORTED' for s in significance.values()):
            need(claim['confidence'] in {'possible','unresolved'} and claim['limitations'],'CONFLICTING_DIMENSIONS',claim['id'])
        label=claim['label'];need(label is None or label in LABELS,'LABEL',label)
        if label is not None and claim['status']=='CURRENT':
            roles={o['record']['role'] for o in basis}
            required={'central':{'STRUCTURAL_DEPENDENCY'},'integrative':{'INTEGRATION'},
                'transitional':{'TRANSITION'},'peripheral':{'PERIPHERAL_FUNCTION'},
                'representative':{'BOUNDED_DISTRIBUTION'},'exceptional':{'BOUNDED_CONTRAST'}}[label]
            need(bool(roles&required),'LABEL_SUPPORT',label)
            if label in {'central','integrative','representative'}:
                need(len({o['record']['portion_id'] for o in basis})>1 and self.unique_occurrences(basis)>1,'LOCAL_LABEL_INFLATION',label)
            if label=='exceptional':
                comparators=[o for o in self.observations[m['id']].values() if o['record']['dimension']==claim['dimension']]
                need(len({o['record']['value'] for o in comparators})>1 and self.unique_occurrences(comparators)>1,'EXCEPTIONAL_CONTRAST',claim['id'])
            if label=='central':need(significance.get('DOCTRINAL_CENTRALITY',{}).get('state')=='SUPPORTED' and significance.get('STRUCTURAL_ROLE',{}).get('state')=='SUPPORTED','CENTRAL_DIMENSIONS',claim['id'])
            if any(s['state']!='SUPPORTED' for s in significance.values()):
                need(claim['confidence'] in {'possible','unresolved'} and claim['limitations'],'CONFLICTING_DIMENSIONS',claim['id'])
        uncertain=False
        for o in basis:
            uncertain |= any(h.get('confidence') in {'possible','unresolved'} or h.get('claim_state') in {'CANDIDATE','UNRESOLVED','REJECTED'} for h in o['historical'])
            a=self.registries[o['record']['dataset_id']].argument
            for p in o['record']['proposition_ids']:
                uncertain |= a.props[p]['status']!='ESTABLISHED' or a.props[p]['owner']=='UNKNOWN'
                scopes=a.r.dependency_scope(a.props[p]['representation_id'])
                uncertain |= any(a.r.spans(n)[s]['state']!='VISIBLE' for n,ss in scopes.items() for s in ss)
                uncertain |= o['uncertainty'][p]['state']!='UNAFFECTED'
                uncertain |= any(risk['status']!='REVIEWED' and set(risk['span_ids'])&scopes.get(risk['representation_id'],set()) for risk in a.r.risks.values())
                if claim['dimension'] in {'DOCTRINE','THEOLOGICAL_STRUCTURE','DOCTRINAL_PLACEMENT'}:
                    selected=set(o['record']['proposition_ids'])
                    authors={n for n in selected if a.props[n]['owner']=='AUTHOR' and a.props[n]['stance'] in {'ASSERTS','QUALIFIES'}}
                    need(bool(authors),'AUTHOR_DOCTRINE_BASIS',claim['id'])
                    if a.props[p]['owner']!='AUTHOR':
                        native=o['native_propositions'][p]
                        need(a.props[p]['owner'] in {'SCRIPTURE','QUOTED_AUTHORITY'} and
                             a.props[p]['role'] in {'SCRIPTURE_LEMMA','QUOTATION'} and
                             'AUTHORITY' in native['argument_functions'] and
                             any(e['source_proposition_id']==p and e['target_proposition_id'] in authors and
                                 e['relation_type']=='SUPPORTS' for e in o['relations'].values()),'NONAUTHOR_DOCTRINE',p)
        if uncertain and claim['status']=='CURRENT':need(claim['confidence'] in {'possible','unresolved'} and claim['limitations'],'UPSTREAM_UNCERTAINTY',claim['id'])
        self._state(claim,self.map_snapshot(m['id'],claim['id']))

    @staticmethod
    def unique_occurrences(basis):
        # A passage remains one passage through OCR, translation and extraction.
        groups=[]
        for o in basis:
            origins=set(tuple(x) for x in o['origins']);portion=o['record']['portion_id']
            matches=[g for g in groups if g['portion']==portion or g['origins']&origins]
            if matches:
                first=matches[0];first['origins']|=origins
                for other in matches[1:]:first['origins']|=other['origins'];groups.remove(other)
            else:groups.append({'portion':portion,'origins':origins})
        return len(groups)

    def comparison_sides(self,c):
        sides=rows(c['sides'],'comparison sides');need(len(sides)>=2,'COMPARISON_SIDES',c['id'])
        seen=set();out=[]
        for s in sides:
            shape(s,'map_id claim_ids','side')
            mid=s['map_id'];need(mid in self.maps and mid not in seen,'SIDE_MAP',mid);seen.add(mid)
            chosen=ids(s['claim_ids'],'side claims',True)
            need(set(chosen)<=self.claims[mid].keys(),'SIDE_CLAIMS',mid)
            for cid in chosen:
                claim=self.claims[mid][cid]
                need(claim['status']=='CURRENT' and claim['snapshot']==self.map_snapshot(mid,cid),'SIDE_REVALIDATION',cid)
            map_=self.maps[mid];corp=self.corpora[map_['corpus_id']]
            dataset_ids=sorted({o['record']['dataset_id'] for cid in chosen for o in self.basis(map_,self.claims[mid][cid])})
            metadata={key:self.datasets[key]['metadata'] for key in dataset_ids}
            out.append({'side':s,'corpus':corp,'metadata':metadata,'licenses':{key:self.licenses[key] for key in dataset_ids},
                'claim_snapshots':{cid:self.map_snapshot(mid,cid) for cid in chosen},'dimensions':self.coverage[mid]})
        return out

    def comparison_snapshot(self,c):
        return fingerprint({'record':{k:v for k,v in c.items() if k not in {'snapshot','status'}},'sides':self.comparison_sides(c)})

    def asymmetries(self,c):
        sides=self.comparison_sides(c)
        return [{'map_id':s['side']['map_id'],'corpus_size':len(s['corpus']['inventory']),
            'completeness':s['corpus']['state'],'unavailable':[p['id'] for p in s['corpus']['inventory'] if p['status']!='INSPECTED'],
            'metadata':s['metadata'],'dimension_coverage':s['dimensions']} for s in sides]

    def validate_comparison(self,c):
        shape(c,'id kind dimension definition sides finding attribution confounds alternatives asymmetry_assessment text confidence limitations status snapshot','comparison')
        need(c['kind'] in {'DEVELOPMENTAL','COMPARATIVE'},'COMPARISON_KIND',c['id'])
        need(c['dimension'] in DIMENSIONS,'COMPARISON_DIMENSION',c['id']);text(c['definition'],'comparison definition')
        need(c['finding'] in {'STRUCTURAL_SIMILARITY','STRUCTURAL_DIFFERENCE','OBSERVED_CHANGE','UNRESOLVED'},'COMPARISON_FINDING',c['id'])
        sides=self.comparison_sides(c)
        for side in sides:
            dim=side['dimensions'].get(c['dimension'])
            need(dim is not None and dim['coverage']=='INSPECTED' and dim['definition']==c['definition'],'NONCOMPARABLE_DIMENSION',side['side']['map_id'])
            need(all(self.claims[side['side']['map_id']][cid]['dimension']==c['dimension'] for cid in side['side']['claim_ids']),'SIDE_DIMENSION',c['id'])
        text(c['asymmetry_assessment'],'asymmetry assessment')
        ids(c['alternatives'],'alternatives')
        if c['kind']=='COMPARATIVE':
            need(c['attribution']=='STRUCTURAL_COMPARISON_ONLY' and c['finding'] in {'STRUCTURAL_SIMILARITY','STRUCTURAL_DIFFERENCE','UNRESOLVED'},'COMPARISON_NOT_GENEALOGY',c['id'])
            need(c['confounds']==[],'COMPARATIVE_FIELDS',c['id'])
            signatures=[fingerprint({'size':len(side['corpus']['inventory']),'state':side['corpus']['state'],
                'dimensions':{k:d['coverage'] for k,d in side['dimensions'].items()},
                'contexts':sorted((m['genre'],m['period'],m['source_form'],m['availability']) for m in side['metadata'].values())}) for side in sides]
            if len(set(signatures))>1:
                need(not re.search(r'equivalent corpora|equal corpora|same completeness|same evidence coverage',c['text']+' '+c['asymmetry_assessment'],re.I),'ASYMMETRY_CONCEALMENT',c['id'])
            need(not re.search(r'borrowed from|depends on|derived from|direct dependence|genealogy|common source|reception of',c['text'],re.I),'STRUCTURE_AS_GENEALOGY',c['id'])
        else:
            need(c['dimension'] in DEVELOPMENT_DIMENSIONS,'DEVELOPMENT_DIMENSION',c['dimension'])
            need(c['attribution'] in {'AUTHORIAL_DEVELOPMENT','OBSERVED_DIFFERENCE_ONLY','UNRESOLVED'},'DEVELOPMENT_ATTRIBUTION',c['id'])
            need(c['finding'] in {'OBSERVED_CHANGE','UNRESOLVED'},'DEVELOPMENT_FINDING',c['id'])
            all_meta=[(key,m) for s in sides for key,m in s['metadata'].items()]
            need(len({m['author_id'] for key,m in all_meta})==1,'SAME_AUTHOR_REQUIRED',c['id'])
            confounds=table(c['confounds'],'confounds');need(set(confounds)==CONFOUNDS,'CONFOUNDS_REQUIRED',c['id'])
            for f in confounds.values():
                shape(f,'id state evidence rationale','confound')
                need(f['state'] in {'CONTROLLED','LIVE_ALTERNATIVE','UNRESOLVED'},'CONFOUND_STATE',f['id'])
                text(f['rationale'],'confound rationale');self.source_refs(f['evidence'])
            if c['attribution']=='AUTHORIAL_DEVELOPMENT' and c['status']=='CURRENT':
                need(all(m['date']['state']=='SECURE' and m['date']['subject'] in {'WORK_COMPOSITION','WORK_PUBLICATION','EDITION_PUBLICATION'} for key,m in all_meta),'SECURE_DATING_REQUIRED',c['id'])
                ranges=[(min(m['date']['earliest'] for m in s['metadata'].values()),max(m['date']['latest'] for m in s['metadata'].values())) for s in sides]
                need(all(a[1]<b[0] for a,b in zip(ranges,ranges[1:])),'SECURE_SEQUENCE_REQUIRED',c['id'])
                need(all(f['state']=='CONTROLLED' for f in confounds.values()),'CONFOUND_NOT_CONTROLLED',c['id'])
                # Edition/translation/editor differences need positive original-author evidence.
                if len({s['corpus']['work_id'] for s in sides})==1:
                    editions=[license['scope']['edition_id'] for side in sides for license in side['licenses'].values()]
                    need(all(editions) and len(set(editions))>=len(sides),'EDITION_IDENTITY_REQUIRED',c['id'])
                if len({s['corpus']['work_id'] for s in sides})==1 or any(m['source_form'] in {'HISTORICAL_TRANSLATION','MODERN_TRANSLATION'} for key,m in all_meta):
                    require_ids=['EDITION'] if len({s['corpus']['work_id'] for s in sides})==1 else []
                    if any(m['source_form'] in {'HISTORICAL_TRANSLATION','MODERN_TRANSLATION'} for key,m in all_meta):require_ids+=['TRANSLATOR','EDITOR']
                    for f in require_ids:
                        for ref in confounds[f]['evidence']:
                            r=self.registries[ref['dataset_id']];r.permit(ref['ref']['representation_id'],'EXACT_ORIGINAL_WORDING',ref['ref']['span_ids'])
            if any(f['state']!='CONTROLLED' for f in confounds.values()):
                need(c['attribution']!='AUTHORIAL_DEVELOPMENT' and c['alternatives'] and c['confidence'] in {'possible','unresolved'} and c['limitations'],'COMPETING_EXPLANATIONS',c['id'])
        if any(self.claims[s['side']['map_id']][cid]['confidence'] in {'possible','unresolved'} for s in sides for cid in s['side']['claim_ids']):
            need(c['confidence'] in {'possible','unresolved'} and c['limitations'],'COMPARISON_UNCERTAINTY',c['id'])
        self._state(c,self.comparison_snapshot(c))

    def render_map_claim(self,mid,cid):
        m=self.maps[mid];c=self.claims[mid][cid];self.validate_map_claim(m,c)
        need(c['status']=='CURRENT','NOT_CURRENT',cid)
        corpus=self.corpora[m['corpus_id']];basis=self.basis(m,c)
        lines=[f"{c['dimension'].replace('_',' ').capitalize()} ({c['confidence']}; {c['scope'].replace('_',' ').lower()}): {c['text']}",
            f"Corpus boundary.\n\n{corpus['boundary']} [{corpus['state'].replace('_',' ').lower()}].",
            f"Inspected passage occurrences: {self.unique_occurrences(basis)}."]
        missing=[p['id']+' ('+p['status'].lower()+')' for p in corpus['inventory'] if p['status']!='INSPECTED']
        if missing:lines.append('Corpus gaps: '+', '.join(missing)+'.')
        if c['label']:lines.append('Structural classification: '+c['label']+'.')
        lines += [s['id'].replace('_',' ').capitalize()+': '+s['state'].lower()+'. '+s['rationale'] for s in c['significance']]
        for index,o in enumerate(basis,1):
            p=o['record'];lines.append('Evidence portion '+str(index)+'. '+p['rationale'])
            for h in o['historical']:
                if h.get('kind')=='EXPLANATION':
                    lines.append('Historical explanation: '+(h['classification'] or 'pressure field').replace('_',' ').lower()+' ('+h['confidence']+').')
                else:lines.append('Historical relation: '+h['relation_type'].replace('_',' ').lower()+' ('+h['confidence']+').')
        lines+=['Limit.\n\n'+x for x in corpus['limitations']+c['limitations']]
        return '\n\n'.join(lines)

    def render_comparison(self,cid):
        c=self.comparisons[cid];self.validate_comparison(c);need(c['status']=='CURRENT','NOT_CURRENT',cid)
        lines=[c['kind'].capitalize()+' '+c['dimension'].replace('_',' ').lower()+': '+c['finding'].replace('_',' ').lower()+' ('+c['confidence']+').',
            'Attribution: '+c['attribution'].replace('_',' ').lower()+'.',c['text'],'Evidence asymmetry.\n\n'+c['asymmetry_assessment']]
        for index,s in enumerate(self.asymmetries(c),1):
            lines.append('Corpus '+str(index)+': '+str(s['corpus_size'])+' portions; '+s['completeness'].replace('_',' ').lower()+'.')
            lines+=['Corpus gap: '+x for x in s['unavailable']]
            lines += ['Dimension '+key.lower()+': '+dim['coverage'].replace('_',' ').lower()+'.' for key,dim in s['dimension_coverage'].items()]
            for key,m in s['metadata'].items():lines.append('Evidence context: '+m['genre']+'; '+m['period']+'; '+m['source_form'].replace('_',' ').lower()+'; '+m['availability']+'.')
        lines += [f['id'].replace('_',' ').capitalize()+': '+f['state'].replace('_',' ').lower()+'. '+f['rationale'] for f in c['confounds']]
        lines += ['Competing explanation: '+x for x in c['alternatives']]
        lines += ['Limit.\n\n'+x for x in c['limitations']]
        return '\n\n'.join(lines)

    def current_outputs(self):
        outputs={}
        for mid,claims in self.claims.items():
            for cid,c in claims.items():
                if c['status']=='CURRENT':outputs['map:'+mid+':'+cid]=self.render_map_claim(mid,cid)
        for cid,c in self.comparisons.items():
            if c['status']=='CURRENT':outputs['comparison:'+cid]=self.render_comparison(cid)
        return outputs


def revalidate(value):
    """Explicit reviewed revalidation. Never called automatically by completion."""
    out=copy.deepcopy(value)
    for m in out['maps']:
        for c in m['claims']:c['status']='REVALIDATION_REQUIRED'
    for c in out['comparisons']:c['status']='REVALIDATION_REQUIRED'
    # Review and license each map before allowing its use as comparison evidence.
    for m in out['maps']:
        for c in m['claims']:
            obj=Cartography({**out,'comparisons':[]})
            c['snapshot']=obj.map_snapshot(m['id'],c['id']);c['status']='CURRENT'
            Cartography({**out,'comparisons':[]})
    obj=Cartography(out)
    for c in out['comparisons']:
        c['snapshot']=obj.comparison_snapshot(c);c['status']='CURRENT'
    Cartography(out)
    return out


def validate_completion(directory,checkpoint,rendered_text,registry):
    path=directory/'hti-cartography.json'
    claims=[c for c in checkpoint.get('claims',[]) if c.get('claim_type')=='cartography']
    from evidence_audit import selected_domain_ids, selected_domain_claims
    selected=selected_domain_ids(checkpoint,"cartography");claims=selected_domain_claims(checkpoint,"cartography")
    if not selected:return
    need(path.is_file(),'INPUT_REQUIRED')
    import task_state
    pub=task_state.require_ready(directory);draft=task_state.current_draft(directory,pub)
    need(path.name in draft['inputs'],'CURRENT_STAGING_REQUIRED')
    obj=Cartography(json.loads(path.read_text()))
    # Bind the task's actual current source substrate, not a lookalike embedded copy.
    datasets=[d for d in obj.datasets.values() if d['integrity']==registry.raw]
    need(bool(datasets),'CURRENT_TASK_SUBSTRATE_REQUIRED')
    need(any(obj.registries[d['id']].work_id==checkpoint.get('work_id') for d in datasets),'TASK_WORK')
    current_ids={d['id'] for d in datasets}
    current_maps={mid for mid,m in obj.maps.items() if obj.corpora[m['corpus_id']]['work_id']==checkpoint.get('work_id') and
                  any(o['record']['dataset_id'] in current_ids for o in obj.observations[mid].values()) and
                  any(c['status']=='CURRENT' for c in obj.claims[mid].values())}
    need(bool(current_maps),'CURRENT_MAP_REQUIRED')
    licensed_maps=set(current_maps)
    for c in obj.comparisons.values():
        if c['status']!='CURRENT' or 'comparison:'+c['id'] not in selected:continue
        sides={s['map_id'] for s in c['sides']}
        need(bool(sides&current_maps),'COMPARISON_TASK_ANCHOR',c['id'])
        licensed_maps|=sides
    need(all(mid in licensed_maps for mid,values in obj.claims.items() if any('map:'+mid+':'+cid in selected for cid in values)),
         'UNREQUESTED_WORK_MAP')
    outputs=obj.current_outputs()
    need({c.get('cartography_id') for c in claims}==selected and selected<=set(outputs),'OUTPUT_BINDINGS')
    for c in claims:
        output=outputs[c['cartography_id']]
        need(c.get('cartography_sha256')==hashlib.sha256(output.encode()).hexdigest(),'OUTPUT_HASH',c.get('claim_id'))
        need(output in rendered_text,'OUTPUT_NOT_VISIBLE',c.get('claim_id'))
