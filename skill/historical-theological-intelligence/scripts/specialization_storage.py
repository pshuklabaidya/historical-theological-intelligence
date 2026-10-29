"""Replaceable specialization storage contracts and explicit portable recovery.

NativeDocsAdapter calls an injected host bridge. No tool availability, document
creation, locator discovery or live response is fabricated by this module.
"""
from __future__ import annotations
import copy
from typing import Protocol
import specialization_core as core

STORAGE_STATES={'NATIVE_BOUND','NATIVE_UNBOUND','PORTABLE_IMPORTED','NO_PERSISTENT_STATE','STALE_STATE','INVALIDATED_STATE','OPERATION_FAILURE','INSTALLED_READ_ONLY'}
CAPABILITIES={'create':True,'read':True,'guarded_replace':True,'work_isolation':True,'exact_locator_recovery':True,'automatic_root_discovery':False,'unguarded_delete':False,'filesystem_cross_chat_recovery':False,'skill_self_modification':False}

class StorageError(core.SpecializationError):
    pass

class LocatorProvider(Protocol):
    def binding(self, account_scope: str, namespace: str) -> dict | None: ...

class BoundLocatorProvider:
    """Explicit host binding only. Later onboarding may replace this provider."""
    def __init__(self,binding=None):self.value=copy.deepcopy(binding)
    def binding(self,account_scope,namespace):
        if self.value is None:return None
        return copy.deepcopy(validate_binding(self.value,account_scope,namespace))

def validate_binding(value,account_scope,namespace):
    core.require(isinstance(value,dict) and set(value)=={'backend','locator','account_scope','namespace'},'LOCATOR_BINDING_FIELDS')
    core.require(value['backend']=='CLAUDE_DOCS' and isinstance(value['locator'],str) and 0<len(value['locator'])<=1024 and value['locator']==value['locator'].strip() and not any(ord(x)<33 for x in value['locator']),'MALFORMED_NATIVE_LOCATOR')
    core.require(core.identifier(account_scope) and core.identifier(namespace) and value['account_scope']==account_scope and value['namespace']==namespace,'LOCATOR_SCOPE_MISMATCH')
    # The host validates native locator syntax and ownership; domain never parses IDs.
    return value

class Storage(Protocol):
    def status(self) -> dict: ...
    def create_registry(self,registry: dict) -> dict: ...
    def read_registry(self) -> dict: ...
    def write_registry(self,registry: dict,expected_revision: int,expected_hash: str) -> dict: ...
    def create_record(self,record: dict) -> dict: ...
    def read_record(self,binding: dict,subject: dict) -> dict: ...
    def write_record(self,binding: dict,record: dict,expected_revision: int,expected_hash: str) -> dict: ...

def envelope(kind,payload,namespace,account_scope):
    core.require(kind in {'REGISTRY','RECORD'},'STORAGE_KIND')
    validate_payload(kind,payload)
    return {'schema_version':'hti-storage-envelope-1','kind':kind,'namespace':namespace,'account_scope':account_scope,'payload':copy.deepcopy(payload),'payload_sha256':core.digest(payload)}

def validate_payload(kind,payload):
    if kind=='REGISTRY':core.validate(payload)
    else:
        core.require(isinstance(payload,dict) and set(payload)=={'registry_id','scope','record'},'STORAGE_RECORD_FIELDS')
        core.require(core.identifier(payload['registry_id']),'STORAGE_REGISTRY_ID')
        core.scope(payload['scope']);r=payload['record'];m=core.manifest(r['manifest'])
        core.require(payload['scope']==m['scope'],'STORAGE_RECORD_SCOPE')
        # Validate complete record shape through its containing registry when consumed.
        core.require(set(r)=={'manifest','revision','state_version','created_revision','updated_revision','status','supersedes','license','dependencies','claims'} and all(core.revision(r[k]) for k in ('revision','state_version','created_revision','updated_revision')) and r['status'] in core.STATUSES and isinstance(r['dependencies'],dict) and isinstance(r['claims'],dict),'STORAGE_RECORD_STATE')
        if r['license'] is not None:core.validate_license(r['license'],m)
        for claim in r['claims'].values():
            core.require(isinstance(claim,dict) and set(claim)=={'surface','value','status','revision','provenance','dependencies','physical_license'} and claim['surface'] in m['permitted_surfaces'] and claim['status'] in core.STATUSES and core.revision(claim['revision']) and isinstance(claim['dependencies'],dict) and bool(claim['dependencies']),'STORAGE_CLAIM_STATE')
            core.provenance(claim['provenance'])

def validate_envelope(value,kind,namespace,account_scope):
    core.require(isinstance(value,dict) and set(value)=={'schema_version','kind','namespace','account_scope','payload','payload_sha256'},'STORAGE_ENVELOPE_FIELDS')
    core.require(value['schema_version']=='hti-storage-envelope-1' and value['kind']==kind and value['namespace']==namespace and value['account_scope']==account_scope,'STORAGE_ENVELOPE_SCOPE')
    validate_payload(kind,value['payload']);core.require(value['payload_sha256']==core.digest(value['payload']),'STORAGE_HASH_MISMATCH')
    if kind=='REGISTRY':core.require(value['payload']['namespace']==namespace and value['payload']['account_scope']==account_scope,'STORAGE_REGISTRY_SCOPE')
    return value

class NativeDocsAdapter:
    """Production request/response adapter to a capability-aware host bridge.

    The bridge must implement docs create/read and update-replace with both
    native ifRev and block ifHash guards. Unsupported guards fail closed.
    A native read receipt binds locator, native revision, block and full payload
    hash. These receipts describe observed responses, not historical evidence.
    """
    def __init__(self,provider,account_scope,namespace,bridge=None,available=False):
        core.require(core.identifier(account_scope) and core.identifier(namespace),'STORAGE_ACCOUNT_NAMESPACE')
        self.provider=provider;self.account_scope=account_scope;self.namespace=namespace;self.bridge=bridge;self.available=available;self.last_failure=None;self.receipts={};self.observed={}
    def status(self):
        if self.last_failure:return {'state':'OPERATION_FAILURE','reason':self.last_failure,'general_hti_available':True}
        if not self.available or self.bridge is None:return {'state':'NO_PERSISTENT_STATE','reason':'Native Docs host unavailable','general_hti_available':True}
        try:b=self.provider.binding(self.account_scope,self.namespace)
        except (ValueError,TypeError):return {'state':'OPERATION_FAILURE','reason':'Invalid registry binding','general_hti_available':True}
        return {'state':'NATIVE_BOUND' if b else 'NATIVE_UNBOUND','reason':'Explicit binding required' if not b else None,'general_hti_available':True}
    def _binding(self):
        core.require(self.available and self.bridge is not None,'NATIVE_STORAGE_UNAVAILABLE')
        binding=self.provider.binding(self.account_scope,self.namespace);core.require(binding is not None,'NATIVE_STORAGE_UNBOUND')
        return binding
    def _request(self,operation,kind,binding=None,payload=None,expected=None):
        core.require(self.available and self.bridge is not None,'NATIVE_STORAGE_UNAVAILABLE')
        if binding:validate_binding(binding,self.account_scope,self.namespace)
        request={'contract':'hti-claude-docs-bridge-1','operation':operation,'kind':kind,'account_scope':self.account_scope,'namespace':self.namespace,'binding':copy.deepcopy(binding),'envelope':envelope(kind,payload,self.namespace,self.account_scope) if payload is not None else None,'guard':copy.deepcopy(expected)}
        if operation=='REPLACE':core.require(expected is not None,'NATIVE_REVISION_GUARD_REQUIRED')
        try:response=self.bridge(request)
        except Exception as exc:
            self.last_failure='Native bridge operation failed';raise StorageError(self.last_failure) from exc
        try:
            core.require(isinstance(response,dict) and response.get('status') in {'OK','CONFLICT','FAILURE'},'NATIVE_RESPONSE_SHAPE')
            if response['status']!='OK':
                self.last_failure='NATIVE_'+response['status'];raise StorageError(self.last_failure)
            core.require(set(response)=={'status','binding','native_revision','block_id','block_hash','envelope','guard_applied'},'NATIVE_RESPONSE_FIELDS')
            actual=validate_binding(response['binding'],self.account_scope,self.namespace)
            if binding:core.require(actual==binding,'NATIVE_LOCATOR_SUBSTITUTION')
            core.require(core.revision(response['native_revision']) and core.identifier(response['block_id']) and isinstance(response['block_hash'],str) and len(response['block_hash'])==8,'NATIVE_REVISION_RECEIPT')
            env=validate_envelope(response['envelope'],kind,self.namespace,self.account_scope)
            # Host encodes one canonical JSON code block, excluding display wrappers.
            core.require(response['block_hash']==core.digest(env)[:8],'NATIVE_BLOCK_HASH_MISMATCH')
            if operation=='REPLACE':
                core.require(response['guard_applied']==expected and response['native_revision']>expected['native_revision'],'NATIVE_GUARD_NOT_APPLIED')
            else:core.require(response['guard_applied'] is None,'NATIVE_UNEXPECTED_GUARD')
            if payload is not None:core.require(env['payload']==payload,'NATIVE_WRITE_NOT_CONFIRMED')
            receipt={'backend':'CLAUDE_DOCS','binding':copy.deepcopy(actual),'native_revision':response['native_revision'],'block_id':response['block_id'],'block_hash':response['block_hash'],'envelope_sha256':core.digest(env),'payload_sha256':env['payload_sha256'],'kind':kind}
            self.receipts[actual['locator']]=receipt;self.observed[actual['locator']]=copy.deepcopy(env['payload']);self.last_failure=None
            return {'state':'NATIVE_BOUND','payload':copy.deepcopy(env['payload']),'receipt':copy.deepcopy(receipt),'binding':copy.deepcopy(actual)}
        except (ValueError,KeyError,TypeError) as exc:
            self.last_failure=str(exc);raise StorageError(self.last_failure) from exc
    def create_registry(self,registry):
        core.validate(registry);core.require(registry['namespace']==self.namespace and registry['account_scope']==self.account_scope,'STORAGE_REGISTRY_SCOPE')
        core.require(self.provider.binding(self.account_scope,self.namespace) is None,'REGISTRY_ALREADY_BOUND')
        # Returns a binding for the caller/provider to retain; no bootstrap discovery.
        return self._request('CREATE','REGISTRY',payload=registry)
    def read_registry(self):return self._request('READ','REGISTRY',binding=self._binding())
    def _guard(self,binding,kind,expected_revision,expected_hash):
        core.require(core.revision(expected_revision) and core.sha(expected_hash),'NATIVE_EXPECTED_REVISION')
        receipt=self.receipts.get(binding['locator']);core.require(receipt is not None and receipt['kind']==kind,'NATIVE_READ_BEFORE_REPLACE')
        observed=self.observed[binding['locator']];observed_revision=observed['revision'] if kind=='REGISTRY' else observed['record']['revision']
        core.require(receipt['payload_sha256']==expected_hash and observed_revision==expected_revision,'REVISION_CONFLICT')
        return {'native_revision':receipt['native_revision'],'block_id':receipt['block_id'],'block_hash':receipt['block_hash'],'payload_revision':expected_revision,'payload_sha256':expected_hash}
    def write_registry(self,registry,expected_revision,expected_hash):
        core.validate(registry);binding=self._binding();guard=self._guard(binding,'REGISTRY',expected_revision,expected_hash)
        core.require(registry['revision']>expected_revision,'REGISTRY_REVISION_NOT_ADVANCED')
        return self._request('REPLACE','REGISTRY',binding,registry,guard)
    def create_record(self,record):return self._request('CREATE','RECORD',payload=record)
    def read_record(self,binding,subject):
        result=self._request('READ','RECORD',binding=binding)
        core.require(result['payload']['scope']==subject,'STORAGE_WRONG_SUBJECT');return result
    def write_record(self,binding,record,expected_revision,expected_hash):
        validate_payload('RECORD',record);guard=self._guard(binding,'RECORD',expected_revision,expected_hash)
        old=self.observed[binding['locator']];core.require(record['scope']==old['scope'] and record['registry_id']==old['registry_id'] and record['record']['manifest']['specialization_id']==old['record']['manifest']['specialization_id'],'NATIVE_RECORD_SUBSTITUTION')
        core.require(record['record']['revision']>expected_revision,'RECORD_REVISION_NOT_ADVANCED')
        return self._request('REPLACE','RECORD',binding,record,guard)
    def compare_revision(self,binding,kind,expected_revision,expected_hash):
        result=self._request('READ',kind,binding=binding);payload=result['payload'];current=payload['revision'] if kind=='REGISTRY' else payload['record']['revision']
        return {'matches':current==expected_revision and core.digest(payload)==expected_hash,'revision':current,'sha256':core.digest(payload)}
    def export_validated_bundle(self,subject):
        return export_bundle(self.read_registry()['payload'],subject)
    def import_validated_bundle(self,bundle,subject,existing=None):
        # Explicit non-native recovery; no unrequested native write follows import.
        return import_bundle(bundle,subject,existing)
    def enumerate_records(self,subject):
        registry=self.read_registry()['payload'];core.scope(subject)
        return {rid:copy.deepcopy(r) for rid,r in registry['records'].items() if core.matches(r['manifest']['scope'],subject)}
    def mark_stale(self,registry,key,expected_revision,expected_hash,reason):
        result=core.mark(registry,key,'STALE',expected_revision,reason);return self.write_registry(result,expected_revision,expected_hash)
    def invalidate(self,registry,key,expected_revision,expected_hash,reason):
        result=core.mark(registry,key,'INVALIDATED',expected_revision,reason);return self.write_registry(result,expected_revision,expected_hash)
    def supersede(self,registry,old_id,manifest,expected_revision,expected_hash,reason):
        result=core.supersede(registry,old_id,manifest,expected_revision,reason);return self.write_registry(result,expected_revision,expected_hash)
    def delete(self,*args,**kwargs):
        raise StorageError('HARD_DELETE_OUTSIDE_ORDINARY_OPERATION: explicit human-approved host operation required')

BUNDLE_SCHEMA='hti-specialization-bundle-1'

def export_bundle(reg,subject):
    core.validate(reg);core.scope(subject)
    selected={rid:copy.deepcopy(r) for rid,r in reg['records'].items() if core.matches(r['manifest']['scope'],subject)}
    # Export only a scope-closed dependency subset. Never silently omit dependencies.
    required=set()
    def walk(dep):
        if dep in required:return
        required.add(dep)
        if dep not in reg['anchors']:
            parts=dep.split(':');rid=parts[1];core.require(rid in selected,'BUNDLE_SCOPE_NOT_CLOSED')
            obj=selected[rid] if parts[0]=='record' else selected[rid]['claims'][parts[2]]
            for d in obj['dependencies']:walk(d)
    for r in selected.values():
        for obj in [r,*r['claims'].values()]:
            for d in obj['dependencies']:walk(d)
    portable=copy.deepcopy(reg);portable['records']=selected;portable['anchors']={k:copy.deepcopy(v) for k,v in reg['anchors'].items() if k in required};portable['storage_binding']=None
    # Native binding removed deliberately; account scope is provenance, not a usable locator.
    core.validate(portable)
    payload={'registry':portable,'scope':copy.deepcopy(subject),'origin':'EXPLICIT_PORTABLE_EXPORT','source_registry_sha256':core.digest(reg),'migration':{'schema':core.SCHEMA,'automatic_migration':False}}
    entries={'registry':core.digest(portable),'manifests':{rid:core.digest(r['manifest']) for rid,r in selected.items()},'records':{rid:core.digest(r) for rid,r in selected.items()}}
    return {'schema_version':BUNDLE_SCHEMA,'payload':payload,'entries':entries,'bundle_sha256':core.digest({'schema_version':BUNDLE_SCHEMA,'payload':payload,'entries':entries})}

def import_bundle(bundle,subject,existing=None):
    core.scope(subject)
    core.require(isinstance(bundle,dict) and set(bundle)=={'schema_version','payload','entries','bundle_sha256'} and bundle['schema_version']==BUNDLE_SCHEMA,'BUNDLE_SCHEMA_INCOMPATIBLE')
    core.require(bundle['bundle_sha256']==core.digest({k:bundle[k] for k in ('schema_version','payload','entries')}),'BUNDLE_INTEGRITY')
    p=bundle['payload'];core.require(isinstance(p,dict) and set(p)=={'registry','scope','origin','source_registry_sha256','migration'},'BUNDLE_FIELDS')
    core.require(p['scope']==subject,'BUNDLE_WRONG_SUBJECT')
    core.require(p['origin']=='EXPLICIT_PORTABLE_EXPORT' and core.sha(p['source_registry_sha256']) and p['migration']=={'schema':core.SCHEMA,'automatic_migration':False},'BUNDLE_PROVENANCE')
    reg=core.validate(p['registry']);core.require(reg['storage_binding'] is None,'PORTABLE_NATIVE_BINDING_FORBIDDEN')
    core.require(all(core.matches(r['manifest']['scope'],subject) for r in reg['records'].values()),'BUNDLE_WRONG_SUBJECT')
    expected={'registry':core.digest(reg),'manifests':{rid:core.digest(r['manifest']) for rid,r in reg['records'].items()},'records':{rid:core.digest(r) for rid,r in reg['records'].items()}}
    core.require(bundle['entries']==expected,'BUNDLE_ENTRY_INTEGRITY')
    if existing is not None:
        core.validate(existing);core.require(existing['registry_id']==reg['registry_id'] and existing['namespace']==reg['namespace'] and existing['account_scope']==reg['account_scope'],'BUNDLE_REGISTRY_CONFLICT')
        core.require(reg['revision']>=existing['revision'],'BUNDLE_STALE_REVISION')
        if reg['revision']==existing['revision']:
            comparable=copy.deepcopy(existing);comparable['storage_binding']=None
            core.require(core.digest(reg)==core.digest(comparable),'BUNDLE_REVISION_CONFLICT')
        else:
            # No implicit merging or replacement of another scope's records.
            core.require(set(existing['records'])<=set(reg['records']),'BUNDLE_MERGE_REQUIRES_EXPLICIT_RESOLUTION')
    return {'state':'PORTABLE_IMPORTED','registry':copy.deepcopy(reg),'receipt':{'origin':'PORTABLE_IMPORTED','bundle_sha256':bundle['bundle_sha256'],'registry_sha256':core.digest(reg),'source_registry_sha256':p['source_registry_sha256']}}

def validate_context_storage(context):
    state=context['storage_state'];core.require(state in STORAGE_STATES,'STORAGE_STATE')
    registry=context['registry'];receipt=context['storage_receipt']
    if state=='INSTALLED_READ_ONLY':
        core.require(registry is not None and registry['storage_binding'] is None and isinstance(receipt,dict) and set(receipt)=={'origin','resources','registry_sha256'} and receipt['origin']=='INSTALLED_READ_ONLY' and receipt['registry_sha256']==core.digest(registry),'INSTALLED_CONTEXT_RECEIPT')
        # Package-byte and fresh identity validation occurs in the same core
        # completion gate; this storage state never claims persistent recovery.
    elif state=='NATIVE_BOUND':
        core.require(registry is not None and isinstance(receipt,dict) and set(receipt)=={'backend','binding','native_revision','block_id','block_hash','envelope_sha256','payload_sha256','kind'},'NATIVE_CONTEXT_RECEIPT')
        validate_binding(receipt['binding'],registry['account_scope'],registry['namespace'])
        env=envelope('REGISTRY',registry,registry['namespace'],registry['account_scope'])
        core.require(receipt['backend']=='CLAUDE_DOCS' and receipt['kind']=='REGISTRY' and receipt['payload_sha256']==core.digest(registry) and receipt['envelope_sha256']==core.digest(env) and receipt['block_hash']==core.digest(env)[:8] and core.revision(receipt['native_revision']) and core.identifier(receipt['block_id']),'NATIVE_CONTEXT_INTEGRITY')
    elif state=='PORTABLE_IMPORTED':
        core.require(registry is not None and isinstance(receipt,dict) and set(receipt)=={'origin','bundle_sha256','registry_sha256','source_registry_sha256'} and receipt['origin']=='PORTABLE_IMPORTED' and core.sha(receipt['bundle_sha256']) and core.sha(receipt['source_registry_sha256']) and receipt['registry_sha256']==core.digest(registry) and registry['storage_binding'] is None,'PORTABLE_CONTEXT_RECEIPT')
    else:
        core.require(not context['uses'],'UNAVAILABLE_SPECIALIZATION_USE')
        if state in {'NATIVE_UNBOUND','NO_PERSISTENT_STATE','OPERATION_FAILURE'}:core.require(registry is None and receipt is None,'UNAVAILABLE_STORAGE_FABRICATED_STATE')
        else:core.require(registry is not None,'STALE_STORAGE_STATE_MISSING')
