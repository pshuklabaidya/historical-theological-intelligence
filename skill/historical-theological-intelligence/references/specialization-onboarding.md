# Specialization onboarding

“I just acquired this book”, “Add this book to my specialized library”, requests to add a repeatedly used work, and “Improve this specialization” begin this workflow. Ordinary translation does not. The assistant manages records; the user need not learn manifests or registry schemas. Start with whatever evidence is available. Photographs are not required to begin.

## The user workflow

1. Describe the holding or the work used repeatedly. A holding report is retained as USER_REPORTED context. It proves no work, edition, exemplar, provenance or physical-history identity. With no secure work identity, onboarding remains partial and unregistered; ordinary HTI continues.
2. Use general HTI work identification and bibliographic verification, independently of the specialization. Record competing editions and their bibliographic evidence. Request a title page, colophon, discriminating leaf or physical photograph only when it would materially resolve a particular claim. A named title or plausible author is a candidate until the ordinary identity gate licenses it.
3. Record useful witnesses/comparators and relevant historical translations with their actual access, representation ancestry and independence. Discovery does not mean inspection. Preserve unresolved searches. There is no fixed witness hierarchy. Extend the existing Verified Work Dossier and Dynamic Witness Graph with licensed evidence.
4. Create work-level knowledge once work identity is established. Create edition knowledge only after independent edition discrimination, and exemplar knowledge only after independent copy identity. A reported physical holding can be recorded without securely identifying its exemplar. Copy identity licenses no unsupported ownership history, ink, handwriting date, binding history or provenance.
5. Validate each new/materially updated layer. Use only independently licensed scopes, general evidence and current source snapshots. Keep native declarative manifests and activation predicates. Empty fields remain empty/unresolved; no Vermigli factual defaults are copied. Keep each claim’s own dependency roots, revisions and verification state.
6. For native persistence, follow the mandatory [concrete Claude Docs host procedure](specialization-core.md#concrete-claude-docs-host-procedure), create a registry through the accepted adapter, or read the explicitly bound existing registry first. Exposed deferred Docs tools require exact schema selection, not semantic-search inference or a filesystem bridge search. Attempt and confirm the required native operation before claiming success. A confirmed CREATE returns a complete copyable recovery binding with the observed document locator and receipt details; retain it in the project or provide it with the next conversation. Do not reduce it to a URL alone. The user-facing instruction is: “Keep this registry document link/binding with your project. In a new conversation, provide that binding and ask to recover your specialized library.” A confirmed native receipt is required before saying the specialization was persisted. Session files are temporary and do not count as cross-conversation persistence.
7. In a fresh top-level conversation, supply the same document binding (or use the explicitly retained project binding). Read that exact registry through Docs. No autonomous discovery of the whole library is promised. Without a binding, report that prior state could not be recovered; do not fabricate it, search sibling tasks or silently start a replacement registry.
8. Add new bibliography, edition discrimination, photographs, witnesses or research. Read current native state first; replace only with both native revision and block-hash guards. Preserve history and other works unchanged. Use supersession, retirement or invalidation rather than silent deletion. Installed Skills never rewrite themselves.
9. Apply actual corrections through canonical revision/invalidation. A corrected text or ownership attribution stales the claims that depend on it and their descendants; unrelated facts survive. Stored stale claims remain inspectable history and provide no current evidence. A hypothetical Stage 11 sensitivity run remains separate and does not apply a correction.
10. In a later source task, general HTI must independently identify the current source before activating matching work, edition or exemplar layers. Unidentified/candidate pages, same-author wrong-work pages, mismatched editions/exemplars and materially stale state cannot bootstrap activation from stored titles, manifests, locators or dossiers.

## Implementation over the accepted substrate

Use `hti_core.specialization_onboarding.begin(id, request, holding_report)` for a current task record. `identify` accepts the ordinary audited checkpoint/binding, an explicitly selected native registry, general bibliographic edition candidates and useful next evidence. It creates only licensed `specialization_core.new_manifest` layers, or extends the unique existing native record at that exact level/scope. Conflicting records require resolution. A reviewed identity rebind never revives stale research claims. `put` stores the exact independently evidenced general claim, field, its retained actual scope, current source references and explicit native dependency tokens. General research claims declare `onboarding_field` and exact `scope`; no specialization-origin claim is accepted. Claims with original wording or author-position purposes must pass the corresponding source/proposition gate. Historical translation remains its actual representation; it cannot establish original wording.

`manifest_view` is a view over native manifests/claims, not a second specialization schema. It shows unresolved fields, evidence ancestry, activation predicates, verification and revision history. `research_objects` projects the current general checkpoint and licensed witness records into the existing work-dossier/witness-registry schemas. Every witness has work scope, access status, source ancestry and an independence group; edges remain textual and reference registered endpoints. Argument, historical, cartographic, novelty and network records retain their respective existing validators and remain separate domains.

`reconcile` performs an actual correction with native identity reconciliation and work-scoped evidence anchors. Scope hashes prevent identically named source spans in another work from being touched. Current source/claim snapshots are rechecked; native dependency propagation follows only actual dependencies. Revalidation is a reviewed update, never automatic revival. Use native `core.revalidate_record` only with current independent identity evidence and then review affected claims separately.

`persist(create=True)` is explicit initialization, never discovery or replacement of unknown prior state. `persist(create=False)` reads the bound registry and uses guarded replacement; a failed/unavailable write has no success receipt. `retrieve` is an administrative native read with `activation_granted: false`. Native locators are opaque storage identifiers. Use the existing private account/namespace partition and injected `hti-claude-docs-bridge-1` host mapping; never hard-code account IDs or locator values. The accepted adapter requires CREATE/READ/REPLACE responses and full payload confirmation. Do not emulate unavailable native guards with unguarded writes.

The abstract bridge is an internal request/response contract, not a tool name or a packaged executable that must be discovered. A successful Docs guide establishes surface visibility only. If the concrete required schema cannot be loaded, permission is denied, the operation fails or its receipt cannot be verified, record that concrete limitation and preserve the honest unpersisted state and optional NON-NATIVE bundle. Host/tool names, ToolSearch syntax and bridge JSON are never required user input. Report established and unresolved identity levels, actual persistence/recovery/activation state, the complete recovery binding when needed, and useful next evidence. Complete native operations, receipt checks, binding retention and any exports before staging and the terminal helper.

Portable `export`/`import_bundle` reuse the existing integrity-, scope-, ancestry-, activation-rule- and revision-validated bundle workflow. This is explicit **NON-NATIVE** transfer. User action: export and retain the bundle; attach it in a later conversation and request import. Imported state cannot activate without independent current identity licensing. It does not demonstrate native recovery.

## Current publication and useful result

Save the current record as `<TASK_DIR>/hti-specialization-onboarding.json`. Open a fresh substantive publication for each onboarding update/correction in the exact owned task, keeping research continuity. Stage current inputs with `task_state.py stage-publication`. Add one `specialization_onboarding` checkpoint claim with `onboarding_id` and SHA-256 of `render(doc, checkpoint, integrity)`; include that exact summary in the existing final-response plan and complete through the accepted helper. The gate binds the current request, staged record and output. Any specialization facts quoted in addition to the summary still need the existing specialization context/use gate. No stale prior completion satisfies an update.

The summary states what is established, which edition/exemplar layers remain unresolved, what is actually persisted, what source evidence would help next, and exactly how to recover later. Do not request photos reflexively or promise persistence without confirmation.

## Validation boundary

Local adapter-contract simulation does not prove target-platform onboarding. Stage 12 requires a later actual-Claude user workflow on a previously unregistered work: report, identity, edition candidates, optional photographs, witnesses, manifest, Docs persistence, fresh top-level recovery with the documented binding, new evidence, correction/invalidation, later activation and wrong-work dormancy. That exact workflow remains unexecuted until Coordination authorizes it. No Stage 13 hardening is begun here.

## Recoverable evidence and corrections

New reviewed `put` operations append sealed GENERAL and SOURCE evidence history to the existing work-scoped anchors. SOURCE history retains the complete validated source-integrity registry, relevant reference and any existing proposition/ownership material. GENERAL history retains the exact research claim and its general evidence ancestry. The existing native envelope and explicit NON-NATIVE portable bundle carry this material without truncation. Historical source or general material never establishes current-source identity.

In a fresh conversation, recover the explicitly bound registry, independently identify the current source, bind the stable subject only after identification, and use the existing reviewed `core.revalidate_record` when required. Call `specialization_evidence.recover_claim(registry, record_id, claim_id)` for a current accumulated claim. It validates the historical evidence closure and returns `integrity`, `general_material`, and `activation_granted: false`. Pass that integrity and the independently established current checkpoint/binding to stock `core.read_claim`. Stage the validated source context in the exact current task's existing source-integrity substrate before quoting specialized facts through governed completion. Multiple conflicting source contexts require reviewed reconciliation using the existing source registry; do not silently replace current supplied-page evidence with recovered context.

`reconcile` checks only historical roots actually available in its supplied source/checkpoint context. An absent representation, span, proposition, claim or ancestor is unavailable, not changed. Its dependent source-backed claim remains non-consumable without the required context. An available root whose snapshot or evidence genuinely changes still stales its true descendants. Explicitly established removal/contradiction may use the existing canonical `core.mark` operation. Identity corrections/downgrades continue through the unchanged identity reconciliation.

Legacy registries without evidence history remain readable as administrative state. `LEGACY_EVIDENCE_CLOSURE_MISSING` means required context was never retained; it does not mean the source changed. Do not reconstruct material from IDs, hashes or stored claim prose. Authentic source material may be restored/reinspected through a governed update. `specialization_evidence.append` attaches matching validated material with a guarded append-only audit event; a changed root requires ordinary anchor correction and separately reviewed claim update. Prior stale/invalidated claims never revive merely through recovery.

Evidence/history may exceed a native block's capacity. A failed guarded native write remains unpersisted; do not shorten evidence, claim semantics or audit history. The existing portable export is an explicit NON-NATIVE alternative with complete closure. Retain and attach that validated bundle for later import; this does not demonstrate native persistence or autonomous discovery.

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

## Current accountable publication

The common `publication_contract` and response-plan digest in [output templates](output-templates.md) govern this feature's substantive output and selected-operation outcome. A retained result is not fulfillment of a new request. Publish selected current exact projections or reviewed current derivations; disclose a current PARTIAL/UNRESOLVED/BLOCKED reason when a selected operation cannot be completed. Preserve native source, ownership, uncertainty, identity and relation licenses. Unrequested operations remain optional. All research, source inspection, corrections, preparation and progress updates precede the committed response. Design R selects transport from exact UTF-8 bytes: DIRECT_STDOUT at or below 24,000 bytes emits the committed answer and stops with no later tool; READ_COMMITTED_FILE above that ceiling emits a short current-publication path/hash/byte-count stub, followed only by one exact Read with allow_large=true, exact relay and stop. No other post-stub tool, narration, editing or new publication is permitted. Later truthful recovery preserves the same commit and repeats its direct payload or bound stub, never scholarship.

The exact selected ONBOARD_SPECIALIZATION step, not a second request interpretation, governs this publication's onboarding summary. A selected summary binds the exact current request, existing independently licensed identity/storage/activation and exact output hash. Retained unselected onboarding stays historical and optional. A blocked prerequisite produces an honest task outcome, not fabricated holdings, identity or persistence success. Canonical specialization correction projections retain their existing exact renderer/profile and anti-circularity gates.
