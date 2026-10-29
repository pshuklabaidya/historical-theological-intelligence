# Argument Architecture

Use this reference when the user requests argument decomposition, an Argument Dossier, a proposition graph, or equivalent argument analysis, including `Translate this and tell me what the argument is.` Ordinary translation alone remains on the ordinary translation route.

## Bounded translation-plus-argument procedure

For `Translate this and tell me what the argument is.`, translate the readable supplied page under the ordinary evidence rules, then construct a source representation and a native Argument Dossier before writing the argument explanation. Read [source-representations.md](source-representations.md) and its page-image registry shape. Keep the current work `UNIDENTIFIED` unless independent admissible evidence licenses a name. Treat this as `TRANSLATE` followed by `BUILD_ARGUMENT_DOSSIER`; do not substitute an informal argument summary for dossier construction or activate later historical subsystems.

Save the adapted source registry as `<TASK_DIR>/hti-source-registry.json` and a dossier as `<TASK_DIR>/hti-argument-dossier.json`. The following example shows the required minimal structure with two supported propositions and one supported internal logical relation. Its generic content and identifiers are schema illustrations, not claims about the supplied page. Replace or omit propositions and relations according to the actual source; one proposition with `relations: []` is valid if no relation is supported. Preserve unresolved readings and do not turn a translated sense into an exact Latin claim.

```json
{
  "schema_version": "1",
  "dossier_id": "dossier-1",
  "argument_id": "argument-1",
  "work_id": "WORK-ID",
  "anchor_representation_id": "page-1",
  "representation_scope": ["page-1"],
  "source_representation_type": "PAGE_IMAGE",
  "source_identifications": [],
  "propositions": [
    {
      "proposition_id": "P1", "dossier_id": "dossier-1",
      "content": "A bounded premise stated in the visible passage.",
      "proposition_type": "THEOLOGICAL_PREMISE", "argument_functions": ["PREMISE"],
      "expression_mode": "DIRECTLY_STATED", "evidence_state": "PAGE_UNCERTAIN",
      "uncertainty": {"confidence": "possible", "evidence_state": "PAGE_UNCERTAIN"},
      "provenance": {"origin": "supplied_page", "locator": "page-1"},
      "source_links": [{"representation_id": "page-1", "representation_claim": "REPRESENTED_ARGUMENT",
        "source_span": "relevant visible lines", "evidence_state": "PAGE_UNCERTAIN",
        "uncertainty": {"confidence": "possible", "evidence_state": "PAGE_UNCERTAIN"},
        "provenance": {"origin": "supplied_page", "locator": "page-1"}}]
    },
    {
      "proposition_id": "P2", "dossier_id": "dossier-1",
      "content": "A bounded conclusion stated in the visible passage.",
      "proposition_type": "CONCLUSION", "argument_functions": ["FINAL_CONCLUSION"],
      "expression_mode": "DIRECTLY_STATED", "evidence_state": "PAGE_UNCERTAIN",
      "uncertainty": {"confidence": "possible", "evidence_state": "PAGE_UNCERTAIN"},
      "provenance": {"origin": "supplied_page", "locator": "page-1"},
      "source_links": [{"representation_id": "page-1", "representation_claim": "REPRESENTED_ARGUMENT",
        "source_span": "relevant visible lines", "evidence_state": "PAGE_UNCERTAIN",
        "uncertainty": {"confidence": "possible", "evidence_state": "PAGE_UNCERTAIN"},
        "provenance": {"origin": "supplied_page", "locator": "page-1"}}]
    }
  ],
  "relations": [{"relation_id": "R1", "dossier_id": "dossier-1",
    "relation_type": "SUPPORTS", "source_proposition_id": "P1", "target_proposition_id": "P2",
    "status": "PROVISIONAL", "construction_basis": "Visible connection in the supplied passage",
    "uncertainty": {"confidence": "possible", "evidence_state": "PAGE_UNCERTAIN"},
    "provenance": {"origin": "supplied_page", "locator": "page-1"}}],
  "interpretations": [], "counterevidence": [],
  "unresolved_questions": [{"question_id": "Q1", "dossier_id": "dossier-1",
    "question_type": "SOURCE_SPAN", "question": "Does the uncertain reading affect this premise?",
    "subject_ids": ["P1"], "provenance": {"origin": "supplied_page", "locator": "page-1"}}],
  "audit_trail": [
    {"audit_id": "A1", "dossier_id": "dossier-1", "subject_id": "P1",
      "decision_type": "PROPOSITION_CONSTRUCTION", "rationale": "Bounded visible premise",
      "provenance": {"origin": "supplied_page", "locator": "page-1"}},
    {"audit_id": "A2", "dossier_id": "dossier-1", "subject_id": "P2",
      "decision_type": "PROPOSITION_CONSTRUCTION", "rationale": "Bounded visible conclusion",
      "provenance": {"origin": "supplied_page", "locator": "page-1"}},
    {"audit_id": "A3", "dossier_id": "dossier-1", "subject_id": "R1",
      "decision_type": "RELATION_CONSTRUCTION", "rationale": "Visible support relation",
      "provenance": {"origin": "supplied_page", "locator": "page-1"}}
  ]
}
```

Run this public construction interface from the Skill root, without reading implementation source:

```bash
python3 - <<'PY'
import json
from pathlib import Path
from scripts.hti_core.source_representation import RepresentationRegistry
from scripts.hti_core.argument_architecture import construct_argument_dossier

registry = RepresentationRegistry.from_dict(json.loads((Path(__import__('os').environ['HTI_STATE_DIR']) / 'hti-source-registry.json').read_text()))
candidate = json.loads((Path(__import__('os').environ['HTI_STATE_DIR']) / 'hti-argument-dossier.json').read_text())
validated = construct_argument_dossier(candidate, registry)
(Path(__import__('os').environ['HTI_STATE_DIR']) / 'hti-validated-argument-dossier.json').write_text(json.dumps(validated.to_dict(), ensure_ascii=False, indent=2))
print('validated Argument Dossier:', validated.dossier.sha256())
PY
```

If construction fails, correct the specific schema, license, provenance, uncertainty, or graph error in the structured input and run the same interface again. Only a successful construction licenses the argument explanation. Condense the validated propositions, their functions, supported relations, and material unresolved questions into a concise `notes` block in the final response plan; run `python3 scripts/complete_commentary_task.py --state-dir "$HTI_STATE_DIR"` for the complete translation-plus-argument response. Keep dossier JSON internal unless requested. Never append an unaudited substitute summary after a failed constructor or finalizer.

## Start from a licensed representation

Construct an Argument Dossier only from representations already validated by `source_representation.py`. Every proposition source link must name an in-scope representation ID, the exact Phase 2 representation claim it needs, provenance, a source span or locator when available, and evidence state or qualitative uncertainty when applicable.

The requested representation claim must be `ALLOWED`. A dossier cannot upgrade OCR to verified text, translation to original wording, transcription to page-physical evidence, a secondary quotation to primary evidence, or an edition to a supplied exemplar.

## Decompose arguments, not sentences

A sentence may contain several propositions. One proposition may span several sentences. Rhetorical or background material need not become a proposition. Separate an embedded authority quotation from the author's claim about it. Mark structurally necessary unstated material `RECONSTRUCTED`; never present it as directly stated or visibly observed.

For each proposition record its semantic type separately from its argument function. Use `UNCLASSIFIED` when the available evidence does not support a narrower classification.

## Internal logical graph

Use only the Phase 3 logical relations: `SUPPORTS`, `DEPENDS_ON`, `QUALIFIES`, `DISTINGUISHES`, `CONTRADICTS`, `INTERPRETS`, `PRESUPPOSES`, `CONCLUDES_FROM`, `REQUIRES`, `DOES_NOT_SUPPORT`, or `UNCLASSIFIED`.

Every edge must remain inside one dossier and must cite its construction basis and provenance. Validate unique node and edge IDs and require existing endpoints. The graph need not be a tree or a DAG.

These relations express internal argument architecture. They are not textual-witness relations and do not establish quotation, dependence, mediation, reception, transformation, revival, rejection, or any other historical genealogy.

## Alternatives and unresolved structure

Keep competing interpretations as separate records with their own proposition and relation membership, rationale, provenance, counterevidence, and unresolved discriminators. A provisional preference requires an explicit rationale. Do not overwrite one decomposition with another and do not require a winner.

Retain counterevidence and unresolved questions structurally. Phase 3 may record evidence state, qualitative uncertainty, and dependencies, but it must not calculate downstream confidence, apply weakest-branch rules, compensate with independent support, or generate numerical probabilities.

## Validate before exposure

Pass the complete structured candidate through `construct_argument_dossier`. A malformed dossier, unlicensed source claim, dangling endpoint, cross-dossier reference, missing audit basis, or later-phase relation fails closed. Use deterministic serialization only after validation succeeds.

## Source-bound ownership and completeness

Before canonical completion, fill the [proposition integrity](proposition-integrity.md) extension of source-integrity.json. Preserve explicit owner/speaker, discourse role, source spans, body coverage and current dependency hashes. Bind this native dossier and every logical relation through the extension. A legacy constructor pass alone does not establish current ownership or complete source coverage.
