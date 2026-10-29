"""Dimension-bound novelty judgments over auditable, source-bound search records.

No search failure establishes historical absence, invention or dependence.
"""
from __future__ import annotations
import copy, hashlib, json, re
from datetime import date
from .cartography import Cartography, shape, text, rows, ids, table, fingerprint
from .model import ValidationError

SCHEMA = 'hti-novelty-1'
DIMENSIONS = frozenset({'PROPOSITION','WORDING','DISTINCTION','EXEGETICAL_ROUTE',
    'SYNTHESIS','ARGUMENTATIVE_SEQUENCE','COMBINATION','FUNCTION'})
LADDER = ('COMMON','UNCOMMON','RARE','APPARENTLY_DISTINCTIVE_WITHIN_SEARCHED_EVIDENCE',
    'APPARENTLY_NOVEL_WITHIN_SEARCHED_EVIDENCE','POSSIBLE_EARLIEST_KNOWN_OCCURRENCE')
CLASSES = frozenset(LADDER) | {'UNRESOLVED','NO_PRECEDENT_FOUND_WITHIN_SEARCHED_EVIDENCE'}
REJECTIONS = frozenset({'DIFFERENT_PROPOSITION','DIFFERENT_FUNCTION','LEXICAL_WITHOUT_CONCEPT',
    'CONCEPT_WITHOUT_STRUCTURE','WRONG_GENRE','DERIVATIVE_WITNESS','LATER_ANALOGY','TRANSLATION_ARTIFACT'})

def need(ok, code, detail=''):
    if not ok: raise ValidationError('NOVELTY_'+code+': '+str(detail))

def list_text(value, label, required=False): return ids(value, label, required)

def iso(value):
    text(value,'search date')
    try: date.fromisoformat(value)
    except ValueError: need(False,'SEARCH_DATE',value)


class Novelty:
    def __init__(self,value):
        self.anchor_mode = value.get("schema_version") == "hti-novelty-anchor-1"
        if self.anchor_mode:
            self._anchor_document(value)
            return
        shape(value,'schema_version evidence objects universes searches candidates claims','novelty document')
        need(value['schema_version']==SCHEMA,'SCHEMA')
        self.raw=copy.deepcopy(value)
        self.evidence=Cartography(self.raw['evidence'])
        self.objects=table(self.raw['objects'],'objects')
        self.universes=table(self.raw['universes'],'universes')
        self.searches=table(self.raw['searches'],'searches')
        self.candidates=table(self.raw['candidates'],'candidates')
        self.claims=table(self.raw['claims'],'claims')
        self.bases={};self.units={};self.executions={};self.findings={}
        for o in self.objects.values():self.bases[o['id']]=self.component(o)
        for u in self.universes.values():self.universe(u)
        for s in self.searches.values():self.search(s)
        for c in self.candidates.values():self.candidate(c)
        for candidate in self.candidates.values():
            for sid in candidate['found_in']:
                search=self.searches[sid]
                if search['mode']=='CONCEPTUAL_REVIEW':
                    need(any(v['unit_id']==candidate['unit_id'] and candidate['id'] in v['candidate_ids'] for v in search['reviews']),'CANDIDATE_INSPECTION_LEDGER',candidate['id'])
        # Every recorded hit and nominated candidate remains in the ledger.
        for s in self.searches.values():
            covered={h for c in self.candidates.values() if s['id'] in c['found_in'] for h in c['hit_ids']}
            need(covered=={h['id'] for h in s['results']},'CANDIDATE_SUPPRESSION',s['id'])
            for review in s['reviews']:
                need(set(review['candidate_ids'])<={c['id'] for c in self.candidates.values() if s['id'] in c['found_in']},'CANDIDATE_SUPPRESSION',s['id'])
        for c in self.claims.values():self.claim(c)

    def _anchor_document(self, value):
        # Discovery is task state, never searched-unit coverage or work identity.
        shape(value, 'schema_version investigation', 'anchor investigation document')
        i = value['investigation']
        shape(i, 'id task_directory work_id anchor_id anchor_snapshot dimension feature universe discovery_ids observations outcome reason snapshot', 'anchor investigation')
        need(i['dimension'] in DIMENSIONS and i['outcome'] == 'UNRESOLVED', 'ANCHOR_LICENSE_CEILING')
        for k in ('id', 'task_directory', 'work_id', 'anchor_id', 'feature', 'reason'):text(i[k], k)
        shape(i['universe'], 'boundary chronology languages genres lexical_forms conceptual_formulations inaccessible_domains discriminating_sources stopping_conditions', 'intended universe')
        text(i['universe']['boundary'], 'comparison boundary');text(i['universe']['chronology'], 'intended chronology')
        for k in ('languages', 'genres', 'lexical_forms', 'conceptual_formulations', 'inaccessible_domains', 'discriminating_sources', 'stopping_conditions'):list_text(i['universe'][k], k)
        need(bool(i['universe']['languages']) and bool(i['universe']['genres']) and bool(i['universe']['stopping_conditions']), 'ANCHOR_UNIVERSE_REQUIRED')
        list_text(i['discovery_ids'], 'discovery ids');rows(i['observations'], 'source observations')
        for observation in i['observations']:
            shape(observation, 'assertion_id assertion_snapshot', 'source observation')
        need(i['snapshot'] == fingerprint({k:v for k,v in i.items() if k != 'snapshot'}), 'ANCHOR_REVALIDATION_REQUIRED')
        self.raw = copy.deepcopy(value);self.investigation = i
        self.objects = {};self.claims = {};self.evidence = None

    def validate_anchor(self, checkpoint, registry):
        from evidence_audit import publication_table
        c = checkpoint['publication_contract'];i = self.investigation
        anchors = publication_table(c['anchors'], 'anchors');discoveries = publication_table(c['discoveries'], 'discoveries');assertions = publication_table(c['assertions'], 'assertions')
        need(i['work_id'] == registry.work_id == checkpoint['work_id'] and i['task_directory'] == c['task_directory'], 'ANCHOR_TASK_SCOPE')
        need(i['anchor_id'] in anchors and i['anchor_snapshot'] == fingerprint(anchors[i['anchor_id']]), 'ANCHOR_CURRENT')
        need(set(i['discovery_ids']) <= set(discoveries) and all(discoveries[k]['anchor_id'] == i['anchor_id'] for k in i['discovery_ids']), 'ANCHOR_DISCOVERY_BINDING')
        for observation in i['observations']:
            aid=observation['assertion_id']
            need(aid in assertions and observation['assertion_snapshot'] == fingerprint(assertions[aid]), 'ANCHOR_OBSERVATION_CURRENT')
            need(assertions[aid]['purpose'] in {'VISIBLE_CONTENT','PROVISIONAL_TEXT','REPRESENTED_ARGUMENT','TRANSCRIBED_WORDING'}, 'ANCHOR_OBSERVATION_SCOPE')
            need(not any(k in assertions[aid]['facets'] for k in ('author_id','work_identity','edition_identity','earliest_known_occurrence','originality','historical_dependence','whole_work')), 'ANCHOR_STRONG_FACET')

    def scope_work_ids(self):
        if self.anchor_mode:return {self.investigation['work_id']}
        return {self.evidence.registries[self.objects[c['object_id']]['dataset_id']].work_id for c in self.claims.values()}

    def component(self,o):
        shape(o,'id dataset_id proposition_ids relation_ids source_refs dimension feature claim_level wording_scope cartography_refs','component')
        need(o['dimension'] in DIMENSIONS,'DIMENSION',o['id']);text(o['feature'],'feature')
        need(o['claim_level'] in {'AUTHORIAL_ARGUMENT','REPORTED_COMPONENT','REPRESENTATION_WORDING'},'CLAIM_LEVEL')
        need(o['wording_scope'] in {'ORIGINAL','REPRESENTED'},'WORDING_SCOPE')
        e=self.evidence;key=o['dataset_id'];need(key in e.datasets,'DATASET')
        r=e.registries[key];a=r.argument;props=list_text(o['proposition_ids'],'propositions',True)
        need(set(props)<=a.props.keys(),'PROPOSITION')
        refs=e.source_refs(o['source_refs']);need(all(x['dataset_id']==key for x in refs),'OBJECT_WORK')
        for p in props:
            a.permit_proposition(p,author_position=o['claim_level']=='AUTHORIAL_ARGUMENT')
            scope=r.dependency_scope(a.props[p]['representation_id'])
            need(any(set(x['span_ids']) & scope.get(x['representation_id'],set()) for x in refs),'SOURCE_ANCESTRY',p)
        native={x.relation_id:x.to_dict() for x in e.dossiers[key].relations}
        rel=list_text(o['relation_ids'],'relations');need(set(rel)<=native.keys(),'RELATION')
        for n in rel:need({native[n]['source_proposition_id'],native[n]['target_proposition_id']}<=set(props),'RELATION_ENDPOINTS')
        if o['dimension'] in {'SYNTHESIS','ARGUMENTATIVE_SEQUENCE','COMBINATION','EXEGETICAL_ROUTE','FUNCTION'}:
            need(bool(rel),'STRUCTURE_REQUIRED')
        if o['dimension']=='WORDING' and o['wording_scope']=='ORIGINAL':
            for x in refs:r.permit(x['representation_id'],'EXACT_ORIGINAL_WORDING',x['span_ids'])
        if o['dimension']=='WORDING':
            need(any(o['feature'] in r.spans(x['representation_id'])[s]['text'] for x in refs for s in x['span_ids']),'WORDING_NOT_PRESENT')
        ancestry=set()
        for x in refs:
            for n,spans in r.dependency_scope(x['representation_id'],x['span_ids']).items():
                if not r.nodes[n]['parents']:ancestry.update((root,s) for root in r.roots(n) for s in spans)
        cart=[]
        for ref in rows(o['cartography_refs'],'cartographic object refs'):
            shape(ref,'map_id claim_id','cartographic object ref');mid=ref['map_id'];cid=ref['claim_id']
            need(mid in e.claims and cid in e.claims[mid],'CARTOGRAPHIC_OBJECT')
            claim=e.claims[mid][cid];need(claim['status']=='CURRENT','STALE_CARTOGRAPHIC_OBJECT')
            basis=e.basis(e.maps[mid],claim)
            need(any(b['record']['dataset_id']==key and set(props)&set(b['record']['proposition_ids']) for b in basis),'CARTOGRAPHIC_OBJECT_BINDING')
            cart.append(e.map_snapshot(mid,cid))
        return {'record':o,'sources':refs,'ownership':[a.props[p] for p in props],
            'native_propositions':[x.to_dict() for x in e.dossiers[key].propositions if x.proposition_id in props],
            'relations':[native[n] for n in rel],'uncertainty':{p:e.analyses[key].analyze(p).to_dict() for p in props},
            'identity':e.licenses[key],'metadata':e.datasets[key]['metadata'],'origins':sorted(ancestry),'cartography':cart}

    def universe(self,u):
        shape(u,'id object_id dimension boundary period languages genres collections lexical_terms conceptual_formulations functional_dimensions excluded_domains known_gaps digitization_gaps unresolved_domains domains','universe')
        need(u['object_id'] in self.objects and u['dimension']==self.objects[u['object_id']]['dimension'],'UNIVERSE_DIMENSION')
        text(u['boundary'],'bounded universe')
        shape(u['period'],'earliest latest rationale','period');p=u['period']
        need(type(p['earliest']) is int and type(p['latest']) is int and p['earliest']<=p['latest'],'PERIOD');text(p['rationale'],'period rationale')
        for name in ['languages','genres','collections']:list_text(u[name],name,True)
        for name in ['lexical_terms','conceptual_formulations','functional_dimensions','excluded_domains','known_gaps','digitization_gaps','unresolved_domains']:list_text(u[name],name)
        need(bool(u['lexical_terms'] or u['conceptual_formulations']),'SEARCH_SPECIFICATION')
        if u['dimension']!='WORDING':need(bool(u['conceptual_formulations']),'CONCEPTUAL_SPECIFICATION')
        self.units[u['id']]={}
        for d in table(u['domains'],'domains').values():
            shape(d,'id collection state units limitations','domain');need(d['collection'] in u['collections'],'COLLECTION')
            need(d['state'] in {'AVAILABLE','INACCESSIBLE','UNINDEXED','UNRESOLVED'},'DOMAIN_STATE');list_text(d['limitations'],'domain limitations')
            if d['state']!='AVAILABLE':need(not d['units'] and bool(d['limitations']),'INACCESSIBLE_AS_SEARCHED')
            for unit in rows(d['units'],'units'):
                shape(unit,'id dataset_id source_refs language genre eligibility rationale','search unit');text(unit['rationale'],'unit rationale')
                need(unit['id'] not in self.units[u['id']],'DUPLICATE_UNIT')
                key=unit['dataset_id'];need(key in self.evidence.datasets,'UNIT_DATASET')
                refs=self.evidence.source_refs(unit['source_refs']);need(all(x['dataset_id']==key for x in refs),'UNIT_SOURCE_WORK')
                need(unit['eligibility'] in {'IN_SCOPE','EXCLUDED'},'UNIT_ELIGIBILITY')
                in_scope=unit['language'] in u['languages'] and unit['genre'] in u['genres']
                need(in_scope if unit['eligibility']=='IN_SCOPE' else not in_scope,'UNIT_SCOPE')
                if unit['eligibility']=='EXCLUDED':need(bool(u['excluded_domains']),'EXCLUDED_UNIT_DISCLOSURE')
                native={x['representation_id']:x for x in self.evidence.datasets[key]['source_registry']['representations']}
                need(all(native.get(x['representation_id'],{}).get('language')==unit['language'] for x in refs),'LANGUAGE_ANCESTRY')
                need(unit['genre']==self.evidence.datasets[key]['metadata']['genre'],'GENRE_ANCESTRY')
                self.units[u['id']][unit['id']]={'record':unit,'domain_id':d['id'],'sources':refs}
        need(bool(u['domains']),'DOMAINS_REQUIRED')

    def execution(self,s):
        u=self.universes[s['universe_id']];units=self.units[u['id']];selected=list_text(s['unit_ids'],'searched units',True)
        need(set(selected)<=units.keys(),'UNSEARCHED_DOMAIN')
        hits=[];origins=set();inputs=[]
        for uid in selected:
            unit=units[uid];need(unit['domain_id']==s['domain_id'],'SEARCH_DOMAIN_BINDING')
            for ref in unit['sources']:
                r=self.evidence.registries[ref['dataset_id']]
                for n,spans in r.dependency_scope(ref['representation_id'],ref['span_ids']).items():
                    if not r.nodes[n]['parents']:origins.update((root,p) for root in r.roots(n) for p in spans)
                for span in ref['span_ids']:
                    content=r.spans(ref['representation_id'])[span]['text'];inputs.append({'unit_id':uid,'source':ref,'span_id':span,'content':content})
                    found=[t for t in s['terms'] if t.casefold() in content.casefold()]
                    if found and s['mode']=='LEXICAL':hits.append({'id':uid+':'+ref['representation_id']+':'+span,'unit_id':uid,'span_id':span,'terms':found})
        return {'inputs':inputs,'origins':sorted(origins),'results':hits,'spec':{k:v for k,v in s.items() if k not in {'receipt','results'}}}

    def search(self,s):
        shape(s,'id universe_id domain_id mode terms formulations unit_ids when version reviews results receipt','search')
        need(s['universe_id'] in self.universes,'SEARCH_UNIVERSE');u=self.universes[s['universe_id']]
        need(s['domain_id'] in {d['id'] for d in u['domains'] if d['state']=='AVAILABLE'},'INACCESSIBLE_AS_SEARCHED')
        need(s['mode'] in {'LEXICAL','CONCEPTUAL_REVIEW'},'SEARCH_MODE');iso(s['when']);text(s['version'],'search version')
        list_text(s['terms'],'terms');list_text(s['formulations'],'formulations')
        need(set(s['terms'])<=set(u['lexical_terms']) and set(s['formulations'])<=set(u['conceptual_formulations']),'QUERY_UNIVERSE')
        if s['mode']=='LEXICAL':need(bool(s['terms']) and not s['reviews'],'LEXICAL_FIELDS')
        else:
            need(bool(s['formulations']),'CONCEPTUAL_REVIEW_REQUIRED')
            reviews=table([dict(v,id=v['unit_id']) for v in rows(s['reviews'],'concept reviews')],'reviews')
            need(set(reviews)==set(s['unit_ids']),'INSPECTION_COVERAGE')
            for review in s['reviews']:
                shape(review,'unit_id evidence assessment candidate_ids','concept review');text(review['assessment'],'conceptual assessment')
                self.evidence.source_refs(review['evidence']);list_text(review['candidate_ids'],'review candidates')
                need(review['evidence']==self.units[u['id']][review['unit_id']]['record']['source_refs'],'INSPECTION_SOURCE_BINDING')
        run=self.execution(s)
        need(s['results']==run['results'],'SEARCH_RECEIPT_RESULTS')
        need(s['receipt']==fingerprint(run),'SEARCH_REVALIDATION_REQUIRED',s['id'])
        self.executions[s['id']]=run

    def candidate(self,c):
        shape(c,'id universe_id dimension state lead_type locator found_in hit_ids unit_id component comparison disposition reason rationale evidence','candidate')
        need(c['universe_id'] in self.universes,'CANDIDATE_UNIVERSE');u=self.universes[c['universe_id']]
        need(c['dimension']==u['dimension'],'CANDIDATE_DIMENSION')
        need(c['state'] in {'LEAD','INSPECTED','INACCESSIBLE'},'INSPECTION_STATE')
        need(c['lead_type'] in {'METADATA','OCR','TOC_INDEX','SEARCH_HIT','CANDIDATE_LEAD','SOURCE_INSPECTION'},'LEAD_TYPE');text(c['locator'],'candidate locator')
        found=list_text(c['found_in'],'found in',True);need(set(found)<=self.searches.keys(),'CANDIDATE_SEARCH')
        need(all(self.searches[x]['universe_id']==u['id'] for x in found),'CANDIDATE_SEARCH_SCOPE')
        list_text(c['hit_ids'],'hit ids');need(set(c['hit_ids'])<={h['id'] for s in found for h in self.searches[s]['results']},'CANDIDATE_HIT')
        need(c['unit_id'] in self.units[u['id']] and any(c['unit_id'] in self.searches[s]['unit_ids'] for s in found),'CANDIDATE_UNIT')
        need(c['comparison'] in {'SAME_DIMENSION','DIFFERENT_DIMENSION','UNRESOLVED'},'COMPARISON_TYPE')
        text(c['rationale'],'candidate rationale')
        if c['state']!='INSPECTED':
            need(c['component'] is None and c['disposition']=='UNRESOLVED' and c['comparison']=='UNRESOLVED' and c['reason'] is None and c['evidence']==[],'LEAD_AS_INSPECTED')
            self.findings[c['id']]=None;return
        need(c['lead_type']=='SOURCE_INSPECTION','METADATA_AS_INSPECTION')
        basis=self.component(c['component']);need(c['component']['dimension']==u['dimension'],'CANDIDATE_DIMENSION')
        unit=self.units[u['id']][c['unit_id']]['record']
        need(c['component']['dataset_id']==unit['dataset_id'],'CANDIDATE_SOURCE_IDENTITY')
        self.evidence.source_refs(c['evidence']);need(c['evidence']==c['component']['source_refs'],'REJECTION_EVIDENCE_BINDING')
        need(set(basis['origins'])<=set(tuple(v) for s in found for v in self.executions[s]['origins']),'CANDIDATE_SEARCH_ANCESTRY')
        need(c['disposition'] in {'PRECEDENT','CONTRAST','REJECTED','UNRESOLVED'},'DISPOSITION')
        target=self.bases[u['object_id']];td=target['metadata']['date'];cd=basis['metadata']['date']
        if u['dimension']=='WORDING' and c['disposition']=='REJECTED' and c['reason'] not in {'DERIVATIVE_WITNESS','LATER_ANALOGY','TRANSLATION_ARTIFACT','WRONG_GENRE'}:
            need(c['component']['feature']!=self.objects[u['object_id']]['feature'],'WORDING_PARALLEL_CANNOT_BE_REJECTED')
        if c['disposition']=='PRECEDENT':
            need(unit['eligibility']=='IN_SCOPE','EXCLUDED_PRECEDENT')
            need(c['comparison']=='SAME_DIMENSION' and c['reason'] is None,'PRECEDENT_DIMENSION')
            need(td['state']=='SECURE' and cd['state']=='SECURE' and cd['subject'] in {'WORK_COMPOSITION','WORK_PUBLICATION','EDITION_PUBLICATION'} and cd['latest']<td['earliest'],'ANTECEDENT_CHRONOLOGY')
            need(not set(basis['origins'])&set(target['origins']),'DERIVATIVE_PRECEDENT')
            if u['dimension']=='WORDING':
                need(c['component']['wording_scope']==self.objects[u['object_id']]['wording_scope'],'WORDING_LAYER_COMPARISON')
                need(c['component']['feature']==self.objects[u['object_id']]['feature'],'WORDING_PARALLEL')
        elif c['disposition']=='CONTRAST':
            if u['dimension']=='WORDING':need(c['component']['feature']!=self.objects[u['object_id']]['feature'],'WORDING_PARALLEL_CANNOT_BE_REJECTED')
            need(c['comparison']=='DIFFERENT_DIMENSION' and c['reason'] is None,'CONTRAST_ADJUDICATION')
        elif c['disposition']=='REJECTED':
            need(c['reason'] in REJECTIONS,'REJECTION_REASON')
            if c['reason']=='LATER_ANALOGY':need(cd['state']=='SECURE' and td['state']=='SECURE' and cd['earliest']>td['latest'],'REJECTION_CHRONOLOGY')
            elif c['reason']=='DERIVATIVE_WITNESS':need(bool(set(basis['origins'])&set(target['origins'])),'REJECTION_DERIVATIVE')
            elif c['reason']=='TRANSLATION_ARTIFACT':
                need(u['dimension']=='WORDING' and self.objects[u['object_id']]['wording_scope']=='ORIGINAL' and c['component']['wording_scope']=='REPRESENTED' and basis['metadata']['source_form'] in {'MODERN_TRANSLATION','HISTORICAL_TRANSLATION'},'REJECTION_TRANSLATION')
            elif c['reason']=='WRONG_GENRE':need(unit['eligibility']=='EXCLUDED' and unit['genre'] not in u['genres'],'REJECTION_GENRE')
            else:need(c['comparison']=='DIFFERENT_DIMENSION','REJECTION_COMPARISON')
        else:need(c['reason'] is None,'DISPOSITION_REASON')
        self.findings[c['id']]=basis

    def coverage(self,uid):
        u=self.universes[uid];searches=[s for s in self.searches.values() if s['universe_id']==uid]
        reviewed={n for s in searches if s['mode']=='CONCEPTUAL_REVIEW' for n in s['unit_ids']}
        searched={n for s in searches for n in s['unit_ids']}
        roots={tuple(v) for s in searches for v in self.executions[s['id']]['origins']}
        unresolved=[c['id'] for c in self.candidates.values() if c['universe_id']==uid and c['disposition']=='UNRESOLVED']
        gaps=u['known_gaps']+u['digitization_gaps']+u['unresolved_domains']+[d['id']+': '+d['state'] for d in u['domains'] if d['state']!='AVAILABLE']
        gaps += [d['id']+': '+limit for d in u['domains'] for limit in d['limitations']]
        gaps += ['No inspected units in declared available domain: '+d['id'] for d in u['domains'] if d['state']=='AVAILABLE' and not d['units']]
        for uid_, unit in self.units[uid].items():
            if unit['record']['eligibility']=='EXCLUDED':continue
            d=self.evidence.datasets[unit['record']['dataset_id']]['metadata']['date']
            if d['state']!='SECURE' or d['earliest']<u['period']['earliest'] or d['latest']>u['period']['latest']:
                gaps.append('Chronological coverage unresolved: '+uid_)
            if u['dimension']=='WORDING' and self.objects[u['object_id']]['wording_scope']=='ORIGINAL':
                for ref in unit['sources']:
                    try:self.evidence.registries[ref['dataset_id']].permit(ref['representation_id'],'EXACT_ORIGINAL_WORDING',ref['span_ids'])
                    except ValueError:gaps.append('Original wording unavailable: '+uid_)
        if u['dimension']=='WORDING':
            target=self.objects[u['object_id']]
            for unit_id,unit in self.units[uid].items():
                if unit['record']['eligibility']=='EXCLUDED':continue
                found=any(target['feature'] in self.evidence.registries[x['dataset_id']].spans(x['representation_id'])[span]['text'] for x in unit['sources'] for span in x['span_ids'])
                adjudicated=any(c['universe_id']==uid and c['unit_id']==unit_id and c['state']=='INSPECTED' and c['disposition']!='UNRESOLVED' and c['component']['feature']==target['feature'] for c in self.candidates.values())
                if found and not adjudicated:unresolved.append('Unadjudicated literal wording occurrence: '+unit_id)
        eligible={k for k,v in self.units[uid].items() if v['record']['eligibility']=='IN_SCOPE'}
        complete=bool(eligible) and eligible<=reviewed and not gaps and not unresolved
        langs={self.units[uid][n]['record']['language'] for n in reviewed if n in eligible};genres={self.units[uid][n]['record']['genre'] for n in reviewed if n in eligible}
        complete=complete and set(u['languages'])<=langs and set(u['genres'])<=genres
        return {'searched_units':sorted(searched),'reviewed_units':sorted(reviewed),'independent_root_spans':sorted(roots),'gaps':gaps,'unresolved_candidates':unresolved,'complete':complete}

    def snapshot(self,c):
        u=self.universes[c['universe_id']];uid=u['id']
        return fingerprint({'object':self.bases[c['object_id']],'universe':u,'units':self.units[uid],
            'unit_identities':{n:self.evidence.licenses[v['record']['dataset_id']] for n,v in self.units[uid].items()},
            'unit_dates':{n:self.evidence.datasets[v['record']['dataset_id']]['metadata']['date'] for n,v in self.units[uid].items()},
            'searches':{s:self.executions[s] for s in self.searches if self.searches[s]['universe_id']==uid},
            'candidates':[{**x,'basis':self.findings[x['id']]} for x in self.candidates.values() if x['universe_id']==uid],
            'claim':{k:v for k,v in c.items() if k not in {'snapshot','status'}}})

    def claim(self,c):
        shape(c,'id object_id universe_id dimension classification confidence assessment limitations status snapshot','judgment')
        need(c['universe_id'] in self.universes and c['object_id'] in self.objects,'JUDGMENT_OBJECT')
        u=self.universes[c['universe_id']]
        need(c['object_id']==u['object_id'] and c['dimension']==u['dimension'],'JUDGMENT_DIMENSION')
        need(c['classification'] in CLASSES,'ORIGINALITY_BARRIER')
        need(c['confidence'] in {'secure','probable','possible','unresolved'},'CONFIDENCE')
        text(c['assessment'],'assessment');list_text(c['limitations'],'limitations')
        need(not re.search(r'\b(invented|invention|first ever|first occurrence|absolute first|is original|original in all|did not exist|never existed|never occurred before|no earlier occurrence exists|genealogically independent)\b',c['assessment'],re.I),'ORIGINALITY_BARRIER')
        if re.search(r'\b(novel|unique|unprecedented|historically rare|original)\b',c['assessment'],re.I):
            need('within searched evidence' in c['assessment'].casefold(),'BOUNDED_PROSE_REQUIRED')
        need(c['status'] in {'CURRENT','REVALIDATION_REQUIRED'},'STATUS')
        need(isinstance(c['snapshot'],str) and re.fullmatch('[0-9a-f]{64}',c['snapshot']),'SNAPSHOT')
        if c['status']=='REVALIDATION_REQUIRED':return
        need(c['snapshot']==self.snapshot(c),'JUDGMENT_REVALIDATION_REQUIRED',c['id'])
        coverage=self.coverage(u['id']);kind=c['classification']
        candidates=[x for x in self.candidates.values() if x['universe_id']==u['id']]
        positive=[x for x in candidates if x['disposition']=='PRECEDENT'];contrasts=[x for x in candidates if x['disposition'] in {'CONTRAST','REJECTED'}]
        independent=[]
        for candidate in positive:
            roots={v[0] for v in self.findings[candidate['id']]['origins']}
            if roots and not any(roots & prior for prior in independent):independent.append(roots)
        basis=self.bases[c['object_id']]
        uncertain=any(v['state']!='UNAFFECTED' for v in basis['uncertainty'].values()) or any(p['status']!='ESTABLISHED' or p['owner']=='UNKNOWN' or p['role']=='UNRESOLVED_VOICE' for p in basis['ownership'])
        if uncertain:need(kind=='UNRESOLVED' and c['confidence'] in {'possible','unresolved'} and c['limitations'],'DEPENDENCY_UNCERTAINTY')
        if coverage['gaps'] or coverage['unresolved_candidates']:need(bool(c['limitations']),'LIMIT_DISCLOSURE')
        if kind=='UNRESOLVED':need(bool(c['limitations']),'UNRESOLVED_REASON');return
        need(any(self.units[u['id']][uid]['record']['eligibility']=='IN_SCOPE' for uid in coverage['searched_units']),'INSUFFICIENT_SEARCH_COVERAGE')
        if kind=='NO_PRECEDENT_FOUND_WITHIN_SEARCHED_EVIDENCE':need(not positive,'KNOWN_PRECEDENT');return
        if kind=='COMMON':need(len(independent)>=2,'COMMON_POSITIVE_SUPPORT')
        elif kind in {'UNCOMMON','RARE'}:need(bool(positive) and coverage['complete'],'RELATIVE_DISTRIBUTION_SUPPORT')
        elif kind=='APPARENTLY_DISTINCTIVE_WITHIN_SEARCHED_EVIDENCE':need(bool(contrasts) and coverage['complete'],'DISTINCTIVE_CONTRAST_SUPPORT')
        else:
            need(not positive,'KNOWN_PRECEDENT');need(coverage['complete'],'STRONG_SEARCH_COVERAGE')
            # Exact wording still needs conceptual/function inspection of candidate parallels.
            if kind=='POSSIBLE_EARLIEST_KNOWN_OCCURRENCE':
                td=basis['metadata']['date']
                need(td['state']=='SECURE' and td['subject'] in {'WORK_COMPOSITION','WORK_PUBLICATION','EDITION_PUBLICATION'},'EARLIEST_TARGET_DATE')
                need(u['period']['earliest']<td['earliest'] and u['period']['latest']>=td['latest'],'EARLIEST_BOUNDS')
                need(bool(candidates) and all(x['state']=='INSPECTED' for x in candidates),'EARLIEST_CANDIDATE_INSPECTION')
                need(any(self.evidence.datasets[v['record']['dataset_id']]['metadata']['date']['latest'] is not None and self.evidence.datasets[v['record']['dataset_id']]['metadata']['date']['latest']<td['earliest'] for v in self.units[u['id']].values() if v['record']['eligibility']=='IN_SCOPE'),'EARLIER_DOMAIN_COVERAGE')
                for unit in self.units[u['id']].values():
                    if unit['record']['eligibility']=='EXCLUDED':continue
                    d=self.evidence.datasets[unit['record']['dataset_id']]['metadata']['date']
                    need(d['state']=='SECURE' and d['subject'] in {'WORK_COMPOSITION','WORK_PUBLICATION','EDITION_PUBLICATION'} and u['period']['earliest']<=d['earliest']<=d['latest']<=u['period']['latest'],'EARLIEST_COVERAGE_DATING')
                for ref in self.objects[c['object_id']]['source_refs']:
                    self.evidence.registries[ref['dataset_id']].permit(ref['ref']['representation_id'],'EXACT_ORIGINAL_WORDING',ref['ref']['span_ids'])

    def render(self,cid):
        c=self.claims[cid];self.claim(c);need(c['status']=='CURRENT','NOT_CURRENT')
        u=self.universes[c['universe_id']];o=self.objects[c['object_id']];coverage=self.coverage(u['id'])
        lines=[c['classification'].replace('_',' ').capitalize()+'.',
            'Dimension: '+c['dimension'].replace('_',' ').lower()+'; '+o['wording_scope'].lower()+' representation scope; '+o['claim_level'].replace('_',' ').lower()+'.',
            'Evidence confidence: '+c['confidence']+'.',c['assessment'],
            'Comparison boundary.\n\n'+u['boundary'],
            'Period: '+str(u['period']['earliest'])+' to '+str(u['period']['latest'])+'.',
            'Languages: '+', '.join(u['languages'])+'. Genres: '+', '.join(u['genres'])+'.',
            'Search coverage: '+('bounded inspected universe' if coverage['complete'] else 'materially incomplete')+'.',
            'Actually searched units: '+str(len(coverage['searched_units']))+'. Conceptually inspected units: '+str(len(coverage['reviewed_units']))+'.',
            'Independent source-root spans: '+str(len(coverage['independent_root_spans']))+'.']
        for s in self.searches.values():
            if s['universe_id']==u['id']:lines.append('Search record: '+s['mode'].replace('_',' ').lower()+'; '+s['when']+'; '+s['version']+'. Terms: '+', '.join(s['terms'])+'. Concepts: '+', '.join(s['formulations'])+'.')
        for candidate in self.candidates.values():
            if candidate['universe_id']==u['id']:lines.append('Candidate: '+candidate['state'].lower()+'; '+candidate['disposition'].lower()+'. '+candidate['rationale'])
        lines+=['Excluded domain.\n\n'+x for x in u['excluded_domains']]
        lines+=['Limit.\n\n'+x for x in coverage['gaps']+coverage['unresolved_candidates']+c['limitations']]
        if c['classification']=='POSSIBLE_EARLIEST_KNOWN_OCCURRENCE':lines.append('The occurrence claim remains bounded to the inspected evidence. Historical priority and causal origin remain separate questions.')
        return '\n\n'.join(lines)

    def current_outputs(self):
        if self.anchor_mode:
            i=self.investigation
            return {'anchor:'+i['id']: 'Historical novelty/origin unresolved.\n\n'+i['reason']+'\n\nIntended comparison boundary: '+i['universe']['boundary']+'\n\nUninspected discovery leads confer no search coverage, chronology, priority or genealogy license.'}
        return {'novelty:'+k:self.render(k) for k,c in self.claims.items() if c['status']=='CURRENT'}


def execute_search(value,search):
    """Execute a lexical scan or bind an explicit source-backed conceptual review."""
    out=copy.deepcopy(search)
    base=copy.deepcopy(value);base['searches']=[];base['candidates']=[];base['claims']=[]
    obj=Novelty(base);run=obj.execution(out)
    out['results']=run['results'];out['receipt']=fingerprint(run)
    return out


def revalidate(value):
    """Explicit scholarly review: bind current evidence; never silently refresh."""
    out=copy.deepcopy(value)
    for c in out['claims']:c['status']='REVALIDATION_REQUIRED'
    obj=Novelty(out)
    for c in out['claims']:c['snapshot']=obj.snapshot(c);c['status']='CURRENT'
    Novelty(out)
    return out


def validate_completion(directory,checkpoint,rendered_text,registry):
    from pathlib import Path
    import task_state
    path=Path(directory)/'hti-novelty.json'
    from evidence_audit import selected_domain_ids, selected_domain_claims
    selected=selected_domain_ids(checkpoint,'novelty');claims=selected_domain_claims(checkpoint,'novelty')
    if not selected:return
    need(path.is_file(),'INPUT_REQUIRED')
    need(not path.is_symlink(),'INPUT_SYMLINK')
    pub=task_state.require_ready(directory);draft=task_state.current_draft(directory,pub)
    need(path.name in draft['inputs'],'CURRENT_STAGING_REQUIRED')
    obj=Novelty(json.loads(path.read_text()))
    if obj.anchor_mode:
        obj.validate_anchor(checkpoint,registry)
        outputs=obj.current_outputs()
        need({c.get('novelty_id') for c in claims}==selected and selected<=set(outputs),'OUTPUT_BINDINGS')
        for c in claims:
            output=outputs[c['novelty_id']]
            need(c.get('novelty_sha256')==hashlib.sha256(output.encode()).hexdigest() and output in rendered_text,'OUTPUT_HASH_OR_VISIBILITY')
        return
    current={k for k,d in obj.evidence.datasets.items() if d['integrity']==registry.raw and obj.evidence.registries[k].work_id==checkpoint.get('work_id')}
    outputs=obj.current_outputs();need(bool(outputs),'CURRENT_JUDGMENT_REQUIRED')
    for c in obj.claims.values():
        if c['status']=='CURRENT' and 'novelty:'+c['id'] in selected:need(obj.objects[c['object_id']]['dataset_id'] in current,'CURRENT_TASK_OBJECT_REQUIRED')
    need({c.get('novelty_id') for c in claims}==selected and selected<=set(outputs),'OUTPUT_BINDINGS')
    for c in claims:
        output=outputs[c['novelty_id']]
        need(c.get('novelty_sha256')==hashlib.sha256(output.encode()).hexdigest(),'OUTPUT_HASH')
        need(output in rendered_text,'OUTPUT_NOT_VISIBLE')
