# Hidden controversy and polemical pressure

Use only for requested interlocutor or pressure analysis. Ordinary translation remains ordinary translation. Requests such as `Who is this argument responding to?`, `What controversy is behind this?`, `Is this aimed at a particular theologian?`, and `What pressures make this distinction important here?` require no manual mode.

The classifications are EXPLICIT_TARGET, HISTORICALLY_PROBABLE_TARGET, POSSIBLE_INTERLOCUTOR, CONTROVERSY_BACKGROUND, LATER_ANALOGY and UNRESOLVED. Confidence is independently secure, probable, possible or unresolved. Oppositional resemblance is not proof of an opponent. A contemporary name does not establish an immediate source. A later analogy does not establish historical targeting or reception. Similarity, contrast, chronology, common vocabulary, shared Scripture and common third sources alone cannot license a named target. Mere explicit mention is not an explicit target: inspect the local denial, reply, or directed address establishing the name's role. Names inside an opponent's quotation do not establish the anchor author's target. Retain the reported ownership and require separate author-owned targeting evidence.

## Existing substrate

Construct the current native Argument Dossier, PRG and source-integrity argument extension first. Retain voice ownership, representation ancestry, coverage and source verification. Use a `kind: CLAIM`, `purpose: REPRESENTED_ARGUMENT` consumer in the existing `argument_integrity.consumers` list. Its dependencies include the anchor propositions and every materially relevant proposition or existing consumer. Each dependency uses its actual current snapshot. Add the `historical_explanation` payload below. This is a typed explanatory claim on the existing consumer architecture, not a second graph.

Do not infer strong original terminology from a translation. A historical translation can support the represented sense and, where its passage actually directs a response, an explicitly represented target. DISTINCTIVE_TERMINOLOGY needs separately licensed exact original wording. Register external inspected passages and their actual derivation roots in the current source-integrity registry. External comparators are evidence representations within this task's work context, not claims that those comparators belong to the anchor work. Never copy a wrong-work specialization into the current registry. Edition or exemplar licenses do not license interlocutor identity. A specialization may contribute a source-linked, already licensed proposition through the existing specialization contract; its mere availability cannot be target evidence.

## Payload schema

Every payload has exactly these common fields:

- `schema_version: hti-historical-explanation-1`
- `kind: INTERLOCUTOR` or `PRESSURE_FIELD`
- `work_id`: exact current work
- `anchor_proposition_ids`: nonempty existing author-owned proposition IDs for named targeting; unresolved/contextual records may retain ambiguous ownership with visible uncertainty
- `confidence`: qualitative confidence, separate from classification
- `chronology`: existing ChronologyAssessment with state, rationale, provenance and optional antecedent_year/recipient_year
- `access`: existing AccessAssessment with state, rationale, provenance and optional channel
- `evidence`, `counterevidence`, `alternatives`, `limitations`: lists, empty when warranted
- `local_form`: the particular distinctions or objection structure explained, with no unlicensed response, influence or causal-origin claim

An INTERLOCUTOR also has exactly `classification` and `target` (name/controversy label, or null for unresolved). A PRESSURE_FIELD instead has exactly `facets`.

Each evidence or counterevidence object has exactly `id`, `factor`, `source_refs`, `assessment`, `target`, `effect`. `source_refs` are nonempty existing ArgumentIntegrity references: representation_id, nonempty span_ids, and current parent_snapshot. `target` identifies the nominated person/group for target-specific support, otherwise null. Evidence effects are SUPPORTS or CONTEXT. Counterevidence effects are DEFEATS, WEAKENS, UNRESOLVED or IRRELEVANT. Do not omit known counterevidence. WEAKENS or UNRESOLVED limits confidence to possible/unresolved. DEFEATS prevents current targeting and leaves an unresolved outcome or a retained revalidation-required hypothesis.

Factors:

EXPLICIT_TARGET_NAME, DOCUMENTED_LOCAL_ENGAGEMENT, DENIED_PROPOSITION_SEQUENCE, DISTINCTIVE_TERMINOLOGY, OBJECTION_SEQUENCE, DOCUMENTED_CONTACT, HISTORICAL_AVAILABILITY, LOCAL_RELEVANCE, CONTEMPORARY_DISPUTE, INSTITUTIONAL_SETTING, TREATMENT_ELSEWHERE, DOCTRINAL_SIMILARITY, DOCTRINAL_OPPOSITION, CHRONOLOGY_ONLY, SHARED_VOCABULARY, SHARED_BIBLICAL_SOURCE, COMMONPLACE, COMMON_THIRD_SOURCE, LATER_RESEMBLANCE, COUNTEREVIDENCE.

Factors label actual evidentiary roles, not stronger licenses awarded by selecting a name. An EXPLICIT_TARGET_NAME must occur in the cited span and its directed-target role must be inspected. A probable unnamed target needs documented local engagement, or a discriminating textual/argumentative feature together with documented contact. Both must support the same nominated target. Possible interlocutors retain a discriminating local link and plausible availability; resemblance alone remains analogy or unresolved. Explicit, probable and possible historical targets require compatible chronology and established/plausible access. Access may be to a documented position/public controversy, not necessarily personal contact. Impossible chronology or inaccessible targets remain unresolved, rejected through counterevidence, or later analogy as appropriate.

Every alternative has exactly `label`, `classification`, `evidence_ids`, `rationale`. Classifications here remain POSSIBLE_INTERLOCUTOR, UNRESOLVED, CONTROVERSY_BACKGROUND or LATER_ANALOGY. Each alternative's supporting references remain auditable. Multiple current hypotheses may also be represented as separate consumers with separate dependencies; do not manufacture a winner.

A pressure facet has exactly `id`, `type`, `text`, `claim`, `evidence_ids`, `relevance_evidence_ids`. Types: DISPUTED_PROPOSITION, AVAILABLE_POSITION, INSTITUTION, ACTIVE_CONTROVERSY, AUTHORITY, CHARACTERISTIC_TERMINOLOGY, CONFESSIONAL_PRESSURE, LOCAL_CIRCUMSTANCE. Claims: HISTORICAL_EXISTENCE, ENVIRONMENT_SALIENCE, ARGUMENT_RELEVANCE. Every included facet requires inspected HISTORICAL_AVAILABILITY evidence and a separately identified LOCAL_RELEVANCE role. Keep the field bounded to the current argument; omit irrelevant contemporary disputes. Background relevance never licenses direct response, named-target identity, dependence, influence or causal origin. A separately warranted target hypothesis or historical edge must carry any such distinct claim.

## Binding and correction

During preparation retain a new consumer as REVALIDATION_REQUIRED, so provisional snapshots do not assert current truth. Use the existing `snapshot`, `proposition-snapshot` and `consumer-snapshot` interfaces to obtain current bindings after actual review. Then mark CURRENT and validate. Stale source/proposition/consumer dependencies block current exposure. A material correction to attribution, dating, translation, source identity or speaker evidence requires reviewing affected hypotheses, binding corrected source evidence, updating classification/confidence/counterevidence and renewing dependencies. Merely changing status is not revalidation. A correction to an unrelated source span leaves an unaffected hypothesis current.

Save the existing Historical Relation Graph as `<TASK_DIR>/hti-historical-graph.json`. Add optional `explanation_bindings`: a list of objects with exactly `consumer_id`, `anchor_node_ids`, `snapshot`. Nodes are existing graph proposition nodes matching the consumer's anchor propositions and work. The snapshot is the existing consumer_snapshot. Historical edges and their ontology remain unchanged. The graph constructor's fourth argument is the current IntegrityRegistry; the third is the existing map of matching DependencyUncertaintyAnalysis objects. Each explained anchor requires its actual current uncertainty analysis. A non-UNAFFECTED upstream result limits confidence to possible/unresolved with a visible limitation. Save the current analysis request as `<TASK_DIR>/hti-dependency-uncertainty-request.json`; use `uncertainty_roots: []` when no material root is supported, never omit an actual one to promote confidence.

From the Skill root, use one import namespace and the exact owned task directory:

```python
import json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path("scripts").resolve()))
import task_state
from source_integrity import IntegrityRegistry
from hti_core.source_representation import RepresentationRegistry
from hti_core.argument_architecture import ArgumentDossier
from hti_core.dependency_uncertainty import DependencyUncertaintyAnalysis
from hti_core.historical_relations import construct_historical_relation_graph

directory = task_state.resolve(os.environ["HTI_STATE_DIR"])
load = lambda name: json.loads((directory / name).read_text())
integrity = IntegrityRegistry(load("source-integrity.json"))
dossier_json = load("hti-argument-dossier.json")
registry_json = load("hti-source-registry.json")
dossier = integrity.argument.validate_native(dossier_json, registry_json)
analysis = DependencyUncertaintyAnalysis.from_dict(
    load("hti-dependency-uncertainty-request.json"), dossier)
validated = construct_historical_relation_graph(
    load("hti-historical-graph.json"), [dossier],
    {dossier.dossier_id: analysis}, integrity)
print(validated.audit.status)
```

The native dossier/registry and graph must be the current task's supplied files. This validation precedes staging and canonical completion; a graph audit alone cannot complete the publication.

Run `python3 scripts/source_integrity.py explanation-render --state-dir "$HTI_STATE_DIR"` to obtain classification-preserving text for current records. Put that exact text into the canonical response plan. Every record has a checkpoint claim with `claim_type: historical_explanation`, `consumer_id`, `explanation_sha256` (SHA-256 of the exact UTF-8 rendered string), and the existing evidence/entity bindings. Register any named referents in checkpoint entities and bind them to the claim. Preserve the renderer's target classification, confidence, alternatives, counterevidence and limitations. Both completion routes verify those claims and current graph bindings. Retained REVALIDATION_REQUIRED records cannot publish as current claims.

Use the current task/publication contract. Stage after all substantive evidence and preparation; graph and uncertainty files join source integrity, dossier, registry and plan in the current publication-bound inputs. Complete through the selected commentary/Scholar helper and return its exact terminal output. Neither a constructor pass nor a previous publication receipt completes the current request.

## Current accountable publication

The common `publication_contract` and response-plan digest in [output templates](output-templates.md) govern this feature's substantive output and selected-operation outcome. A retained result is not fulfillment of a new request. Publish selected current exact projections or reviewed current derivations; disclose a current PARTIAL/UNRESOLVED/BLOCKED reason when a selected operation cannot be completed. Preserve native source, ownership, uncertainty, identity and relation licenses. Unrequested operations remain optional. All research, source inspection, corrections, preparation and progress updates precede the committed response. Design R selects transport from exact UTF-8 bytes: DIRECT_STDOUT at or below 24,000 bytes emits the committed answer and stops with no later tool; READ_COMMITTED_FILE above that ceiling emits a short current-publication path/hash/byte-count stub, followed only by one exact Read with allow_large=true, exact relay and stop. No other post-stub tool, narration, editing or new publication is permitted. Later truthful recovery preserves the same commit and repeats its direct payload or bound stub, never scholarship.

Select exact current consumer IDs in scope.domain_outputs and bind native explanation output hashes. Other retained consumers remain in history. A prose explanation outside those exact outputs requires reviewed derivation and cannot strengthen classification or confidence through wording. Native graph/uncertainty/consumer payload licenses remain unchanged.
