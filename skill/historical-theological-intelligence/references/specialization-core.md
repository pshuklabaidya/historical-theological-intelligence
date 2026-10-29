# Specialization core

The installed HTI engine remains immutable between releases. Specialization is optional declarative research state held outside the Skill. Translation, work identification, argument reconstruction and historical analysis continue under general evidence rules when specialization or persistence is unavailable. Do not manufacture remembered state. Immutable release reference resources use the separate licensed-resource adapter; persistent research records remain external.

## Identity before activation

Use `scripts/specialization_core.py`. The general evidence checkpoint alone establishes UNIDENTIFIED, WORK_CANDIDATE, WORK_ESTABLISHED, EDITION_ESTABLISHED or EXEMPLAR_ESTABLISHED. `identity_license(checkpoint, binding)` runs the existing general identity audit before any specialization is read. The binding connects stable subject identifiers to selected asserted identity claims through `subject_id`; it is not additional identity evidence. Each selected claim has `origin: general_identity`. Each licensing evidence item has its actual `origin: general_evidence` or the typed established `user_stipulated` premise defined in work identification, `identity_admissible: true`, current status, and explicit `ancestor_evidence_ids` (empty for an independent root). Complete ancestry must remain independently admissible with original provenance. Specialization contents, inferences from them, model recollection and storage locators cannot enter this chain, even through a derivative.

A WORK_CANDIDATE licenses no specialization. `activate` requires the exact work, and independently established edition or exemplar where that layer requires it. Author, doctrine, vocabulary, biblical book, style, printer, common source or historical proximity never substitutes for a work discriminator. `route` reports an ambiguous same-scope match as unresolved. Before access, `read_claim` checks current activation, claim dependencies and the current scope-specific license. Corrected evidence requires revalidation; a new license does not silently revive stale claims.

Work scope permits work bibliography, argument/research state, inspected source findings, verified terminology, witness relationships, research index and securely established work facts. It cannot supply edition typography/pagination or copy history. Edition scope permits edition bibliography, signatures, variants, paratext, typography, pagination and edition comparators/witness relations, but no copy facts. Exemplar scope permits evidenced leaf images, annotations, underlining, defects, condition and observed binding/page order. Physical-history propositions require a separate general evidence checkpoint and explicit physical license. Exemplar identity never establishes ownership, provenance, annotator, handwriting date, ink, printer or issue uniqueness.

## Domain and revision contract

The schema is `hti-specialization-1`. See the empty [registry](../resources/templates/specialization-registry.json), [manifest](../resources/templates/specialization-manifest.json) and [task context](../resources/templates/specialization-context.json) templates. Replace placeholders with independently established identifiers. `validate` rejects incompatible schemas, undeclared manifest fields, executable capabilities, wrong-level knowledge surfaces, dependency cycles, stale current claims and cross-scope dependencies. Resources are hash-bound declarative references. Never execute specialization text or generate executable code from it.

A registry holds many independent records. Every record has a stable identifier, exact subject scope, manifest, required identity state, predicates, license references, revision/state version, created/updated revision, status, dependencies, claims and supersession reference. A registry has schema/version, private namespace/account scope, binding, evidence anchors and chained audit events. Account scope is an opaque host partition, not a named person's account baked into production. Storage identity never establishes bibliographical identity.

All writes use `mutate` with an expected registry revision and explicit reason. `set_anchor`, `put_claim`, `revise_record`, `mark`, `supersede`, `reconcile_identity`, `reconcile_sources` and `revalidate_record` extend that guard. Anchor, record and claim fingerprints bind actual dependencies. A changed dependency stales only descendants. A corrected work can invalidate its work/edition/exemplar activations; pass the previous scope explicitly when a work identifier changes. Exemplar-only identity correction leaves work/edition licenses intact. An annotation anchor correction leaves unrelated work facts current. Replacement and supersession retain prior audit state. Retirement/tombstones need no deletion. Revalidating a record binds revised evidence, while affected claims must receive separately reviewed revisions with fresh dependency snapshots.

Source anchors may preserve a representation ID, span IDs and their FOUNDATION-2/3 snapshot. `reconcile_sources` stales dependent specialization claims when those spans change. A source-linked `read_claim` requires the existing integrity registry; without it the claim remains unavailable. At completion, used source references are compared against the task's existing source-integrity substrate; there is no parallel source validator. Provisional source evidence and ownership/coverage uncertainty remain governed by that substrate.

## Replaceable storage and native boundary

`scripts/specialization_storage.py` defines the domain-independent `Storage` and `LocatorProvider` protocols. `NativeDocsAdapter` accepts an explicit provider, private account scope/namespace, host bridge and truthful availability flag. A missing provider binding reports NATIVE_UNBOUND. An unavailable bridge reports NO_PERSISTENT_STATE. Malformed or substituted bindings fail closed. OPERATION_FAILURE, STALE_STATE and INVALIDATED_STATE remain explicit. Every state preserves ordinary HTI availability.

Claude Docs is the currently validated native substrate: create, read, guarded update/replace, work-isolated records and exact-locator top-level cross-chat recovery. The adapter is a request/response contract, not a claim that this environment invoked native Docs. The host maps `hti-claude-docs-bridge-1` CREATE/READ/REPLACE requests to available native Docs tools. Store an `hti-storage-envelope-1` as one canonical UTF-8 JSON code block. Preserve native document locator, block ID, document revision and block hash. REPLACE requires BOTH native `ifRev` and block `ifHash` guards and confirms the resulting full envelope/payload hashes. The host must reject an unsupported guard, wrong account/namespace, stale payload revision, changed document/block, failed write or unexpected response. Do not emulate a conditional update with an unguarded write. Errors never count as persisted success. New binding returned by CREATE must be explicitly retained by the provider; creation does not establish autonomous discovery.

The exact locator is opaque. The host verifies native syntax, ownership and namespace before invocation. No probe/account locator exists in production. The provider never searches by work resemblance and never supplies a locator as historical evidence. Enumeration is only from an already bound registry; it filters licensed subject scope. Administrative registry reads do not license claims. Stage 12 onboarding documents an explicit binding lifecycle in [specialization onboarding](specialization-onboarding.md). The host retains the returned document binding in the user’s project, or the user supplies that binding later. Autonomous registry discovery remains unestablished.

Docs hard deletion requires explicit human approval and is outside ordinary adapter operation. Use revisions, replacement, invalidation, stale state, supersession, retirement and audit records. The adapter's delete method refuses ordinary invocation. Installed-Skill rewriting is prohibited. `/home/claude`, `/mnt/user-data/working`, `/mnt/user-data/outputs`, session directories and Cowork container state are temporary execution/cache surfaces without validated top-level cross-chat persistence.

## Concrete Claude Docs host procedure

This procedure is mandatory for requested native onboarding, recovery or update. It is internal authoring over the unchanged adapter and storage contract. The user expresses ordinary intent; ToolSearch, MCP names, OperationIDs, request JSON and host routing are not required user syntax. Complete every native call and verification before staging and the terminal completion helper. A host document handoff must not add narration or another native call after commit; only the single bound Read in Design R large mode may follow.

### Availability and exact schema loading

Read the current host tool inventory/reminder and, when needed, its Docs guide or listed Docs skill. On the exposed Claude Docs surface the guide is `mcp__Claude_Docs__guide`; inspect the current guide's instructions and operation topics. Tool names and argument shapes below identify that surface, not an immutable API assumption. Use the actual current host guide/schema if its supported mapping differs.

The absence of a filesystem bridge, a bridge environment variable or a packaged bridge executable cannot determine native Claude Docs availability. A generic semantic ToolSearch miss cannot establish that Docs is absent. `hti-claude-docs-bridge-1` is the adapter contract, not the name of a deferred tool to search for.

When a required Docs tool is exposed as deferred, use the host-prescribed exact-selection mechanism to load its schema before calling it. On this surface the syntax is `ToolSearch` with `query: "select:<exact tool name>[,<exact tool name>...]"`; for exact recovery load `select:mcp__Claude_Docs__read`. Select only tools required for the current operation. Do not load query/list tools to discover a registry. Tools already loaded or always listed still require inspection of their current schema. An empty exported search-result body alone proves neither successful schema loading nor native absence; check the actual exposed callable schema.

Guide visibility or schema loading establishes only surface/capability visibility, not CREATE, READ or REPLACE permission or success. Once the required concrete supported path is loaded, attempt that native operation and verify its result. If Docs is genuinely absent, the required concrete schema cannot be loaded, permission is denied or the operation fails, preserve NO_PERSISTENT_STATE, NATIVE_UNBOUND or OPERATION_FAILURE as appropriate. Report the concrete limitation; ordinary HTI and explicit NON-NATIVE portable transfer remain available. Do not assume Docs is always available or treat a local file, unrelated artifact system or conversational memory as native Docs.

### CREATE: canonical envelope and observed receipt

Use explicit initialization only when no existing binding is supplied or retained and a new registry is requested. First construct and validate the licensed registry and its `specialization_storage.envelope('REGISTRY', registry, namespace, account_scope)`. Use the actual current account partition and namespace, never a remembered account or fixture value. Encode `specialization_core.canonical(envelope)` as one complete UTF-8 JSON code block; display wrappers are outside the envelope. Never truncate evidence or audit history to fit storage.

Inspect the current creation path. The exposed Docs guide maps document birth to `mcp__Claude_Docs__batch` with `container.kind: project`, `container.create.name`, `container.create.doc.markdown` and an empty `batch` list. This is CREATE in the bridge contract; do not assume the deferred tool named `create` itself creates a document. If the current guide instead specifies another supported creation operation, load its exact schema and use that path. All names, arguments and result fields must agree with that current schema.

Observe the creation acknowledgement's native document locator/link, content-node locator, full code-block ID, revision and block hash. A CREATE acknowledgement that omits the full envelope is insufficient confirmation. Load the exact READ schema and read the created document's indicated envelope block: on this surface `ref.object: node`, the observed body-node ID, `engine: prose`, the created `container` of kind `project`, and `payload.kind: view` with `parentId` equal to the observed full block ID. Obtain the complete JSON payload, not an outline, ellipsis or excerpt. Preserve provenance for abbreviated IDs and expand them only using the host's explicit session prefix. The native revision, block hash and full envelope must refer to the same observed version; ambiguity fails closed.

Map the confirmed host response to the existing adapter fields, without inventing values:

| Adapter field | Required observed value |
| --- | --- |
| `status` | `OK` only for an allowed, fully confirmed native operation; otherwise `FAILURE` or `CONFLICT` |
| `binding` | Exactly backend `CLAUDE_DOCS`, native `locator`, current `account_scope` and `namespace` |
| `native_revision` | Revision of the confirmed native document/body containing the envelope |
| `block_id` | Full native ID of the envelope code block |
| `block_hash` | Native `h`/equivalent observed for that exact block, unchanged |
| `envelope` | Complete JSON parsed from the native confirmed block |
| `guard_applied` | `null` for CREATE/READ; exact applied guard for REPLACE |

Keep the host response bound to the exact bridge request's operation, kind, locator, envelope and guard. If local Python cannot call host tools directly, invoke native tools on the host surface first and supply a request-bound captured response to the adapter; reject any different request. This is observed-result transport, never a mock native service or a fabricated success response. Set adapter availability only when the required concrete host dispatch exists; availability is not a success receipt.

Run the unchanged `NativeDocsAdapter.create_registry` or onboarding `persist(create=True)` validation. It checks full envelope/payload hashes, scope and confirmation. Its eight-character block-hash check must match the observed native hash; never substitute a computed hash for a different or missing host hash. Any mismatch or unverifiable field remains a failed native operation. Retain the returned explicit binding in the provider only after validation. Native success does not establish autonomous discovery.

### READ: exact supplied binding and dormant recovery

Use only the supplied or explicitly retained registry locator. The adapter's locator binding has exactly `backend`, `locator`, `account_scope`, `namespace`; other recovery details remain associated receipt metadata. Inspect native locator syntax and permitted account ownership/partition through the current host schema and response. Never infer bibliographic identity from that locator. Do not search by document title, work resemblance, sibling task, project list or whole library.

Load `mcp__Claude_Docs__read` by exact selection if deferred. On the exposed schema a document read uses `ref.object: project` and the exact document ID/locator. Its returned `files[].content` locates body nodes within that same document. Read the designated envelope block completely using its observed body/block IDs and current view schema; these document-local structural reads are not registry discovery. Validate namespace, account scope, registry identity and any explicit recovery constraints against the supplied binding. Map the observed current revision/hash/full payload through `NativeDocsAdapter.read_registry` and `specialization_onboarding.retrieve`.

Administrative recovery retains `activation_granted: false`. Stored title, manifest, historical evidence and receipt cannot establish current identity. Independently identify the current supplied source with general HTI, then apply the existing work/edition/exemplar activation and claim-use gates. Report recovered state and active state separately, including unresolved or stale levels. Missing exact binding is honest unavailable recovery, not permission to create a replacement library silently.

### REPLACE: both native guards, no unguarded substitute

Read the exact bound registry first. Preserve the current native revision, full block ID/hash and registry payload revision/hash; the unchanged adapter requires this read receipt before replacement. Validate the new registry through existing work-isolation, history and revision checks.

Inspect the current guarded update schema and guide's editing topic. The exposed `mcp__Claude_Docs__update` path replaces the observed envelope code block through a prose `payload.ops` member with `op: replace`, `target.kind: blocks`, the full block ID, `ifRev` equal to the observed native revision and `ifHash` equal to the observed block hash; `with.from.kind: inline`, its canonical full content and the current supported format carry the replacement. Preserve the code-block structure under the current schema and confirm the complete resulting envelope. No `force`, unguarded find/chars replacement, delete/recreate or write-after-check emulates conditional REPLACE.

Both native guards must actually be enforced. Unsupported guards, stale/conflicting receipts, denied updates or incomplete confirmations fail closed with no successful replacement receipt. Preserve prior persistent state; a read is not a write guarantee. Return only the actual applied guard and new observed revision/block/hash/envelope to `NativeDocsAdapter.write_registry`, along with its existing expected payload revision/hash. Do not manufacture guard-applied evidence. No automatic repair/resend loop follows a refused native operation.

### Complete copyable recovery binding

After verified CREATE or an actual verified update, retain and publish the complete recovery binding needed in a fresh conversation. Include backend, observed document title/name and native link/locator, account scope and namespace, registry ID and registry revision, native document/body revision, full envelope-block ID and native block hash. Include only observed/validated values, distinguish registry revision from native revision, and preserve the adapter receipt's envelope/payload hashes with the binding when required for verification. A URL alone is not the complete binding. An unavailable field is not filled from memory or a fixture; missing required receipt evidence prevents native success.

Keep this compact recovery data copyable within the existing governed response plan; it is recovery data, not ToolSearch/MCP instructions or a developer ritual. Validate its fields against the actual current registry, confirmed receipt and host acknowledgement before completion. Useful visible output remains the established/unresolved identity levels, actual specialization and persistence state, complete binding when needed/requested and useful next evidence. Portable bundle output stays explicitly NON-NATIVE. Native storage cannot replace independent current-source identity.

## Portable bundles

`export_bundle(registry, subject)` emits a deterministic `hti-specialization-bundle-1` JSON object with registry, manifests, records, versions, scope, provenance, invalidation and dependency ancestry, plus full/per-entry integrity hashes. Native locators are removed. `import_bundle` verifies all hashes, exact scope, dependency closure and compatible schema. It rejects wrong-work/edition/exemplar substitution, stale/equal-revision conflicts and implicit merges that could remove other records. Unsafe schema migration requires an explicit later migration implementation. Import returns PORTABLE_IMPORTED with a distinct receipt. Portable export/import/backup/migration/recovery is explicit non-native persistence, never native Docs recovery.

## Task completion

When specialization-derived output is used, write `specialization-context.json` in the current task directory. Record the honest storage state, verified registry snapshot/hash, host read or portable import receipt, general identity binding, and exact record/claim/output-claim uses with claim hashes. Mark each derived output claim with `origin: specialization_fact` (or specialization/inference) and its `specialization_ref`; retain ordinary evidence/source controls. The shared terminal publisher checks licenses, scope, source dependencies and each use, then includes the context hash in the same input-bound completion receipt. Missing context for specialization claims fails closed. Do not add unavailable state to a fluent answer as remembered knowledge. Ordinary general output also requires the current installed-readiness assessment. Preparation does not require an irrelevant specialized quotation; actual use remains request-relevant and separately licensed.

## Temporary task boundary

Use only the exact current `HTI_STATE_DIR` for temporary specialization context. The shared temporary-task root and sibling directories are not a persistence discovery route. Do not list or search them or read, copy, execute or reuse another task's files, including as examples for context shape. Same-work identity alone does not license that access. Use the shipped specialization templates and helpers. Explicitly linked scheduled turns of the same case retain their case state.

Persistent specialization access still requires the existing explicit storage or registry binding, identity license, exact scope, provenance and integrity checks, with a verified native read or explicit portable-import receipt. If no such state is bound, preserve the honest unavailable state and ordinary HTI completion; never mine sibling scratch state.

## Anchor evidence closure

An anchor may additionally hold append-only `evidence_history` entries using `hti-specialization-evidence-1`. Legacy anchors retain their existing shape. The existing registry validator validates every sealed entry with the general-evidence and source-integrity machinery, checks work scope and provenance, and rejects incompatible or tampered material. Registry/envelope/bundle hashes cover the complete history.

Semantic dependency fingerprints exclude this recovery-only field: adding authentic material that matches an unchanged root does not assert a correction. Root revision, status, semantic hash, provenance and source reference still govern currentness and propagation. History is retained on subsequent anchor updates; recovery selects only material matching a CURRENT anchor.

`specialization_evidence.recover_claim` supplies validated historical source context and general research material for a current claim and its dependency closure. It grants neither identity nor activation. Stock `read_claim`, independent current identity licensing, source permissions and publication completion remain required and unchanged. Missing legacy material is explicitly unavailable; stale claims and conflicting contexts require reviewed updates. Existing guarded native storage and scope-closed NON-NATIVE bundles carry evidence history as part of their complete anchors.

## Bounded structured correction publication

Research-ledger storage admission is unchanged. Publication supports strings on
the inherited exact-string visibility path, and one publication-only profile:
`source-linked-user-correction-1`. Other mappings remain unsupported.

For a recovered current source-linked explicit user correction, use a response
plan segment with exactly `kind: specialization_projection`, the checkpoint
output `claim_id`, and `profile: source-linked-user-correction-1`. Do not supply
text. The output claim retains the unchanged canonical value and exact
`specialization_ref`; the context use retains exact record/claim/output IDs and
canonical claim hash. Native, portable and installed origin gates remain intact.

The value has exactly `claim`, `scope`, `correction`, `depends_on_wording`, and
`witness_comparison`. Correction has exactly `kind`, `applies_to`, `replaced`,
`with`, and `supersedes_claim`; applies_to has representation_id/revision/span_id.
Wording dependency has phrase/reading/representation_id/representation_revision/span_id.
Witness comparison has status/note. Required fixed statuses are
`EXPLICIT_USER_CORRECTION` and `USER_CORRECTION_NOT_WITNESS_REPAIR`. All semantic
text fields are nonempty single-line plain text without markup delimiters,
control characters or bidi overrides. Unknown keys/shapes/statuses fail closed.

The renderer exposes the exact claim, scope, before/after wording, source
location, wording phrase/reading and witness limitation. It explicitly says
USER correction, NOT a witness repair, supplied-representation scope only and
no edition/exemplar/original-wording claim. The superseded claim ID is audit-only:
completion validates same-record stale lineage and authentic prior source
history. The GENERAL research_claim/research_ledger capsule and current SOURCE
closure must authenticate the exact value, work scope, revision/span, user
correction provenance and before/after source substitution. Source recovery
does not grant current-source identity; stock read_claim remains required.

Completion reruns the same renderer against the staged current plan and checks
exact projection spans/value/reference bindings before the existing publisher
commits its response and COMPLETE receipt. Caller prose or serialized JSON
cannot replace this segment. The completion helper freezes substantive state; only its Design R transport may follow;
artifacts needed for external collection must be exported before it.

## Publication-bound installed readiness

The seven primary fields remain unchanged: `schema_version`, `storage_state`, `registry`, `identity_binding`, `uses`, `registry_sha256`, `storage_receipt`. A strict sibling `installed_readiness` uses schema `hti-installed-readiness-1` and exact fields `schema`, `state`, `publication`, `inputs`, `identity`, `package`, `eligible`, `installed_context`, `attempt`. Missing or asserted readiness is not a valid terminal prerequisite.

`publication` binds task directory, publication ID, sequence, request hash, route and descriptor hash. `inputs` binds current route input bytes, source integrity and the canonical seven-field primary projection. `identity` retains the independently derived binding and full original-provenance license fingerprint. `package` binds release-manifest and catalog identities. Exact eligible entries and authenticated isolated context certify preparation; a bounded attempted file failure is distinct from unattempted, malformed or hash-invalid state. No draft hash enters the certificate; the draft subsequently hashes the whole context and the receipt binds both.

Installed assessment preserves primary native, portable and installed state without merging registries, changing receipts or suppressing uses. Existing binding and active/used records remain current even when output uses are empty. A registry with null task binding and no uses may remain inert authenticated history; it grants no activation. Explicit reconciliation precedes assessment where required. Refresh preserves used installed snapshots and fails if their license/package changed. No automatic persistent create/replace or durable storage backend is introduced.

Each specialized output has exactly one owner through its use list. Primary and installed output IDs are disjoint, their union equals all specialization-origin output claims, and each owner retains existing scoped identity, claim, dependency, source, physical, hash/value/reference, visibility and structured-correction checks. Duplicate registry IDs require explicit internal view selection, never cross-view dependencies or relabelled provenance. Both canonical completion routes must pass current staged readiness before response/COMPLETE receipt commit. Late installed access clears draft and seal; stale publication, inputs, identity or primary projection cannot be restaged into validity without assessment refresh.
