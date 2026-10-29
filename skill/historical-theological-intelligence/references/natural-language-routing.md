# Natural-language routing

## Purpose

Map an ordinary request to the smallest ordered set of accepted HTI operations that can answer it. The route is inspectable control state. It is not historical, textual, bibliographic, conceptual, or doctrinal evidence.

Text-only and null-page inputs are first-class structured HTI routes. A pasted quotation, transcription, historical or modern translation, and scholarly edition can anchor an Argument Dossier without a page image, subject to their distinct representation permissions. A bare question such as `Where did the distinction between necessity of consequence and necessity of the consequent come from?` launches bounded source discovery, then binds verified passages to source representations, dossiers, and validated relations. The canonical checkpoint, response plan, and completion helper support `locus.page_id: null`; never decline them solely because no image or literal supplied-page span exists. The supplied text can provide its own span; a bare question provides a research target, not a verified passage. Preserve unresolved locators when research cannot establish them.

For a bare question, create the directory only for a new task (`python3 scripts/task_state.py new`); a linked substantive follow-up retains its exact directory. Select operations with this router, open the current publication as below before discovery, inspect sources within the requested scope, write `<TASK_DIR>/evidence-checkpoint.json` with `locus.page_id: null` and `locus.image_sha256: null`, write `<TASK_DIR>/final-response-plan.json`, stage current inputs with `python3 scripts/task_state.py stage-publication --state-dir "$HTI_STATE_DIR"`, and run `python3 scripts/complete_commentary_task.py --state-dir "$HTI_STATE_DIR"`. Use the same directory on Continue. Failed or unavailable source inspection leaves a relation or locator unresolved in the checkpoint; it never licenses direct dependence or a freeform findings report. Before helper success there is no substantive user-facing answer. On interruption return only `Structured completion is unfinished. Continue to resume from the preserved checkpoint.` After helper success follow only the publisher-selected Design R transport: direct exact stdout and stop, or its single bound Read then exact relay and stop.

## Linked task and current publication

Before scholarly research, use `task_state.py begin-publication --state-dir "$HTI_STATE_DIR" --route commentary --request "EXACT CURRENT SUBSTANTIVE REQUEST"` for a new task's first response or a new substantive response in an already linked task. Select `--route scholar` for Scholar View. A correction, addendum or source/related-work follow-up is itself a current publication, not an unstructured extension of the prior response. The owned task and research survive; the old completion becomes contained history.

For interruption of unfinished work, use `resume-publication` in the same directory, preserving its publication identity. After current checkpoint/plan or compact Scholar preparation, `stage-publication` binds those inputs to the current request and route. Finish all research before staging and final completion; new resource reads/searches require restaging. A previous receipt cannot satisfy the current publication. Resource access from completed state returns an actionable requirement to begin a fresh publication before payload.

A non-substantive clarification, acknowledgement or status/history inspection does not open a new scholarly publication or task. It cannot carry a substantive source finding. Once the requested substantive scope is clear, take the publication branch before research. Transport replay is restricted to the exact already validated current response, never a new request or postscript.

## Least sufficient operation set

- `Translate these pages.` selects ordinary translation only.
- `Give me scholar view.` selects the inherited `SCHOLARLY_TRANSLATE` operation. Scholar View includes diplomatic transcription, normalized Latin, complete translation, explicit uncertainty, independent witness comparison when accessible, relevant source verification, theological loci, and exegetical-method analysis. When external research is available and has not been declined, its research disposition permits comparator discovery and source verification; if no independent comparator can be inspected, degrade transparently rather than substituting the supplied page's own report of variants.
- `Translate this and identify the citation.` selects translation, then source verification.
- `Translate this and tell me what the argument is.` selects translation, then a bounded Argument Dossier.
- `Trace this argument backward.` selects backward lineage after the argument anchor is available.
- `How did Augustine reach this author?` selects historical-relation investigation and source-transmission analysis.
- `Compare these concepts, but do not make an influence claim.` selects conceptual comparison without genealogy.
- `Trace this locus through the Reformed confessions.` resolves the locus, then uses the Phase 9 trace.
- `Start with a modern argument and trace it backward.` selects a modern anchor and backward investigation; it does not require an early-modern Latin page.

Never activate every subsystem merely because it exists. Source language, script, or multilingual content invokes Phase 10 safeguards transparently and does not by itself change the substantive intent.

The translation-plus-argument route requires the native source representation and validated Argument Dossier described in [source-representations.md](source-representations.md) and [argument-architecture.md](argument-architecture.md). An informal argument summary is not execution of `BUILD_ARGUMENT_DOSSIER`. Render concise prose from the validated dossier and complete the translation response through the existing finalizer; do not activate later historical operations for this request.

## Structured plan

A route records:

- request reference;
- current anchor and context provenance;
- primary and additional intents;
- ordered operations and dependencies;
- direction and bounded scope;
- named entities with roles, not identity licenses;
- output depth and presentation modifiers;
- research disposition and negative constraints;
- ambiguity, clarification, and unresolved referents;
- non-disableable safeguards and audit rationale.

Validate the plan before execution. Reject unknown operations, cycles, missing required anchors, invalid directions, conflicting work contexts, later-phase operations, and any attempt to disable evidence safeguards.

## Context and ambiguity

Reuse a current argument, distinction, locus, passage, or source question only when it is unique within the current work. If two referents would lead to materially different analysis, ask one user-centered clarification. Do not mention phase numbers or internal implementation in ordinary clarification.

When a new work is supplied, bind subsequent follow-ups to that work. Never carry a prior work's identity, witness graph, dossier, historical edges, or claims into the new work.

## Presuppositions and partial completion

Question grammar never supplies evidence. Requests that presume copying, direct consultation, identity, influence, or contradiction route to the corresponding adjudication and may be supported, mediated, unresolved, or rejected.

Composite requests can partly succeed. Report each secure result and leave the unsupported operation unresolved. Do not replace an unresolved dependence question with conceptual similarity while presenting it as dependence.

## Presentation and research

`Briefly`, `in detail`, `show the Latin`, `table`, `citation-ready`, and `no commentary` affect rendering only. They do not weaken uncertainty or licensing. `Scholar view` is not merely a presentation modifier: it selects the defined scholarly-translation operation above. External research is used when a historical or verification question requires it and omitted when current supplied evidence is sufficient or the user declines it. Scholar View may use external research for its required witness-comparison and source-verification work when access is available; failure to locate an accessible comparator is a graceful-degradation result, not permission to treat the supplied page's internal variant discussion as an independent witness.

## Phase boundary

This router composes inherited operations and the two Stage 8 operations: RECONSTRUCT_INTERLOCUTOR and ANALYZE_PRESSURE_FIELD. Both require the current source-bound Argument Dossier. Ordinary translation remains unchanged. Stage 9 adds MAP_WHOLE_WORK, MAP_DEVELOPMENT and COMPARE_WORK_MAPS for explicitly requested cartography. Each requires validated lower-level dossiers. See [cartography](cartography.md) for corpus boundaries, significance, dates, confounds, asymmetries and current completion bindings. Stage 10 adds ASSESS_NOVELTY, ADJUDICATE_ORIGINALITY and AUDIT_NOVELTY_LEDGER only for requested or clearly implied novelty work. Explicit novelty opt-outs are honored. See [novelty](novelty.md). Stage 11 adds requested historical access networks and hypothetical sensitivity through the contract below. Stage 12 adds requested ONBOARD_SPECIALIZATION; see [onboarding](specialization-onboarding.md). See [historical explanation](historical-explanation.md) for the exact evidence and completion contract.


## Stage 11 historical access and sensitivity

`Could this author actually have had access to this source?`, `What historical route could have carried this argument?`, and `Does owning this book show that he used it?` request ASSESS_ACCESS_NETWORK. `How much does the dependence claim rely on this intermediary?`, `What happens if this source attribution is wrong?`, and `Which conclusions survive if this evidence is removed?` request TEST_HISTORICAL_SENSITIVITY. The dossier prerequisite supplies no historical evidence. Sensitivity additionally requires the actual explicit dependency record; do not construct guessed links to satisfy routing. Honor `no network analysis` and `no sensitivity analysis`. Translation alone routes identically to the inherited ordinary operation.

Stage 11 outputs use current infrastructure/scenario files and fresh substantive publication state. The terminal helper remains authoritative. New-work onboarding is a separately requested Stage 12 operation.


Stage 12 ordinary intents include acquiring a book, adding a repeatedly used work, improving a specialization and recovering a specialized library from an exact registry binding. `Recover my specialized library from this exact registry binding` selects the existing `ONBOARD_SPECIALIZATION` operation. The recovery phrase is limited to the specialized library; bare `recover`, damaged-text recovery, argument recovery and deleted-file recovery do not select onboarding. `Do not recover my specialized library` and equivalent explicit recovery opt-outs exclude that operation. Routing grants no identity, persistence or activation claim. Exact-binding administrative retrieval remains non-activating; current-source identity must be independently licensed before the existing activation gate. No page or photograph is required to begin a pending holding report. Identity and facts still require independent evidence. Explicit onboarding opt-outs are honored. Use the current onboarding file and the existing fresh publication/completion helper.

## Current accountable publication

The common `publication_contract` and response-plan digest in [output templates](output-templates.md) govern this feature's substantive output and selected-operation outcome. A retained result is not fulfillment of a new request. Publish selected current exact projections or reviewed current derivations; disclose a current PARTIAL/UNRESOLVED/BLOCKED reason when a selected operation cannot be completed. Preserve native source, ownership, uncertainty, identity and relation licenses. Unrequested operations remain optional. All research, source inspection, corrections, preparation and progress updates precede the committed response. Design R selects transport from exact UTF-8 bytes: DIRECT_STDOUT at or below 24,000 bytes emits the committed answer and stops with no later tool; READ_COMMITTED_FILE above that ceiling emits a short current-publication path/hash/byte-count stub, followed only by one exact Read with allow_large=true, exact relay and stop. No other post-stub tool, narration, editing or new publication is permitted. Later truthful recovery preserves the same commit and repeats its direct payload or bound stub, never scholarship.

Review the existing router's OperationID steps against the request and bind them before research. Keep its directions, dependencies and mandatory safeguards unchanged. The chosen plan is immutable within this publication; a changed request opens a fresh publication. Outcomes use COMPLETED/PARTIAL/UNRESOLVED/BLOCKED, with BLOCKED referencing selected prerequisites. Ordinary translation selects its own operation and safeguards only. Claude chooses the plan internally from ordinary intent. A source question can anchor active discovery before identity; an unresolved outcome preserves the specific decision question and actual effort.
