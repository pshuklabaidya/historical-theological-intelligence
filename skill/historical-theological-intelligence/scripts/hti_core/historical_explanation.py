"""Evidence-licensed Stage 8 claims on existing argument consumers.

These records explain local argumentative form. They never create a historical
source edge, a witness edge, an identity license, or a causal-origin assertion.
"""
from __future__ import annotations

from .model import ValidationError
from .historical_relations import ChronologyAssessment, AccessAssessment
from .uncertainty import V01_QUALITATIVE_CONFIDENCE

SCHEMA = 'hti-historical-explanation-1'
CLASSIFICATIONS = frozenset({'EXPLICIT_TARGET', 'HISTORICALLY_PROBABLE_TARGET',
    'POSSIBLE_INTERLOCUTOR', 'CONTROVERSY_BACKGROUND', 'LATER_ANALOGY', 'UNRESOLVED'})
FACTORS = frozenset({'EXPLICIT_TARGET_NAME', 'DOCUMENTED_LOCAL_ENGAGEMENT',
    'DENIED_PROPOSITION_SEQUENCE', 'DISTINCTIVE_TERMINOLOGY', 'OBJECTION_SEQUENCE',
    'DOCUMENTED_CONTACT', 'HISTORICAL_AVAILABILITY', 'LOCAL_RELEVANCE',
    'CONTEMPORARY_DISPUTE', 'INSTITUTIONAL_SETTING', 'TREATMENT_ELSEWHERE',
    'DOCTRINAL_SIMILARITY', 'DOCTRINAL_OPPOSITION', 'CHRONOLOGY_ONLY',
    'SHARED_VOCABULARY', 'SHARED_BIBLICAL_SOURCE', 'COMMONPLACE', 'COMMON_THIRD_SOURCE',
    'LATER_RESEMBLANCE', 'COUNTEREVIDENCE'})
DISCRIMINATORS = frozenset({'DOCUMENTED_LOCAL_ENGAGEMENT', 'DENIED_PROPOSITION_SEQUENCE',
    'DISTINCTIVE_TERMINOLOGY', 'OBJECTION_SEQUENCE', 'TREATMENT_ELSEWHERE'})
FACETS = frozenset({'DISPUTED_PROPOSITION', 'AVAILABLE_POSITION', 'INSTITUTION',
    'ACTIVE_CONTROVERSY', 'AUTHORITY', 'CHARACTERISTIC_TERMINOLOGY',
    'CONFESSIONAL_PRESSURE', 'LOCAL_CIRCUMSTANCE'})
PRESSURE_CLAIMS = frozenset({'HISTORICAL_EXISTENCE', 'ENVIRONMENT_SALIENCE', 'ARGUMENT_RELEVANCE'})
COMMON_FIELDS = {'schema_version', 'kind', 'work_id', 'anchor_proposition_ids',
    'confidence', 'chronology', 'access', 'evidence', 'counterevidence', 'alternatives',
    'limitations', 'local_form'}
TARGET_FIELDS = {'classification', 'target'}
PRESSURE_FIELDS = {'facets'}


def require(condition, code, detail):
    if not condition:
        raise ValidationError(code + ': ' + str(detail))


def text(value, label):
    require(isinstance(value, str) and bool(value.strip()), 'EXPLANATION_TEXT', label)
    return value


def sequence(value, label):
    require(isinstance(value, list), 'EXPLANATION_LIST', label)
    return value


def unique_ids(value, label):
    result = sequence(value, label)
    for item in result: text(item, label)
    require(len(set(result)) == len(result), 'EXPLANATION_DUPLICATE', label)
    return result


def records(argument):
    return {k:c for k,c in argument.consumers.items() if 'historical_explanation' in c}


def validate_consumer(argument, consumer):
    """Validate current evidence without promoting source or confidence layers."""
    r = argument.r
    p = consumer['historical_explanation']
    require(isinstance(p, dict) and p.get('schema_version') == SCHEMA, 'EXPLANATION_SCHEMA', consumer['id'])
    kind = p.get('kind')
    require(kind in {'INTERLOCUTOR', 'PRESSURE_FIELD'}, 'EXPLANATION_KIND', kind)
    allowed = COMMON_FIELDS | (TARGET_FIELDS if kind == 'INTERLOCUTOR' else PRESSURE_FIELDS)
    require(set(p) == allowed, 'EXPLANATION_FIELDS', sorted(set(p) ^ allowed))
    require(consumer['kind'] == 'CLAIM' and consumer['purpose'] == 'REPRESENTED_ARGUMENT',
            'EXPLANATION_CONSUMER', consumer['id'])
    require(p['work_id'] == r.work_id, 'EXPLANATION_WORK', p['work_id'])
    anchors = unique_ids(p['anchor_proposition_ids'], 'anchors')
    require(bool(anchors) and set(anchors) <= argument.props.keys(), 'EXPLANATION_ANCHOR', anchors)
    deps = {d['id'] for d in consumer['dependencies'] if d['kind'] == 'proposition'}
    require(set(anchors) <= deps, 'EXPLANATION_DEPENDENCIES', anchors)
    confidence = p['confidence']
    require(confidence in V01_QUALITATIVE_CONFIDENCE - {'illegible'}, 'EXPLANATION_CONFIDENCE', confidence)
    text(p['local_form'], 'local_form')
    for item in unique_ids(p['limitations'], 'limitations'): text(item, 'limitation')
    chronology = ChronologyAssessment.from_dict(p['chronology'])
    access = AccessAssessment.from_dict(p['access'])
    active = consumer['status'] == 'CURRENT'
    if active:
        require(argument.consumer_current(consumer['id']), 'EXPLANATION_REVALIDATION_REQUIRED', consumer['id'])
    def proposition_dependencies(key):
        found={d['id'] for d in argument.consumers[key]['dependencies'] if d['kind']=='proposition'}
        for d in argument.consumers[key]['dependencies']:
            if d['kind']=='consumer':found |= proposition_dependencies(d['id'])
        return found
    deps |= proposition_dependencies(consumer['id'])
    uncertain = False
    for key in deps:
        prop = argument.props[key]
        uncertain |= prop['status'] != 'ESTABLISHED' or prop['owner'] == 'UNKNOWN'
        scopes = r.dependency_scope(prop['representation_id'])
        uncertain |= any(r.spans(n)[s]['state'] != 'VISIBLE' for n,ss in scopes.items() for s in ss)
        uncertain |= any(risk['status'] != 'REVIEWED' and set(risk['span_ids']) & scopes.get(risk['representation_id'],set()) for risk in r.risks.values())
    if uncertain:
        require(confidence in {'possible', 'unresolved'}, 'EXPLANATION_UPSTREAM_UNCERTAINTY', consumer['id'])
        require(bool(p['limitations']), 'EXPLANATION_UNCERTAINTY_DISCLOSURE', consumer['id'])
    evidence = {}
    roots = {}
    for item in sequence(p['evidence'], 'evidence') + sequence(p['counterevidence'], 'counterevidence'):
        require(isinstance(item,dict), 'EXPLANATION_EVIDENCE', item)
        require(set(item) == {'id','factor','source_refs','assessment','target','effect'}, 'EXPLANATION_EVIDENCE_FIELDS', item)
        key = text(item['id'], 'evidence id')
        require(key not in evidence and item['factor'] in FACTORS, 'EXPLANATION_EVIDENCE_ID', key)
        text(item['assessment'], 'evidence assessment')
        require(item['target'] is None or isinstance(item['target'],str) and item['target'].strip(), 'EXPLANATION_EVIDENCE_TARGET', key)
        counter = item in p['counterevidence']
        require(item['effect'] in ({'DEFEATS','WEAKENS','UNRESOLVED','IRRELEVANT'} if counter else {'SUPPORTS','CONTEXT'}), 'EXPLANATION_EFFECT', key)
        refs = sequence(item['source_refs'], 'source_refs')
        require(bool(refs), 'EXPLANATION_SOURCE_REQUIRED', key)
        evidence[key] = item; roots[key] = set()
        for ref in refs:
            n,spans = argument.ref(ref)
            if active: require(argument.ref_current(ref) and argument.source_current(n), 'EXPLANATION_SOURCE_STALE', key)
            # Every evidence role is limited to the supplied representation.
            if active:r.permit(n, 'REPRESENTED_ARGUMENT', spans)
            roots[key].update(r.roots(n))
            if item['factor'] == 'DISTINCTIVE_TERMINOLOGY' and active:
                r.permit(n, 'EXACT_ORIGINAL_WORDING', spans)
            if item['factor'] == 'EXPLICIT_TARGET_NAME' and active:
                require(any(set(spans) & r.dependency_scope(argument.props[a]['representation_id']).get(n,set()) for a in anchors), 'EXPLICIT_TARGET_ANCHOR_SCOPE', key)
                require(item['target'] is not None and any(item['target'].casefold() in r.spans(n)[s]['text'].casefold() for s in spans), 'EXPLICIT_NAME_NOT_VISIBLE', key)
            if any(r.spans(n)[s]['state'] != 'VISIBLE' for s in spans):
                require(confidence in {'possible','unresolved'}, 'EXPLANATION_EVIDENCE_UNCERTAIN', key)
    for alt in sequence(p['alternatives'], 'alternatives'):
        require(isinstance(alt,dict) and set(alt)=={'label','classification','evidence_ids','rationale'}, 'EXPLANATION_ALTERNATIVE', alt)
        text(alt['label'],'alternative label');text(alt['rationale'],'alternative rationale')
        require(alt['classification'] in CLASSIFICATIONS, 'EXPLANATION_ALTERNATIVE_TYPE', alt)
        require(set(unique_ids(alt['evidence_ids'],'alternative evidence')) <= evidence.keys(), 'EXPLANATION_ALTERNATIVE_EVIDENCE', alt)
        # An alternative label is a candidate, never a separately established target.
        require(alt['classification'] in {'POSSIBLE_INTERLOCUTOR','UNRESOLVED','LATER_ANALOGY','CONTROVERSY_BACKGROUND'}, 'EXPLANATION_ALTERNATIVE_PROMOTION', alt)
        if alt['classification']=='POSSIBLE_INTERLOCUTOR':
            require(any(evidence[e]['target']==alt['label'] and evidence[e]['factor'] in DISCRIMINATORS | {'EXPLICIT_TARGET_NAME'} and evidence[e]['effect']=='SUPPORTS' for e in alt['evidence_ids']), 'EXPLANATION_ALTERNATIVE_LOCAL_BASIS', alt['label'])
        if alt['classification']=='LATER_ANALOGY':
            require(any(evidence[e]['factor']=='LATER_RESEMBLANCE' for e in alt['evidence_ids']), 'EXPLANATION_ALTERNATIVE_ANALOGY_BASIS', alt['label'])
    effects = {x['effect'] for x in p['counterevidence']}
    if 'DEFEATS' in effects:
        require(not active or kind=='INTERLOCUTOR' and p['classification']=='UNRESOLVED' and confidence=='unresolved', 'EXPLANATION_DEFEATED', consumer['id'])
    if effects & {'WEAKENS','UNRESOLVED'}:
        require(confidence in {'possible','unresolved'}, 'EXPLANATION_COUNTEREVIDENCE_CAP', consumer['id'])
    support = [x for x in p['evidence'] if x['effect']=='SUPPORTS']
    if kind == 'INTERLOCUTOR':
        classification = p['classification']
        require(classification in CLASSIFICATIONS, 'EXPLANATION_CLASSIFICATION', classification)
        target = p['target']
        require(target is None or isinstance(target,str) and target.strip(), 'EXPLANATION_TARGET', target)
        if classification == 'UNRESOLVED':
            require(confidence == 'unresolved', 'EXPLANATION_UNRESOLVED_CONFIDENCE', consumer['id'])
        else:require(target is not None, 'EXPLANATION_TARGET_REQUIRED', consumer['id'])
        named = classification in {'EXPLICIT_TARGET','HISTORICALLY_PROBABLE_TARGET','POSSIBLE_INTERLOCUTOR'}
        if named and active:
            require(chronology.state == 'COMPATIBLE' and access.state in {'ESTABLISHED','PLAUSIBLE'}, 'EXPLANATION_AVAILABILITY', consumer['id'])
            require(all(argument.props[k]['owner']=='AUTHOR' and argument.props[k]['role'] in {'AUTHOR_ASSERTION','REPLY','REJECTION','DISTINCTION','CONCLUSION','APPLICATION'} for k in anchors), 'EXPLANATION_ANCHOR_OWNER', anchors)
            if confidence in {'secure','probable'}:
                require(all(argument.props[k]['status']=='ESTABLISHED' for k in anchors), 'EXPLANATION_OWNERSHIP', anchors)
        matching = [x for x in support if x['target']==target]
        factors = {x['factor'] for x in matching}
        if active and classification=='EXPLICIT_TARGET':
            require('EXPLICIT_TARGET_NAME' in factors, 'EXPLANATION_EXPLICIT_BASIS', consumer['id'])
            require(confidence in {'secure','probable','possible'}, 'EXPLANATION_EXPLICIT_CONFIDENCE', confidence)
        if active and classification=='HISTORICALLY_PROBABLE_TARGET':
            require(confidence=='probable', 'EXPLANATION_PROBABLE_CONFIDENCE', confidence)
            require('DOCUMENTED_LOCAL_ENGAGEMENT' in factors or bool(factors & DISCRIMINATORS) and 'DOCUMENTED_CONTACT' in factors,
                    'EXPLANATION_DISCRIMINATING_BASIS', consumer['id'])
        if active and classification=='POSSIBLE_INTERLOCUTOR':
            require(confidence in {'possible','unresolved'} and bool(factors & (DISCRIMINATORS | {'EXPLICIT_TARGET_NAME'})), 'EXPLANATION_POSSIBLE_BASIS', consumer['id'])
        if active and classification=='CONTROVERSY_BACKGROUND':
            require(chronology.state=='COMPATIBLE' and {'HISTORICAL_AVAILABILITY','LOCAL_RELEVANCE'} <= {x['factor'] for x in support}, 'EXPLANATION_BACKGROUND_RELEVANCE', consumer['id'])
        if classification=='LATER_ANALOGY':
            require('LATER_RESEMBLANCE' in {x['factor'] for x in support}, 'EXPLANATION_ANALOGY_BASIS', consumer['id'])
    else:
        require(chronology.state=='COMPATIBLE' and access.state in {'ESTABLISHED','PLAUSIBLE'}, 'PRESSURE_AVAILABILITY', consumer['id'])
        facets = sequence(p['facets'], 'facets')
        require(bool(facets), 'PRESSURE_EMPTY', consumer['id'])
        seen=set()
        for facet in facets:
            require(isinstance(facet,dict) and set(facet)=={'id','type','text','claim','evidence_ids','relevance_evidence_ids'}, 'PRESSURE_FACET', facet)
            key=text(facet['id'],'facet id');require(key not in seen,'PRESSURE_DUPLICATE',key);seen.add(key)
            require(facet['type'] in FACETS and facet['claim'] in PRESSURE_CLAIMS, 'PRESSURE_CLAIM_BOUNDARY', key)
            text(facet['text'],'facet text')
            supporting=unique_ids(facet['evidence_ids'],'facet evidence')
            relevant=unique_ids(facet['relevance_evidence_ids'],'facet relevance')
            require(bool(supporting) and bool(relevant) and set(supporting+relevant)<=evidence.keys(), 'PRESSURE_EVIDENCE', key)
            require(any(evidence[x]['factor']=='HISTORICAL_AVAILABILITY' and evidence[x]['effect']=='SUPPORTS' for x in supporting), 'PRESSURE_HISTORICAL_AVAILABILITY', key)
            require(any(evidence[x]['factor']=='LOCAL_RELEVANCE' and evidence[x]['effect']=='SUPPORTS' for x in relevant), 'PRESSURE_LOCAL_RELEVANCE', key)
    return {'consumer_id':consumer['id'],'classification':p.get('classification'),
            'confidence':confidence,'evidence_roots':{k:sorted(v) for k,v in roots.items()},
            'state':consumer['status']}


def render_consumer(argument, consumer):
    validate_consumer(argument,consumer)
    require(consumer['status']=='CURRENT','EXPLANATION_NOT_CURRENT',consumer['id'])
    p=consumer['historical_explanation']
    if p['kind']=='INTERLOCUTOR':
        label=p['classification'].replace('_',' ').capitalize()
        lines=[f"{label}: {p['target'] or 'target identity unresolved'} ({p['confidence']})."]
        if p['classification']=='LATER_ANALOGY':lines.append('The resemblance supports later analogy only.')
    else:
        lines=[f"Historical pressure field ({p['confidence']}):"]
        lines += [f"{f['type'].replace('_',' ').capitalize()}: {f['text']} [{f['claim'].replace('_',' ').lower()}]." for f in p['facets']]
    lines.append('Local argumentative form: '+p['local_form'])
    for item in p['counterevidence']:lines.append('Counterevidence ('+item['effect'].lower()+'): '+item['assessment'])
    for alt in p['alternatives']:lines.append('Alternative ('+alt['classification'].replace('_',' ').lower()+'): '+alt['label']+'. '+alt['rationale'])
    lines += ['Limit: '+s for s in p['limitations']]
    return '\n'.join(lines)


def validate_publication(argument, checkpoint, rendered_text):
    from evidence_audit import selected_domain_ids, selected_domain_claims
    selected=selected_domain_ids(checkpoint,'historical_explanation')
    if not selected:return
    current={k:c for k,c in records(argument).items() if c['status']=='CURRENT'}
    claims=selected_domain_claims(checkpoint,'historical_explanation')
    require({c.get('consumer_id') for c in claims}==selected and selected<=set(current), 'EXPLANATION_OUTPUT_BINDINGS', list(current))
    for claim in claims:
        consumer=current[claim['consumer_id']]
        output=render_consumer(argument,consumer)
        require(claim.get('explanation_sha256')==__import__('hashlib').sha256(output.encode()).hexdigest(), 'EXPLANATION_OUTPUT_HASH', claim.get('claim_id'))
        require(output in rendered_text, 'EXPLANATION_NOT_VISIBLE', claim.get('claim_id'))
