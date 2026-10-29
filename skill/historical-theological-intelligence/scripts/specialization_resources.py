"""Licensed immutable release resources, distinct from persistent research state.

All domain licensing, claims and dependencies use specialization_core. Resource
text is data, never executable. The catalog contains routing identifiers only.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import errno
from contextvars import ContextVar
from pathlib import Path
import specialization_core as core

ROOT = Path(__file__).resolve().parents[1]
CATALOG = 'resources/specializations/catalog.json'
READ_TRACE = ContextVar('installed_read_trace', default=None)

def bytes_at(root, locator, expected):
    root = Path(root).resolve()
    path = (root / locator).resolve()
    core.require(isinstance(locator, str) and not Path(locator).is_absolute()
                 and root in path.parents and not any(x == '..' for x in Path(locator).parts),
                 'INSTALLED_RESOURCE_PATH')
    core.require(core.sha(expected), 'INSTALLED_RESOURCE_HASH_SHAPE')
    trace = READ_TRACE.get()
    if trace is not None:
        trace.append({'locator': locator, 'expected_sha256': expected})
    data = path.read_bytes()
    core.require(hashlib.sha256(data).hexdigest() == expected, 'INSTALLED_RESOURCE_HASH')
    return data

def catalog(root=ROOT):
    release, paths = release_manifest(root)
    core.require(CATALOG in paths, 'INSTALLED_CATALOG_NOT_MANIFESTED')
    data = json.loads(bytes_at(root, CATALOG, paths[CATALOG]))
    core.require(set(data) == {'schema_version', 'entries'} and data['schema_version'] == 'hti-installed-catalog-1', 'INSTALLED_CATALOG_SCHEMA')
    seen = set()
    for entry in data['entries']:
        core.require(set(entry) == {'specialization_id', 'level', 'scope', 'manifest_locator', 'manifest_sha256'}, 'INSTALLED_CATALOG_FIELDS')
        core.scope(entry['scope'], entry['level'])
        key = (entry['level'], core.digest(entry['scope']))
        core.require(key not in seen, 'AMBIGUOUS_INSTALLED_ROUTING')
        seen.add(key)
    return data

def eligible(checkpoint, binding, root=ROOT):
    license = core.identity_license(checkpoint, binding)
    rank = core.evidence_audit.IDENTITY_STATES.index(license['identity_state'])
    # No specialization catalog or payload is opened for an unlicensed task.
    if rank < 2:
        return []
    selected = []
    for entry in catalog(root)['entries']:
        if core.matches(entry['scope'], license['scope']) and rank >= core.evidence_audit.IDENTITY_STATES.index(core.LEVELS[entry['level']]):
            selected.append(entry)
    return selected

def materialize(checkpoint, binding, root=ROOT):
    """Reconstruct a task snapshot, never write the installed package or Docs."""
    entries = eligible(checkpoint, binding, root)
    if not entries:
        return {'schema_version':core.SCHEMA,'storage_state':'NO_PERSISTENT_STATE',
                'registry':None,'identity_binding':copy.deepcopy(binding),'uses':[],
                'registry_sha256':None,'storage_receipt':None}
    reg = core.new_registry('installed-release', 'installed-resources', 'release-distribution')
    receipts = []
    for entry in entries:
        m = core.manifest(json.loads(bytes_at(root, entry['manifest_locator'], entry['manifest_sha256'])))
        core.require(m['scope'] == entry['scope'] and m['level'] == entry['level'] and m['specialization_id'] == entry['specialization_id'], 'INSTALLED_MANIFEST_SUBSTITUTION')
        reg = core.add_record(reg, m, reg['revision'], 'Read immutable release manifest after general identity licensing.')
        rid = m['specialization_id']
        reg = core.license_record(reg, rid, checkpoint, binding, reg['revision'], 'Independent general identity licenses this exact scope.')
        resource_ids = set()
        for resource in m['resources']:
            key = resource['resource_id']
            core.require(key not in resource_ids, 'DUPLICATE_INSTALLED_RESOURCE')
            resource_ids.add(key)
            packet = json.loads(bytes_at(root, resource['locator'], resource['sha256']))
            core.require(set(packet) == {'schema_version','scope','provenance','claims','assets'} and packet['schema_version'] == 'hti-installed-resource-1' and packet['scope'] == m['scope'], 'INSTALLED_PACKET_SCOPE')
            p = packet['provenance']
            core.require(set(p) == {'locator','evidence_refs','verification','caveats','stage5_components'} and p['verification'] == 'INSPECTED' and p['stage5_components'] and isinstance(p['caveats'], list), 'INSTALLED_PROVENANCE')
            prov = {'origin':'general_evidence','locator':p['locator'],'evidence_refs':p['evidence_refs']}
            core.provenance(prov)
            for asset in packet['assets']:
                core.require(asset['work_id']==m['scope']['work_id'] and asset['representation_type']=='HISTORICAL_TRANSLATION', 'INSTALLED_ASSET_SCOPE')
                bytes_at(root,asset['locator'],asset['sha256'])
            anchor = 'evidence:' + rid + '.' + key
            reg = core.set_anchor(reg, anchor, {'revision':1,'status':'CURRENT','sha256':resource['sha256'],'provenance':prov,'source_ref':None}, reg['revision'], 'Hash-bound inspected resource provenance.')
            for claim in packet['claims']:
                core.require(set(claim) == {'claim_id','value'} and isinstance(claim['value'], str) and bool(claim['value']), 'INSTALLED_CLAIM_FIELDS')
                cid = claim['claim_id']
                core.require(cid not in reg['records'][rid]['claims'], 'DUPLICATE_INSTALLED_CLAIM')
                reg = core.put_claim(reg, rid, cid, {'surface':resource['surface'],'value':claim['value'],'status':'CURRENT','revision':1,'provenance':prov,'dependencies':{anchor:core.snapshot(core.nodes(reg)[anchor])},'physical_license':None}, reg['revision'], 'Inspected bounded reference claim, not identity evidence.')
            receipts.append({'record_id':rid,'resource_id':key,'sha256':resource['sha256']})
    return {'schema_version':core.SCHEMA,'storage_state':'INSTALLED_READ_ONLY',
            'registry':reg,'identity_binding':copy.deepcopy(binding),'uses':[],
            'registry_sha256':core.digest(reg),'storage_receipt':{'origin':'INSTALLED_READ_ONLY','resources':receipts,'registry_sha256':core.digest(reg)}}

def validate_context(context, checkpoint, root=ROOT, records=None):
    from specialization_storage import validate_context_storage
    validate_context_storage(context)
    core.require(context['storage_state']=='INSTALLED_READ_ONLY','INSTALLED_STORAGE_ORIGIN')
    core.validate(context['registry'])
    core.require(context['registry_sha256']==core.digest(context['registry']) and context['storage_receipt']['registry_sha256']==context['registry_sha256'], 'INSTALLED_CONTEXT_INTEGRITY')
    selected = list(context['registry']['records']) if records is None else records
    if not selected:
        return context
    expected = materialize(checkpoint, context['identity_binding'], root)
    core.require(expected['storage_state'] == 'INSTALLED_READ_ONLY', 'INSTALLED_LICENSE_UNAVAILABLE')
    # A changed edition or exemplar license cannot suppress unrelated work
    # resources. Certify only the records actually read/used, against fresh
    # package content and their scope-specific licensing snapshots.
    for rid in selected:
        core.require(rid in expected['registry']['records'] and context['registry']['records'].get(rid)==expected['registry']['records'][rid], 'INSTALLED_CONTEXT_REVALIDATION_REQUIRED')
        for dep in context['registry']['records'][rid]['claims'].values():
            for anchor in dep['dependencies']:
                core.require(context['registry']['anchors'].get(anchor)==expected['registry']['anchors'].get(anchor), 'INSTALLED_CONTEXT_REVALIDATION_REQUIRED')
        actual_receipts=[x for x in context['storage_receipt']['resources'] if x['record_id']==rid]
        expected_receipts=[x for x in expected['storage_receipt']['resources'] if x['record_id']==rid]
        core.require(actual_receipts==expected_receipts,'INSTALLED_CONTEXT_REVALIDATION_REQUIRED')
    return context

def resource_packet(context, checkpoint, rid, resource_id, root=ROOT):
    validate_context(context, checkpoint, root, records=[rid])
    core.activate(context['registry'], rid, checkpoint, context['identity_binding'])
    m = context['registry']['records'][rid]['manifest']
    found = [r for r in m['resources'] if r['resource_id'] == resource_id]
    core.require(len(found) == 1, 'INSTALLED_RESOURCE_UNAVAILABLE')
    r = found[0]
    return json.loads(bytes_at(root, r['locator'], r['sha256']))

def witness(context, checkpoint, rid, resource_id, root=ROOT):
    packet = resource_packet(context, checkpoint, rid, resource_id, root)
    assets = packet['assets']
    core.require(len(assets) == 1, 'HISTORICAL_WITNESS_UNAVAILABLE')
    asset = assets[0]
    core.require(set(asset) == {'witness_id','work_id','locator','sha256','representation_type','language','evidence_root_id','derivative_of','rights','caveats'} and asset['work_id'] == packet['scope']['work_id'] and asset['representation_type'] == 'HISTORICAL_TRANSLATION' and asset['derivative_of'] == packet['scope']['work_id'] and core.identifier(asset['evidence_root_id']) and asset['rights'] and asset['caveats'], 'HISTORICAL_WITNESS_SCOPE')
    return asset, bytes_at(root, asset['locator'], asset['sha256'])

def search(context, checkpoint, rid, resource_id, query, limit=8, radius=3, purpose='REPRESENTED_ARGUMENT', root=ROOT):
    # English text cannot be requested as exact original Latin or independent
    # Latin corroboration. Existing source_integrity governs every later use.
    core.require(purpose == 'REPRESENTED_ARGUMENT', 'HISTORICAL_TRANSLATION_PURPOSE')
    core.require(isinstance(query, str) and query.strip() and type(limit) is int and 1 <= limit <= 20 and type(radius) is int and 0 <= radius <= 15, 'BOUNDED_WITNESS_SEARCH')
    asset, data = witness(context, checkpoint, rid, resource_id, root)
    lines = data.decode('utf-8').splitlines()
    page = None
    hits = []
    for i, line in enumerate(lines):
        if line.startswith('[PAGE '):
            page = line
        if query.casefold() in line.casefold():
            lo, hi = max(0, i-radius), min(len(lines), i+radius+1)
            hits.append({'line':i+1,'span_id':'L'+str(i+1),'page_marker':page,'context_start':lo+1,'context':lines[lo:hi]})
            if len(hits) == limit:
                break
    return {'work_id':asset['work_id'],'witness':copy.deepcopy(asset),'independence_group':asset['evidence_root_id'],
            'query':query,'hits':hits,'alignment':'UNRESOLVED_UNTIL_BOTH_SOURCES_INSPECTED',
            'exact_original_wording':False,'independent_latin_corroboration':False}

def _bind_installed_use(context, checkpoint, rid, cid, output_claim_id, integrity=None):
    validate_context(context, checkpoint, records=[rid])
    claim = core.read_claim(context['registry'], rid, cid, checkpoint, context['identity_binding'], integrity)
    core.require(not any(u['output_claim_id'] == output_claim_id for u in context['uses']), 'DUPLICATE_SPECIALIZATION_USE')
    out = copy.deepcopy(context)
    out['uses'].append({'record_id':rid,'claim_id':cid,'output_claim_id':output_claim_id,'claim_sha256':core.digest(claim)})
    return out, {'claim_id':output_claim_id,'claim_type':'specialization_reference','origin':'specialization_fact','status':'asserted','value':claim['value'],'evidence_ids':[], 'specialization_ref':{'record_id':rid,'claim_id':cid}}


def release_manifest(root=ROOT):
    data = (Path(root)/'SHA256SUMS.txt').read_bytes()
    entries = {}
    for line in data.decode('utf-8').splitlines():
        fields = line.split('  ', 1)
        core.require(len(fields) == 2 and core.sha(fields[0]), 'RELEASE_MANIFEST_SHAPE')
        digest, locator = fields
        core.require(locator not in entries and locator and not Path(locator).is_absolute()
                     and '..' not in Path(locator).parts and '\\' not in locator, 'RELEASE_MANIFEST_PATH')
        entries[locator] = digest
    return hashlib.sha256(data).hexdigest(), entries


def route_checkpoint(directory, root=ROOT):
    import task_state
    pub = task_state.descriptor(directory)
    core.require(pub is not None, 'CURRENT_PUBLICATION_REQUIRED')
    if pub['route'] == 'commentary':
        return json.loads(task_state.path(directory, 'checkpoint').read_text())
    import complete_scholar_view_task as scholar
    task = json.loads(task_state.path(directory, 'scholar').read_text())
    evidence = scholar.copy_evidence(task)
    claims = copy.deepcopy(task.get('claims', []))
    state, selected, _, _ = scholar.build_identity(task, evidence, claims)
    checkpoint = json.loads((Path(root)/'resources/templates/evidence-checkpoint.json').read_text())
    checkpoint.update(work_id=task['work_id'], identity_state=state, selected_claim_ids=selected,
                      evidence=evidence, claims=claims)
    return checkpoint


def publication_binding(directory):
    import task_state
    pub = task_state.descriptor(directory)
    core.require(pub is not None, 'CURRENT_PUBLICATION_REQUIRED')
    return {**{k:pub[k] for k in ('task_directory','publication_id','sequence','request_sha256','route')},
            'publication_sha256': hashlib.sha256(task_state.path(directory,'publication').read_bytes()).hexdigest()}


def input_binding(directory, primary):
    import task_state
    pub = task_state.descriptor(directory)
    keys = ('checkpoint','plan') if pub['route'] == 'commentary' else ('scholar',)
    names = [task_state.FILES[k] for k in keys]
    integrity = task_state.path(directory,'integrity')
    if integrity.exists():
        names.append(integrity.name)
    result = {}
    for name in names:
        path = directory/name
        core.require(path.is_file() and not path.is_symlink(), 'READINESS_INPUT_PATH')
        result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    result['primary_context_sha256'] = core.digest(primary)
    return result


def inspect_installed(checkpoint, binding, root=ROOT):
    """Read-only release authentication, also used to verify retained snapshots.

    Reconstruct comparison values in memory; never attach a context, read a
    passage for interpretation, mutate task state or certify terminal readiness.
    """
    release, paths = release_manifest(root)
    core.require(CATALOG in paths, 'INSTALLED_CATALOG_NOT_MANIFESTED')
    package = {'release_sha256':release,'catalog_locator':CATALOG,'catalog_sha256':paths[CATALOG]}
    trace = []; token = READ_TRACE.set(trace)
    entries = None; snapshot = None
    try:
        entries = eligible(checkpoint, binding, root)
        snapshot = materialize(checkpoint, binding, root) if entries else None
        attempt = None if not entries else {'operation':'AUTHENTICATE_INSTALLED','reads':trace,'outcome':'PREPARED','failure':None}
        state = 'PREPARED' if entries else 'VERIFIED_NO_ELIGIBLE'
    except OSError as exc:
        # Only a real located, bounded file availability failure is fallback.
        allowed = {errno.ENOENT,errno.EACCES,errno.EPERM,errno.EIO,errno.ENOTDIR}
        core.require(bool(trace) and exc.errno in allowed, 'INSTALLED_AVAILABILITY_UNCLASSIFIED')
        attempt = {'operation':'AUTHENTICATE_INSTALLED','reads':trace,'outcome':'UNAVAILABLE',
                   'failure':{'locator':trace[-1]['locator'],'errno':exc.errno}}
        state = 'UNAVAILABLE_AFTER_VALIDATED_ATTEMPT'
    finally:
        READ_TRACE.reset(token)
    return state, package, entries, snapshot, attempt


def empty_primary():
    return {'schema_version':core.SCHEMA,'storage_state':'NO_PERSISTENT_STATE',
            'registry':None,'identity_binding':None,'uses':[], 'registry_sha256':None,'storage_receipt':None}


def assess(directory, context, checkpoint, root=ROOT):
    """Build comparison bindings; caller owns pre-publication task writes."""
    primary = core.validate_primary(context, checkpoint, root)
    binding = core.derive_binding(checkpoint)
    if binding is None:
        state, package, entries, installed, attempt = 'DORMANT', None, None, None, None
        identity = None
    else:
        license = core.identity_license(checkpoint, binding)
        identity = {'binding':binding,'license_sha256':core.digest(license)}
        state, package, entries, installed, attempt = inspect_installed(checkpoint,binding,root)
    return {'schema':'hti-installed-readiness-1','state':state,
            'publication':publication_binding(directory),'inputs':input_binding(directory,primary),
            'identity':identity,'package':package,'eligible':entries,'installed_context':installed,'attempt':attempt}


def prepare_current(directory, root=ROOT, binding=None):
    import task_state
    from terminal_output import atomic_write
    task_state.research_entry(directory)
    checkpoint = route_checkpoint(directory, root)
    derived = core.derive_binding(checkpoint)
    if binding is not None:
        core.require(binding == derived, 'INDEPENDENT_BINDING_MISMATCH')
    path = task_state.path(directory,'specialization')
    context = json.loads(path.read_text()) if path.exists() else empty_primary()
    primary = core.primary_context(context)
    old = context.get('installed_readiness')
    fresh = assess(directory, context, checkpoint, root)
    if old is not None:
        core.require(isinstance(old,dict) and set(old)==set(fresh), 'INSTALLED_READINESS_FIELDS')
        retained = old.get('installed_context')
        if retained is not None and retained.get('uses'):
            core.require(fresh['state']=='PREPARED' and core.primary_context(retained) == {**fresh['installed_context'],'uses':retained['uses']}, 'USED_INSTALLED_CONTEXT_RECONCILIATION_REQUIRED')
            fresh['installed_context'] = copy.deepcopy(retained)
    out = {**primary,'installed_readiness':fresh}
    # The complete primary projection is preserved, not normalized or merged.
    core.require(core.primary_context(out)==primary, 'PRIMARY_CONTEXT_OVERWRITE')
    atomic_write(path, json.dumps(out,ensure_ascii=False,indent=2).encode()+b'\n')
    return out


def validate_readiness(directory, context, checkpoint, root=ROOT):
    actual = context.get('installed_readiness')
    fields = {'schema','state','publication','inputs','identity','package','eligible','installed_context','attempt'}
    core.require(isinstance(actual,dict) and set(actual)==fields and actual['schema']=='hti-installed-readiness-1', 'INSTALLED_READINESS_FIELDS')
    # Authentication only: no writes, preparation attachment or research here.
    expected = assess(directory, context, checkpoint, root)
    installed = actual['installed_context']
    if installed is not None:
        primary = core.primary_context(installed)
        core.require(set(installed)==core.PRIMARY_FIELDS and primary['storage_state']=='INSTALLED_READ_ONLY' and expected['installed_context'] is not None, 'INSTALLED_READINESS_SNAPSHOT')
        core.validate_primary(primary, checkpoint, root)
        compare = copy.deepcopy(primary); compare['uses'] = []
        core.require(compare == expected['installed_context'], 'INSTALLED_READINESS_SNAPSHOT')
        expected['installed_context'] = copy.deepcopy(primary)
    core.require(actual == expected, 'INSTALLED_READINESS_STALE_OR_ASSERTED')
    # Compare against the actual canonical completion checkpoint too, not only
    # the pre-publication compact input or a cached preparatory checkpoint.
    binding = core.derive_binding(checkpoint)
    core.require(actual['identity'] == (None if binding is None else
        {'binding':binding,'license_sha256':core.digest(core.identity_license(checkpoint,binding))}), 'INSTALLED_READINESS_IDENTITY')
    return installed


def select_view(context, record_id, owner=None):
    if set(context)==core.PRIMARY_FIELDS:
        core.require(owner in {None,'primary'}, 'SPECIALIZATION_VIEW')
        return context, 'primary'
    core.primary_context(context)
    readiness = context.get('installed_readiness')
    installed = readiness.get('installed_context') if isinstance(readiness,dict) else None
    views = {'primary':core.primary_context(context)}
    if installed is not None:
        views['installed'] = installed
    matches = [name for name,view in views.items() if view.get('registry') is not None and record_id in view['registry']['records']]
    core.require(owner in {None,'primary','installed'}, 'SPECIALIZATION_VIEW')
    if owner is None:
        core.require(len(matches)==1, 'AMBIGUOUS_SPECIALIZATION_VIEW')
        owner = matches[0]
    core.require(owner in matches, 'SPECIALIZATION_VIEW_UNAVAILABLE')
    return views[owner], owner


def bind_use(context, checkpoint, rid, cid, output_claim_id, integrity=None, owner=None):
    view, name = select_view(context,rid,owner)
    existing = list(context['uses'])
    ready = context.get('installed_readiness')
    if isinstance(ready,dict) and ready.get('installed_context') is not None:
        existing += ready['installed_context']['uses']
    core.require(not any(u['output_claim_id']==output_claim_id for u in existing), 'DUPLICATE_SPECIALIZATION_USE')
    if view['storage_state']=='INSTALLED_READ_ONLY':
        updated, claim = _bind_installed_use(view,checkpoint,rid,cid,output_claim_id,integrity)
    else:
        core.validate_primary(view,checkpoint)
        payload = core.read_claim(view['registry'],rid,cid,checkpoint,view['identity_binding'],integrity)
        updated = copy.deepcopy(view)
        updated['uses'].append({'record_id':rid,'claim_id':cid,'output_claim_id':output_claim_id,'claim_sha256':core.digest(payload)})
        claim = {'claim_id':output_claim_id,'claim_type':'specialization_reference','origin':'specialization_fact','status':'asserted','value':payload['value'],'evidence_ids':[],'specialization_ref':{'record_id':rid,'claim_id':cid}}
    out = copy.deepcopy(context)
    if name=='installed':
        out['installed_readiness']['installed_context'] = updated
    else:
        for key in core.PRIMARY_FIELDS:
            out[key] = updated[key]
    if 'installed_readiness' in out and out['installed_readiness'] is not None:
        out['installed_readiness']['publication'] = None
    return out, claim


def invalidate_access(directory):
    import task_state
    from terminal_output import atomic_write
    task_state.research_entry(directory)
    path = task_state.path(directory,'specialization')
    context = json.loads(path.read_text())
    if isinstance(context.get('installed_readiness'),dict):
        context['installed_readiness']['publication'] = None
        atomic_write(path,json.dumps(context,ensure_ascii=False,indent=2).encode()+b'\n')
    return context


def authorize_path(path, state_dir=None):
    """Guard generic witness reads and invalidate any pre-existing readiness seal."""
    path = Path(path).resolve()
    if (ROOT/'resources/specializations').resolve() not in path.parents:
        return
    import task_state
    directory = task_state.resolve(state_dir)
    checkpoint = route_checkpoint(directory)
    context = invalidate_access(directory)
    candidates = [core.primary_context(context)]
    ready = context.get('installed_readiness')
    if isinstance(ready,dict) and ready.get('installed_context') is not None:
        candidates.append(ready['installed_context'])
    for view in candidates:
        if view.get('registry') is None or view['storage_state']!='INSTALLED_READ_ONLY':
            continue
        for rid,record in view['registry']['records'].items():
            for resource in record['manifest']['resources']:
                packet = resource_packet(view,checkpoint,rid,resource['resource_id'])
                for asset in packet['assets']:
                    if (ROOT/asset['locator']).resolve()==path:
                        witness(view,checkpoint,rid,resource['resource_id'])
                        return copy.deepcopy(asset)
    core.require(False,'INSTALLED_PATH_NOT_LICENSED')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('operation', choices=['prepare','refresh','read','search'])
    p.add_argument('--state-dir', required=True, type=Path)
    p.add_argument('--binding', type=Path)
    p.add_argument('--view', choices=['primary','installed'])
    p.add_argument('--record'); p.add_argument('--resource'); p.add_argument('--query')
    args = p.parse_args()
    import task_state
    directory = task_state.resolve(str(args.state_dir))
    if args.operation in {'prepare','refresh'}:
        context = prepare_current(directory, binding=json.loads(args.binding.read_text()) if args.binding else None)
        print(json.dumps({'state':context['installed_readiness']['state'],'persistence_write':False,'structured_completion':'UNFINISHED'}))
    else:
        checkpoint = route_checkpoint(directory)
        context = invalidate_access(directory)
        view, _ = select_view(context,args.record,args.view)
        value = resource_packet(view,checkpoint,args.record,args.resource) if args.operation=='read' else search(view,checkpoint,args.record,args.resource,args.query)
        print(json.dumps(value,ensure_ascii=False,indent=2))

if __name__ == '__main__':
    main()
