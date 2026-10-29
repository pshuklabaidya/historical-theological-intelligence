# Commentary native authoring

Use this path for commentary research, identification, argument, reception,
pressure-field, cartography and pastoral requests. Scholar View retains its
existing compact Scholar adapter. Ordinary user requests remain natural language.

Use the bounded transaction path for complex commentary research. It removes mechanical publication assembly from the model while leaving all scholarship, evidence judgments, review and kernel publication unchanged.

For a new source-bound task, bind the explicit supplied representation before composition:

```bash
python3 scripts/native_authoring.py bootstrap-interface
python3 scripts/native_authoring.py bootstrap --state-dir "$HTI_STATE_DIR" --payload BOOTSTRAP.json
python3 scripts/task_state.py compose --state-dir "$HTI_STATE_DIR"
```

`bootstrap` only binds an explicitly authored `hti-source-integrity-1` object to the owned task so natural-language routing has a resolved anchor. It never establishes historical work identity from the isolation token.

After reading the exact composition manifest and recording the actual selection review, perform the scholarly research and author one compact transaction payload. Inspect the public payload contract rather than implementation source:

```bash
python3 scripts/native_authoring.py transaction-interface
python3 scripts/native_authoring.py transaction --state-dir "$HTI_STATE_DIR" --payload TRANSACTION.json
```

The transaction accepts explicit scholarly constructor inputs - source representation registry, argument dossier, optional dependency-uncertainty request, historical relation graph, and optional reception-analysis inputs - plus source integrity, evidence, claims, anchors, research plan, entities, reviewed prose, outcomes, section order and scope. It runs the existing HTI native constructors, writes their validated native state, and mechanically computes current publication bindings, source/proposition/relation snapshots, canonical source assertions, derivation hashes, review bindings, source/domain output bindings and section wiring before the unchanged full nonpublishing preflight. A successful result is `READY_UNCOMMITTED` and names the unchanged kernel publisher as the next command.

The transaction must not choose propositions, relations, confidence, identity, outcomes, evidence, limitations or review attestations. Every derivation requires an explicitly supplied separate-pass review record. Do not provide prebuilt `hti-*.json` native files: provide the scholarly constructor inputs under `native`, and let the helper serialize them through the existing constructors and validators. A failed transaction returns `NEEDS_CORRECTION` with read-only diagnostics and commits no response or receipt.

The older `initialize` / hand-filled bundle path remains available for narrow debugging and simple fixtures, but complex reception and pressure-field work should not hand-assemble publication JSON or inspect helper source merely to discover field shapes.

Fill these fields as research proceeds:

- `checkpoint`: evidence, claims, selected claims, identity hypotheses, page
  and reading-risk state. All existing evidence and critical-reading rules apply.
- `plan`: identity selection, typed non-current entities, translation text if
  requested, and mode. For translation use `ordinary_translation` and the full
  English text. For research use `research`, `translation: null` and scope
  `translation_requirement: NONE`.
- `contract`: current assertions, actual separately reviewed derivations, native
  result references, anchors, discoveries, research plan and exact current scope.
  The constructor already binds task, publication, request and operation plan.
- `sections`: `[{"kind":"research","assertion_ids":["A1","A2"]}]` becomes
  canonical nested blocks/segments. Use an allowed fixed heading. Substantive
  wording belongs inside governed assertions, including confidence and notes.

Native dossier/graph/map/consumer state remains in the canonical task files
specified by the selected capability references. Use their documented native
constructors. Do not fabricate empty successful domain results. Required state
is visible in `compose` and the registry; only selected successful operations
require their native result. A failed lookup does not abort independent work.

Mechanical Python interfaces are available without implementation inspection:

```python
import sys
sys.path.insert(0, 'scripts')
from native_authoring import source_ref, projection, review_packet
# registry is the current source_integrity.IntegrityRegistry.
# Explicitly select representation/span/purpose after inspecting the source.
ref = source_ref(registry, 'SOURCE-ID', ['SPAN-ID'], 'REPRESENTED_ARGUMENT')
# projection(...) accepts the actual text, parents, purpose, source_layer,
# ownership, scope, status, facets, qualifications and limitations.
# CANONICAL text must equal its licensed parent projection exactly.
# A synthesis instead needs a DERIVATION and a genuine separate-pass review.
unsigned = review_packet(actual_derivation, current_publication)
```

`review_packet` supplies only binding hashes. Its reviewer is null, review flags
are false and attestation is empty. Perform the actual separate review of the
exact payload and parents, record qualifications, conflicts and material changes,
then sign that packet. It is not a review. Changed parents or prose require a
new actual review; no automatic snapshot refresh licenses a changed assertion.
The helper never supplies a scholarly attestation, identity, evidence or outcome.

Every selected step needs an explicit COMPLETED, PARTIAL, UNRESOLVED or BLOCKED
outcome. Use the exact generated step ID. COMPLETED/PARTIAL need actual native
or source results of the correct kind. An incomplete result needs a specific
reason visible in a selected UNRESOLVED/PROVISIONAL assertion. BLOCKED names
the incomplete selected prerequisite. Preserve serious research effort and
accessible consequential leads; incomplete states do not substitute for it.
Set `contract.terminal.preparation_reviewed: true` only after actual preparation
review. The remaining terminal policy stays unchanged.

## Reception and pressure-field convergence

For these two operations, obtain the public field/signature guide and run the
read-only diagnostic as soon as a bounded bundle exists, and after a failed
preparation. These commands replace implementation-source searches:

```bash
python3 scripts/native_authoring.py interface
python3 scripts/native_authoring.py diagnose --state-dir "$HTI_STATE_DIR"
```

`diagnose` reports compact-bundle JSON locations, assertion IDs, unlicensed
named tokens, current-work aliases, source bindings, missing body coverage
scopes, stale parents and native-state obligations together. It changes nothing
and never means READY. Correct the listed obligations in one focused author
pass; `sections` accepts only `kind` and `assertion_ids`, not nested renderer
blocks. The interface gives the exact shape and helper signatures.

Keep established identity unchanged when an alias is rejected. Current-work
names belong to Identification; use an unambiguous unnamed reference in analysis
and separately review that changed passage. A genuinely non-current name needs
an independently evidenced `plan.entities` entry and its ID on the assertion.
Never register the current work/author as non-current or rename its identity to
pass a check. Quoted source wording and independently licensed names are distinct.
Research may select analytical passages without a full source appendix, while
retaining every actual native result and complete source accounting. Remove a
source binding from publication selection only when that source passage is no
longer selected for literal display; do not remove its evidence or ancestry.
Translation coverage requirements do not change.

For output-binding or coverage findings use the public shapes:

```bash
python3 scripts/source_integrity.py interface
python3 scripts/source_integrity.py argument-interface
```

A binding names an actual registered representation and `rendered_source_layer`
(or `translation` only for an actual full translation). A supplied root used by
bindings/propositions needs an inventoried body scope. Assign each span its true
coverage disposition; registration itself establishes no represented result.
Preserve source classes, limits and ancestry. After changes to prose or parents,
use `review_packet` only for unsigned bindings, perform an actual separate review,
and sign it. The helper never chooses evidence, signs, or assigns outcomes.

After the explicit corrections and current review, run `prepare` and, only on
READY_UNCOMMITTED, the unchanged kernel publisher shown by `next_command`.
No command here replaces full preparation or allows a substantive fallback.
If the diagnostic cannot resolve a requirement within the bounded correction
allowance, author the warranted incomplete outcome with its specific reviewed
reason and actual result refs. Keep the selected dependency closure and every
valid retained result. Do not fake native objects to satisfy a status.

For a selected `ANALYZE_RECEPTION` or `ANALYZE_PRESSURE_FIELD`, keep a lawful
terminal publication within the current execution budget. Initialize the bundle
early as above. After inspecting the anchor and before optional source expansion,
author the supported bounded result and the specific unresolved questions,
review their exact assertions, and run the full `prepare` path. This is an early
nonpublishing check, not permission to stop research without serious effort.
Update this same current publication as material evidence arrives.

Bind each actual source layer immediately: keep `source-integrity.json`
`output_bindings` and the contract's selected `scope.source_bindings` current.
Use `rendered_source_layer` for an actual represented source layer and
`translation` only for an actual full translation. Preserve complete retained
source accounting separately from the exact passages selected for publication.
A registered source requires an output binding even when only selected spans
are published. Do not leave these requirements until the final preparation.
Keep marginal labels, uncertain spans and semantic risks faithful to their
source. Unresolved readings cannot support strong claims.

After any native-construction, source-access or full-preflight failure, identify
the exact failed obligation and its effect on the requested conclusion before
another attempt. Make at most two focused corrective passes before a mandatory
convergence review, even when a later pass exposes a different gate. A new error
does not restart that allowance. Repair only from already inspected evidence
and documented interfaces; repeated implementation searches, native rebuilds
or optional source expansion must not consume the publication reserve. Reserve
at least the final quarter of an exposed remaining tool/turn budget for current
review, full preparation and kernel publication. If no reliable counter is
exposed, use the two-pass boundary; do not invent a remaining-turn count.

At convergence review, retain every validated result and actual research
attempt. Adjudicate every selected operation explicitly: COMPLETED only for an
actual valid complete result; PARTIAL only with its required valid native/source
result and limitations; UNRESOLVED when its question or native result cannot yet
be established; BLOCKED only by a named incomplete selected prerequisite. Keep
the full selected dependency closure. Put the exact incomplete reason in a
selected current UNRESOLVED/PROVISIONAL assertion with its existing separately
reviewed derivation, and retain unresolved discoveries and research-plan stopping
reasons. Scope the reason to the actual missing evidence, uncertain reading or
validation obligation. Execution exhaustion establishes no historical conclusion.
No helper may assign these statuses, fabricate state, or sign a review for you.

When the remaining budget cannot support further lawful native repair or source
acquisition, stop optional expansion and author that truthful bounded terminal
result. Do not claim an invalid native object as a result or delete its failed
attempt. Preserve failed construction separately in the owned task, retaining
all source observations and ancestry in canonical source accounting. Include
only valid current claims and projections in publication, without promoting,
relabeling or concealing uncertainty. Fix mechanical bindings from actual current
sources. Retain independently established identity and installed readiness.
Run `prepare`, then the unchanged `complete_commentary_task.py` kernel publisher.
Every existing validator still applies. A blocked prerequisite does not require
an invented successful object. A successful receipt certifies publication;
operation outcomes still carry their actual scholarly completion status.

If a lawful prepared result still cannot pass the existing gates, preserve the
failure and use the existing structured-completion interruption boundary. Never
emit a freeform substitute or force a success receipt. After a successful commit,
apply the unchanged transport-and-stop contract immediately.

## Identity and installed readiness

Identity evidence must satisfy both the general evidence audit and independent
specialization licensing. A directly inspected visible title may be recorded
with `origin: general_evidence`, its actual `evidence_class`, a discriminating
`kind`, `identity_admissible: true`, exact provenance, and
`ancestor_evidence_ids: []` when genuinely a root. Derived evidence lists all
actual ancestor IDs; every ancestor must independently meet the licensing
contract. `general_evidence` describes evidence ownership, not a historical
source type. Keep observation type and provenance in their own fields. Never
relabel specialization, persistence, uninspected metadata, or resemblance as
independent general identity evidence. A user suggestion is not an established
bibliographic premise.

An asserted selected identity claim needs `origin: general_identity`, the
matching `subject_id`, its actual `claim_type` (work_identity, edition_identity
or exemplar_identity), and the independently licensed evidence IDs. Work identity
alone licenses neither edition nor exemplar. If evidence does not license an
identity, retain the corresponding uncertain state and a useful bounded result.
Do not promote or demote identity merely to clear a gate.

After current research and bundle authoring:

```bash
python3 scripts/native_authoring.py prepare --state-dir "$HTI_STATE_DIR"
```

This assembles the canonical checkpoint and plan, verifies actual review and
outcome structure, derives installed readiness from current independent identity,
stages the publication and runs the full nonpublishing commentary preflight:
renderer, source-integrity/native dispatch, specialization, image inspection,
composition and captured-input stability. It returns READY_UNCOMMITTED only
when these gates pass. It writes no committed response or completion receipt
and prints no scholarly answer. Correct the identified input directly, then
prepare again. No scratch rendering script or implementation-source search is
needed for routine preparation.

For already canonical state, prepare installed readiness using
`specialization_resources.py prepare`, stage normally and run
`native_authoring.py check --state-dir "$HTI_STATE_DIR"`. This checks without
replacing canonical inputs. Preserve any already licensed specialization use.

After READY_UNCOMMITTED, complete without further research:

```bash
python3 scripts/complete_commentary_task.py --state-dir "$HTI_STATE_DIR"
```

Only that existing kernel publisher commits. It repeats every authoritative gate
against the actual current inputs. A preflight result is neither publication nor
a reusable waiver. Research, input correction or resource access requires current
preparation and staging again. An existing commit cannot be prepared again.

## Selection and transport boundaries

Multiple authors, passages or works do not themselves request comparison.
Developmental cartography selects MAP_DEVELOPMENT and its prerequisites, not
COMPARE_WORK_MAPS. Add comparison only for actual comparative intent. Keep all
transitive dependencies and genuine composite requests. When the requested
development cannot be established, publish that uncertainty instead of silently
changing the operation.

The publisher's 24,000-byte threshold, immutable commit and one-Read branch stay
fixed. After commit, no substantive narration is allowed. If the host interrupts
the final relay or injects an output-token-limit continuation, do not resume
mid-body, explain the fixture or describe the commit. Return only:

`Delivery is unfinished. Continue to recover the preserved response.`

No additional tool is allowed in that interrupted delivery turn. A later user
Continue uses the existing verified same-commit transport recovery. Host exact
relay capacity is not established by a successful native commit.
