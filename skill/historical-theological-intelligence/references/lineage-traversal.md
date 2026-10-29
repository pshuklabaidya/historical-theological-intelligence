# Bidirectional Lineage Traversal

Use this module only for an explicit backward, forward, or bidirectional lineage request, an explicit request to identify discontinuity, or an explicit request for bounded next-step historical research planning.

## Structured workflow

1. Resolve the requested anchor to exactly one validated Phase 5 Historical Relation Graph node. An anchor may resolve by graph-node ID, dossier ID, or proposition ID where unambiguous.
2. Choose `BACKWARD`, `FORWARD`, or `BIDIRECTIONAL` and a bounded maximum depth. Optional period bounds are diagnostic constraints, not claims about historical truth.
3. Traverse only active, validated Phase 5 edges according to the relation matrix below.
4. Preserve edge IDs, relation types, scope, confidence, Phase 4 uncertainty, evidence roots, unresolved alternatives, and direction.
5. Preserve branches, convergence, empty sides, graph gaps, cycle boundaries, and revival discontinuities.
6. Validate every path against the unchanged Historical Relation Graph before rendering it.
7. If requested, derive research-plan items only from structured gaps or unresolved links. Label them as research targets and require Phase 5 validation for any proposed edge.

## Relation-aware traversal

| Relation | Default path treatment | Direction | Safeguard |
|---|---|---|---|
| `DIRECT_QUOTATION` | genealogical lineage | antecedent to recipient | bounded scope remains visible |
| `DIRECT_DEPENDENCE` | genealogical lineage | antecedent to recipient | no transitive direct-dependence edge |
| `MEDIATED_DEPENDENCE` | genealogical lineage | antecedent to recipient | mediation channel or intermediary remains visible |
| `SHARED_SOURCE` | contextual shared ancestry | symmetric context | never recipient-to-recipient descent |
| `INHERITED_COMMONPLACE` | contextual tradition | recorded Phase 5 orientation | never forced into a particular-source lineage |
| `CONCEPTUAL_AFFINITY` | non-genealogical context | symmetric context | excluded from ancestry by default |
| `INDEPENDENT_CONVERGENCE` | non-genealogical context | symmetric context | excluded from ancestry |
| `RECEPTION` | historical engagement | antecedent to recipient | engagement is not generic dependence |
| `TRANSFORMATION` | historical engagement | antecedent to recipient | transformation metadata remains on the edge |
| `REVIVAL` | historical engagement with discontinuity | antecedent to recipient | preserve the discontinuous interval |
| `REJECTION` | historical engagement | antecedent to recipient | rejection is not generic descent |

Backward traversal follows directional edges from recipient to antecedent. Forward traversal follows them from antecedent to recipient. Bidirectional output retains both direction labels and never infers direction from display order.

## Gaps and uncertainty

`NO_ESTABLISHED_RELATION` means only that no eligible edge is present in the validated graph. It is not evidence of historical disappearance. Use positive disappearance or diminished-transmission labels only when evidence separately supports them.

Do not summarize a path as one scalar confidence. Keep every edge's qualitative confidence, every relevant Phase 4 uncertainty link, shared evidence roots, and unresolved alternatives visible. Multiple paths do not become independent corroboration merely because they are distinct routes.

## Determinism and termination

Bound traversal depth. Maintain a path-local visited-node set and stop before revisiting a node. Sort eligible neighbors by established year when available, historical-period order, relation type, edge ID, and node ID. Sort paths, gaps, branches, convergences, unresolved links, contextual relations, and plan items by stable IDs before serialization.

## Research planning boundary

A plan may request passage inspection, chronology and access verification, intermediary investigation, shared-root checking, or discrimination among unresolved relation types. It must not invent a named intermediary, rank immediate sources, create a transmission profile, or add an edge. Those tasks remain subject to Phase 5 licensing and future Phase 7 forensic adjudication.
