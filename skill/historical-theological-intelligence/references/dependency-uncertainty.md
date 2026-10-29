# Dependency-Sensitive Uncertainty

Use this layer only after a validated Argument Dossier and Proposition-Relation Graph exist. It derives qualitative consequences from recorded uncertainty roots without rewriting propositions or increasing the authority of source representations.

## Structured workflow

1. Record each uncertainty root with a stable ID, dossier ownership, typed origin, subject, rationale, provenance, and any existing evidence or uncertainty state.
2. Validate the root against an existing proposition, relation, representation, or competing interpretation.
3. Derive dependency arcs from the Phase 3 relation ontology.
4. Analyze the requested target proposition in the appropriate interpretation context.
5. Preserve every path, evidence root, root effect, support branch, and rationale in the result audit.
6. Expose the result only after the structured uncertainty audit passes.

## Public execution contract

Reuse the **existing validated dossier**, source registry, dossier ID, proposition IDs, relation IDs, representation IDs, and evidence roots. Do not infer a new dossier from prose. If the validated dossier remains in memory, pass its `ArgumentDossier` object directly. If it was saved through [argument-architecture.md](argument-architecture.md), reload `<TASK_DIR>/hti-validated-argument-dossier.json` and `<TASK_DIR>/hti-source-registry.json`, revalidate the saved `dossier` object against that registry, and check its saved `dossier_sha256`. Keep the matching work context; do not substitute a later dossier from another work.

Save the uncertainty request as `<TASK_DIR>/hti-dependency-uncertainty-request.json`. Its exact minimal shape is below. All identifiers and statements are **generic schema illustrations**; replace them with supported IDs and uncertainty from the validated dossier. Omit a root when the evidence does not warrant it; do not manufacture roots to fill the example.

```json
{
  "schema_version": "1",
  "dossier_id": "dossier-1",
  "uncertainty_roots": [
    {
      "root_id": "U1",
      "dossier_id": "dossier-1",
      "subject_kind": "PROPOSITION",
      "subject_id": "P1",
      "origin_type": "PAGE_READING",
      "rationale": "The premise depends on a reading that remains uncertain.",
      "provenance": {"origin": "supplied_page", "locator": "page-1"},
      "evidence_state": "PAGE_UNCERTAIN",
      "uncertainty": {"confidence": "possible", "evidence_state": "PAGE_UNCERTAIN"}
    }
  ],
  "targets": [
    {"target_proposition_id": "P2", "active_root_ids": ["U1"]}
  ]
}
```

Every root requires a unique stable `root_id`, the validated `dossier_id`, `subject_kind`, an existing in-scope `subject_id`, `origin_type`, a non-empty `rationale`, and a `provenance` object. Add `evidence_state` and qualitative `uncertainty` when applicable; the uncertainty object uses a qualitative `confidence` such as `possible`, with its evidence state when applicable. Valid subject kinds are `PROPOSITION` (proposition ID), `RELATION` (relation ID), `REPRESENTATION` (ID in the dossier's representation scope), and `INTERPRETATION` (competing interpretation ID). An optional root `interpretation_ids` is an ordered list of existing interpretation IDs; an interpretation subject is automatically scoped to its own interpretation when this field is omitted.

Choose the origin that actually describes the root: `PAGE_READING`, `OBSCURED_TEXT`, `RECONSTRUCTED_TEXT`, `TRANSLATION`, `LEXICAL`, `GRAMMATICAL`, `REPRESENTATION_LIMITATION`, `OCR`, `TRANSCRIPTION`, `BIBLIOGRAPHIC_IDENTITY`, `SOURCE_ATTRIBUTION`, `PROPOSITION_RECONSTRUCTION`, `PROPOSITION_CLASSIFICATION`, `RELATION_DIRECTION`, `COMPETING_INTERPRETATION`, or `OTHER`. These are uncertainty origins, not evidence classes or conclusion states. Do not add numerical probabilities or confidence scores.

`targets` is a non-empty list of objects with an existing `target_proposition_id`. The optional `interpretation_id` selects an existing interpretation for that target. Optional `active_root_ids` selects which recorded roots are active: omit it to analyze **all** roots, use `[]` for none, or list existing root IDs for a bounded scenario. Roots outside a selected interpretation remain inactive. A missing root ID or a target from another dossier fails validation.

From the Skill root, use the documented constructor and its audit-gated result. The saved dossier wrapper contains `dossier`, `dossier_sha256`, `status`, and `audit`; pass its inner `dossier` after validation, **not** the wrapper or a reconstructed prose summary:

```bash
python3 - <<'PY'
import json
from pathlib import Path
from scripts.hti_core.source_representation import RepresentationRegistry
from scripts.hti_core.argument_architecture import construct_argument_dossier
from scripts.hti_core.dependency_uncertainty import construct_dependency_uncertainty

registry_data = json.loads((Path(__import__('os').environ['HTI_STATE_DIR']) / 'hti-source-registry.json').read_text())
stored = json.loads((Path(__import__('os').environ['HTI_STATE_DIR']) / 'hti-validated-argument-dossier.json').read_text())
if stored.get('status') != 'validated' or stored.get('audit', {}).get('status') != 'PASS':
    raise ValueError('Argument Dossier has no passing validation audit')
registry = RepresentationRegistry.from_dict(registry_data)
validated_dossier = construct_argument_dossier(stored['dossier'], registry)
dossier = validated_dossier.dossier
if dossier.sha256() != stored.get('dossier_sha256'):
    raise ValueError('stored Argument Dossier hash does not match')
request = json.loads((Path(__import__('os').environ['HTI_STATE_DIR']) / 'hti-dependency-uncertainty-request.json').read_text())
validated = construct_dependency_uncertainty(request, dossier)
result = validated.to_dict()
(Path(__import__('os').environ['HTI_STATE_DIR']) / 'hti-validated-dependency-uncertainty.json').write_text(
    json.dumps(result, ensure_ascii=False, indent=2)
)
print('uncertainty audit:', result['audit']['status'])
print('result SHA-256:', result['result_sha256'])
for target in result['results']:
    print(target['target_proposition_id'], target['state'])
PY
```

If the constructor rejects a request, correct the indicated root, ownership, target, or evidence field and rerun the same public call. Do not render an unaudited replacement result. The documented request, saved dossier, and constructor are sufficient for routine execution; inspection of `scripts/hti_core/dependency_uncertainty.py` is unnecessary to discover schemas or semantics.

## Reading the validated result

In `<TASK_DIR>/hti-validated-dependency-uncertainty.json`, require `status: "validated"` and `audit.status: "PASS"`. The `results[]` entries report `target_proposition_id`, qualitative `state`, `active_root_ids`, `root_impacts`, `support_branches`, `surviving_independent_support`, and `audit_trail`. For each relevant `root_impacts[]`, report its `root_id`, `effect`, and `paths[]` where the path's `proposition_ids`, `relation_ids`, `effects`, and `aggregate_effect` establish how uncertainty reaches the target. Keep `IRRELEVANT` roots visible when the question calls for them. For `support_branches[]`, distinguish `secure` from `genuinely_independent`; check `evidence_roots`, `dependency_ancestry`, and `affected_root_ids` before describing separate support. Shared evidence roots prevent a claim of genuine independence even when there are two graphical branches. Record the audit status and `result_sha256`; explain the validated state in ordinary prose without claiming a proposition is false or turning a reconstructed reading into a visible one. Raw JSON and internal IDs need only be shown when useful to the user.

## Relation semantics

- `SUPPORTS` carries contributory uncertainty from source to target.
- `DEPENDS_ON`, `REQUIRES`, `PRESUPPOSES`, and `CONCLUDES_FROM` carry critical uncertainty from the required target premise to the dependent source proposition.
- `QUALIFIES`, `DISTINGUISHES`, and `INTERPRETS` carry scope-modifying uncertainty from source to target.
- `CONTRADICTS` and `DOES_NOT_SUPPORT` do not create positive dependency paths.
- `UNCLASSIFIED` relations produce unresolved dependency consequences rather than guessed semantics.

An unresolved relation remains unresolved. Relation direction is structural and must not be inferred from prose after the graph has been accepted.

## Result states

- `UNAFFECTED`: no active uncertainty reaches the target.
- `LOCAL_UNCERTAINTY`: uncertainty remains at the target without downstream propagation.
- `QUALIFIED`: uncertainty affects scope or interpretation.
- `WEAKENED`: a contributory branch is uncertain, or an independent secure branch prevents critical uncertainty from collapsing the target.
- `MATERIALLY_UNCERTAIN`: critical uncertainty reaches the target and no genuinely independent secure support survives.
- `UNRESOLVED`: dependency semantics are insufficient for a determinate effect.

These states are not truth values, probabilities, proposition types, evidence states, or relation types.

## Independence

Multiple paths or files do not prove independence. A secure support branch is genuinely independent only when it shares neither Phase 2 evidence roots nor critical dependency ancestry with the uncertain branch. OCR and transcription from one image, multiple translations from one source, and repeated derivatives of one representation remain dependent.

## Interpretations and cycles

Analyze competing interpretations separately. Interpretation-specific roots and edges do not contaminate another interpretation. Claims common to every viable interpretation may be summarized across those separate results without merging the interpretations.

Traversal enumerates bounded simple paths with per-path visited propositions. Permitted cycles therefore terminate and never create accumulating confidence or artificial independent support.

## Boundaries

Uncertainty propagation never promotes reconstructed content to direct observation, OCR to verified transcription, translation to original wording, or secondary quotation to primary evidence. It creates no Dynamic Witness Graph edge, Historical Relation Graph edge, lineage claim, transmission claim, reception claim, or confessional relation.
