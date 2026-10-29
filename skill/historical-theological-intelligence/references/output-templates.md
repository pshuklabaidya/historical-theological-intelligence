# Output Templates

## Construction rule

Complete the structured response plan from `resources/templates/final-response-plan.json`, save the checkpoint as `<TASK_DIR>/evidence-checkpoint.json`, save the plan as `<TASK_DIR>/final-response-plan.json`, and run `python3 scripts/complete_commentary_task.py --state-dir "$HTI_STATE_DIR"`. Use the successful rendered text it prints. The renderer supplies the Identification line and derives current-work identity spans from the recorded identity state and evidence.

The response plan uses these controls. A research-only publication uses a research mode with `translation: null`; the common scope determines current visibility. The examples below require corresponding current contract records before publication:

- `identity.visible_claim_id`: either `null` or one evidence-licensed `work_identity` claim. `UNIDENTIFIED` cannot expose a named claim.
- `translation.text`: the complete translated page content. It is rendered as `translated_page_content` and remains subject to the ordinary page-evidence and high-risk-reading rules.
- `sections[].kind`: choose a fixed renderer heading such as `textual_uncertainties`, `notes`, `diplomatic_latin`, `normalized_latin`, `witness_comparison`, `source_notes`, `rare_book_notes`, `citation`, `pastoral_study`, `exegetical_method`, `theological_loci`, or `research`.
- Each section must nest blocks and segments exactly as `sections[].blocks[].segments[]`, for example `{"kind":"notes","blocks":[{"segments":[{"kind":"assertion_projection","assertion_id":"note-reviewed"}]}]}`. Do not put `segments` directly under a section.
- `segments[].kind: text`: finite nonassertive punctuation/spacing only. Substantive prose uses `assertion_projection` with a selected current assertion ID. Routine labels inside that governed passage retain inherited named-referent rules.
- Standalone `entity` segments are refused. Register typed non-current entities and bind their IDs through the enclosing assertion's `entity_ids` (or its native claim's entity fields). A licensed name does not license a sentence.
- `term` segments cannot publish substantive terminology; technical terms belong to the governed passage. Only finite nonassertive tokens remain unbound.
- `segments[].kind: page_text`: quoted or transcribed page content outside the main translation; supply evidence IDs.
- `segments[].kind: linebreak`: explicit line break.

Genuine named historical persons, historical sources, external comparators, bibliographic records, and other evidence-bearing non-current referents belong in `entities` and enter governed projections through bound entity IDs. Routine Scripture references, language names, grammatical labels, textual-tradition labels, and short quoted wording may remain inside governed analytical projections when they are not being used to establish identity, dependence, bibliography, or another evidence-bearing historical claim. A display containing a recorded current-work hypothesis or claim alias cannot enter through a non-current entity; resolve the identity or leave that ambiguous name out of analytical prose. `bibliographic_candidate` may refer only to an external work with a distinct `target_work_id`; it cannot exempt a candidate for the supplied page.

## Named non-current referents

If the finalizer identifies genuine named non-current referents, it reports the raw-name problems together so they can be fixed in one structured edit rather than one tool cycle per name. Retain each meaningful name that matters to the response. Register it with evidence in `entities`, bind it in the current assertion's `entity_ids`, and render the entire reviewed passage using `assertion_projection`. Resolve display markers before binding the exact reviewed payload. Do not paraphrase away a historical or theological name merely to clear the error. For an optional note that adds little value, deleting the note is preferable to constructing unnecessary entity apparatus. Each entity needs `entity_id`, `role`, `scope`, `display`, `current_work_referent: false`, and non-empty `evidence_ids` that exist in the checkpoint. The evidence must support the stated referent and role. These generic shape examples require replacement with actual evidence-backed names and IDs:

```json
{
  "entities": [
    {"entity_id":"person-1","role":"historical_name","scope":"historical_source","display":"Example Scholar","current_work_referent":false,"evidence_ids":["E-person"]},
    {"entity_id":"source-1","role":"historical_source","scope":"historical_source","display":"Example Treatise","current_work_referent":false,"evidence_ids":["E-source"]},
    {"entity_id":"scripture-1","role":"scripture_reference","scope":"scripture","display":"Genesis 1:1","current_work_referent":false,"evidence_ids":["E-scripture"]},
    {"entity_id":"place-1","role":"other_named_entity","scope":"other_noncurrent","display":"Example City","current_work_referent":false,"evidence_ids":["E-place"]}
  ],
  "sections": [{"kind":"notes","blocks":[{"segments":[
    {"kind":"assertion_projection","assertion_id":"note-reviewed"}
  ]}]}]
}
```

`historical_name` permits `page_content`, `historical_source`, or `other_noncurrent` when evidence warrants that exact role. `historical_source` requires `historical_source`; `scripture_reference` requires `scripture`; `other_named_entity` requires `other_noncurrent`. An `external_comparator` or `external_bibliographic_record` additionally requires a distinct non-current `target_work_id`. A `bibliographic_candidate` also requires `candidate_scope: "external_work"`. A recorded current-work identity alias is never made non-current merely by setting `current_work_referent: false`, assigning a scope, or citing evidence; it stays outside these examples. Only the renderer-owned Identification may expose a licensed current-work claim.

## Default translation

The renderer produces:

**Identification:** generated entirely from audited identity state.

**Translation:** complete polished English; use unobtrusive brackets only where meaning depends on reconstruction. Do not silently restore physically obscured Latin in transcription layers.

**Textual uncertainties:** only consequential readings, each with visible reading or lacuna, proposed resolution, and effect.

**Notes:** a few useful Scripture, source, linguistic, exegetical, or historical notes.

**Confidence and identity status:** overall confidence plus any material limitation.

If no visible current-work claim is licensed, leave `identity.visible_claim_id` null. The renderer reports either `Work unidentified from the present evidence` or, when the state is `WORK_CANDIDATE`, that candidate evidence remains unresolved without naming a private candidate.

## Scholar view

Scholar View is the inherited scholarly-translation route, not ordinary translation with extra freeform prose. For a new full translation keep `mode: ordinary_translation`, put the complete English rendering in `translation.text`, and use the fixed section kinds for the scholarly apparatus. The usual section set is `rare_book_notes` for a bounded page description, `diplomatic_latin`, `normalized_latin`, `textual_uncertainties`, `witness_comparison`, `source_notes`, `theological_loci`, and `exegetical_method`; use `notes` only when it adds material value. Do not pad sections with empty findings.

Witness comparison requires an independently inspected comparator witness. Register the comparator before using it, record it as `other_witness` or `historical_translation` evidence with a distinct independence group, inspect the comparator passage, and report the supplied-page reading, comparator reading, and any substantive effect. The supplied page's own statement that another reading exists is page evidence, not an independent witness comparison. When no independent comparator is accessible, state that limitation and omit or explicitly qualify the comparison rather than manufacturing one.

When external research is available and not declined, attempt comparator discovery and relevant proposition-level source verification before finalizing Scholar View. One inaccessible source or witness does not abort the task. A catalog, OCR hit, contents page, index, or snippet is only a lead; inspect the comparator passage itself before claiming a substantive textual relationship.

For actual image-based diplomatic Latin or a glyph-level s/f claim, complete and validate the long-s checklist before response completion; preserve `ſ`, `f`, and `s` in the diplomatic layer and label normalization. For every blocked transcription region, carry its typed page state into `output.transcription_spans`; present any completion separately with `RECONSTRUCTS`. Routine Scholar View construction should use this reference, `resources/templates/evidence-checkpoint.json`, `resources/templates/final-response-plan.json`, and the documented long-s commands. Validator and finalizer source remain available for genuinely unclear diagnostics, but routine schema discovery should not require reading their implementation.

Reserve tool budget for structured completion. Optional notes, extra image derivatives, and nonessential source work are subordinate to writing the checkpoint and response plan and obtaining helper success. If the turn stops before helper success, the only permitted assistant response is `Structured completion is unfinished. Continue to resume from the preserved checkpoint.`

## Citation-ready

Give citation, identification basis, edition/exemplar caveat, stable witness links, and a compact audit trail for disputed readings. Current-work names still enter through the renderer-owned identity field rather than custom citation prose.

## Scholar View compact production interface

Read [Scholar output](../capabilities/textual/scholar-output.md) in full for this route.

## Current accountable publication

The common `publication_contract` and response-plan digest in [output templates](output-templates.md) govern this feature's substantive output and selected-operation outcome. A retained result is not fulfillment of a new request. Publish selected current exact projections or reviewed current derivations; disclose a current PARTIAL/UNRESOLVED/BLOCKED reason when a selected operation cannot be completed. Preserve native source, ownership, uncertainty, identity and relation licenses. Unrequested operations remain optional. All research, source inspection, corrections, preparation and progress updates precede the committed response. Design R selects transport from exact UTF-8 bytes: DIRECT_STDOUT at or below 24,000 bytes emits the committed answer and stops with no later tool; READ_COMMITTED_FILE above that ceiling emits a short current-publication path/hash/byte-count stub, followed only by one exact Read with allow_large=true, exact relay and stop. No other post-stub tool, narration, editing or new publication is permitted. Later truthful recovery preserves the same commit and repeats its direct payload or bound stub, never scholarship.

## Internal publication-contract authoring

Use the shipped checkpoint/plan/compact templates. Blank bindings and `preparation_reviewed: false` are placeholders, never valid licenses. Do research and scholarly review before declaring preparation complete. The user supplies natural-language intent; Claude authors the following internal state.

1. Open the publication. Review the existing router's plan and serialize a selection file with `operation_plan` and `selection_review`. The plan retains existing request_text, operations, anchor_id and mandatory safeguards. Each step retains step_id, existing operation, depends_on, anchor_id, direction and phase_owner. The review contains reviewer (CLAUDE or HUMAN), exact request_sha256, selection_reviewed: true. `task_state.py select-operations --selection FILE --state-dir "$HTI_STATE_DIR"` binds that selection once, before research. A changed request opens a fresh publication.
2. Copy task_directory, publication_id and request_sha256 from current publication state into publication_contract, set its actual work_id, and hash the selected operation_plan as operation_plan_sha256. This hash and all object snapshots use sorted-key, compact, literal UTF-8 JSON (`hti_core.hashing.sha256_json`); exact prose hashes use UTF-8 SHA-256 without normalization. No hash refresh replaces actual review.
3. Register assertion, derivation, anchor, discovery and plan records as needed. Empty arrays are appropriate for an ordinary source-only translation, provided its selected operation and source accounting are fulfilled. Do not activate unrelated features or invent evidence to fill a template.
4. Bind scope and terminal intent, hash the complete contract into plan.publication_contract_sha256, then stage. The final helper checks actual current source/native parents and exact output. Complete all preparation before that helper. Set delivery to DESIGN_R_PUBLISHER_SELECTED, success_continuation to RELAY_COMMITTED_RESPONSE_AND_STOP and post_success_actions to ["ONE_BOUND_READ_IF_READ_COMMITTED_FILE"]. This declares policy only; the trusted publisher selects actual transport. Truthful later transport recovery preserves the same current commit.

### Parent references

Every reference has kind, id, snapshot. Permitted kinds and extra fields:

| Kind | Current owner and snapshot | Extra fields |
|---|---|---|
| EVIDENCE | Existing checkpoint evidence record; canonical object hash | none |
| CLAIM | Existing audited native/identity/high-risk/specialization claim; canonical object hash | none |
| SOURCE_SPAN | Actual IntegrityRegistry representation; parent_snapshot(id, span_ids) | span_ids, existing purpose |
| PROPOSITION | Actual native dossier plus ownership registry; proposition_snapshot(id) | none |
| PRG_RELATION | Validated native logical relation; canonical native relation hash | none |
| HRG_RELATION | Current licensed active historical edge; canonical native edge hash | none |
| CONSUMER | Existing current argument consumer; consumer_snapshot(id) | none |
| DOMAIN_OUTPUT | Exact native current output UTF-8 hash | domain |
| QUESTION | Current owned anchor object hash; unresolved use only | none |
| SOURCE_STATUS | Validated checkpoint foreign_language_tokens object hash; generated summary | none |
| NATIVE_PLAN | Existing exported ResearchPlanItem object hash; not evidence | file, JSON pointer |

Native plan files are existing graph/dossier/uncertainty inputs. Domain names are cartography, novelty, historical_explanation, historical_infrastructure, historical_sensitivity, specialization_onboarding. Only independently validated source/comparator evidence licenses inspection. A locator, title, query, download or intended search universe grants no coverage or dating.

Native lineage, transmission, reception and confessional operation results can use an existing checkpoint claim with claim_type `native_operation_result`, existing OperationID in operation, native_input and the exact protected native API result in value. Source completion reconstructs/validates the typed result against actual current native inputs. A reviewed scholarly passage may then derive from its CLAIM reference. This wrapper is publication accountability for existing operations, not a parallel operation ontology. It does not grant identity or create a graph edge. Partial historical work can retain a current typed relation and explicit remaining gaps; informal prose alone does not complete a native operation.

### Assertions and reviewed passages

An assertion has id, form (CANONICAL, DERIVATION or UNRESOLVED), projection, projection_sha256, status (SECURE, SUPPORTED, PROVISIONAL or UNRESOLVED), currentness: CURRENT, purpose, source_layer, ownership, scope, facets, qualifiers, limitations, parents, optional claim_id, optional derivation_id and optional entity_ids. Canonical form has exactly one current parent and exact canonical text; it may not rewrite that parent's payload. A reviewed derivation or unresolved assertion points to its derivation_id and repeats the exact reviewed projection, parents, purpose, source_layer, ownership, scope, facets, qualifiers, limitations, status and currentness. `{{assertion:ID}}` selects an entire bounded passage in compact authoring. Canonical plans use `{kind: assertion_projection, assertion_id: ID}`. Legacy claim_text must equal the governed projection and have an unambiguous matching claim_id. Specialization_projection retains its exact profile and canonical correction projection. Assertions cannot be emitted twice outside their projection.

A derivation has the shared assertion payload fields, id, positive revision, counterevidence references, uncertainty_inheritance and review. Review fields: reviewer (CLAUDE or HUMAN), distinct_pass: true, publication_id, request_sha256, payload_sha256 (canonical derivation without review), parents_sha256, purpose, retained_qualifications: true, source_ownership_fidelity: true, material_changes, unresolved_conflicts, attestation. These record actual distinct-pass review of the complete bounded passage, including negation, modality, speaker, qualifications and scope. Changed payload or parents requires a new reviewed revision. The adapter never generates a review attestation. Counterevidence and correction are explicit; a contrary reformulation is not a faithful canonical summary. An unresolved question parent cannot license a positive claim.

Declared status may not exceed its current licensed parents. Declared chronology, relation and other facets require explicit matching licensed native/inspected facets, never a date guessed from a locator. Evidence `verified_facets` are usable only with actual inspected passage and proposition_found. Code checks declared structure and licenses, not historical or theological truth. False scholarly attestation remains model error. Fluent scholarship is permitted through a coherent bounded passage rather than sentence-by-sentence objects. A licensed entity supports its name, not an independent surrounding assertion. Names remain subject to inherited role/identity gates.

Nonassertive renderer-owned text is limited to fixed headings, labels, punctuation and whitespace. Arbitrary caller headings, confidence sentences, technical terms, captions and connective claims must be projections. Literal source text uses existing page/source-layer permissions and complete body accounting. Source-status summaries are renderer-owned projections of validated source state, not fake propositions. Internal IDs and review bureaucracy normally stay out of the scholarly answer.

### Current operation outcomes

Every selected step has one outcome with id equal to step_id, status, result_refs, assertion_ids, plan_item_ids, reason, blocked_by and limitations. Allowed terminal states: COMPLETED, PARTIAL, UNRESOLVED, BLOCKED. COMPLETED/PARTIAL need actual current result references of the operation's proper native/source kind; selected projections and task-relevant limitations remain visible. Incomplete states need a specific reason. BLOCKED references selected prerequisite IDs with incomplete outcomes. NOT_RUN is nonterminal and rejected. A complete honest answer receipt can include incomplete research outcomes. Unrequested operations stay optional.

A consequential accessible source must receive actual reasonable effort/inspection or a specific legitimate incomplete reason. Incomplete status is not a shortcut around the user's serious research question. Connect materially dependent outcomes to the relevant plan_item_ids; do not hide unadjudicated blockers behind COMPLETED. Prose alone does not count as native dossier, graph, map, comparator, identity or persistence execution.

### Bounded anchors, discoveries and plans

Anchor fields: id, task_directory, work_id (isolation token, not established identity), kind (PAGE/PASSAGE/ARGUMENT/PROPOSITION/SOURCE_QUESTION), question, dimension, source_refs, proposition_refs, source_form, language, identity_state, identity_claim_ids, limitations. Non-question anchors require actual source references; argument/proposition anchors require native propositions. Identity bindings reference independently licensed selected claims only. No anchor grants author/work/edition/exemplar identity, whole-work scope, chronology, originality, dependence, exact original wording or earliest occurrence.

Discovery fields: id, locator, provenance, anchor_id, plan_item_id, materiality, conclusion_effect, access_status, attempts, inspection_status, inspection, disposition, reason, comparator_ref. Qualitative materiality includes DECISION_CHANGING when appropriate; code does not rank relevance. Access status: UNKNOWN/ACCESSIBLE/ACQUIRED/INACCESSIBLE. Inspection status: LEAD/INSPECTED/INACCESSIBLE. Attempts record route/outcome/provenance. Inspection requires actual content_ref, relevant_passage and inspection_outcome. Download stays LEAD until the relevant content is inspected. Disposition: OPEN/VERIFIED/REJECTED/UNRESOLVED; rejection of an uninspected locator is not rejection of an inspected historical parallel. An inaccessible record needs actual attempt and reason. Uninspected records have no inspection/comparator, verified outcome, native searched unit, negative coverage or chronology/genealogy license. New access evidence can reopen a lead while preserving attempts.

Research-plan fields reuse the native ResearchPlanItem concepts: id, target_question, anchor_id, uncertain_question, why_material, possible_conclusion_effect, evidence_needed, discriminating_test, qualitative priority, discovery_ids, access_attempts, inspection_outcomes, conclusion_effect, completion_state, stopping_reason, provenance, optional native_plan_ref. Imported native items retain current snapshots and no graph-fact license. Planned conclusions are not published findings. The plan makes Claude's source judgment auditable; it imposes no relevance score, source/search/tool quota or endless-search requirement. Contextual research and broad historical fields remain useful. Failed access leaves dependent work incomplete while independent research can continue.

### Retained substrate and current scope

Scope fields: mode (FULL/DELTA), assertion_ids, source_bindings, domain_outputs, outcome_ids, retained, translation_requirement (NONE/FULL/CORRECTION), required_source_bindings. Selected IDs are current and exact; required source bindings are included in current source selection. Literal source text and translation match current selected canonical projections. No retained source coverage or historical result is deleted to pass visibility checks.

Retained entries have publication_id, receipt_sha256, response_sha256 and current source_refs. They bind an actual successful prior publication in this same owned task and actual current source state. A DELTA requires such retained binding. Prior source material is reusable, not a new selected-operation result. A research follow-up can omit the old translation. A new translation requires FULL complete requested readable source and gap accounting; a material correction requires CORRECTION affected content plus a governed correction account and dependency revalidation. A correction does not require repeating unrelated unchanged material. Essential current parents are staged. A changed source/proposition invalidates affected projections and derivations, never repairs them through automatic hash refresh.

Completed publication turnover preserves its input-bound checkpoint, plan and source-integrity bytes in the existing owned publication history. Retained source references must match historical and current span snapshots. A changed span is new/corrected material requiring review and selected correction; unchanged independent spans may remain retained. Older receipts without a saved substrate may prove retention only when their recorded source-integrity hash equals the unchanged current bytes; never manufacture a historical snapshot. These archives confer no current identity or evidence license.

A native ResearchPlanItem exported by a verified TRACE_LINEAGE claim may be linked through NATIVE_PLAN file `evidence-checkpoint.json`, pointer `/claims/N/value/research_plan/N`. The resolver reconstructs that typed native result before accepting the item snapshot. This links the existing planner without editing its graph or treating a plan as evidence. Native plans retain `established_graph_fact: false` and `creates_historical_edge: false`.

## Scholar View from supplied text

Read [Scholar output](../capabilities/textual/scholar-output.md) in full for representation-aware Scholar preparation.

Use the additive [commentary native-authoring helper](native-authoring.md) for mechanical binding and full nonpublishing preflight. It preserves all native constructors, actual review and kernel publication. Prepare installed readiness before staging; a renderer preview alone does not validate readiness, source coverage or native completion.
