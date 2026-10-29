# Historical Relation Graph

Use this module only when the task explicitly asks for a historical relation among arguments or argument-components, or when a historical-relation claim is necessary to answer the task.

## Locked relation types

- `DIRECT_QUOTATION` - bounded quotation or reproduction supported at the asserted scope.
- `DIRECT_DEPENDENCE` - direct dependence supported by chronology, possible access, and discriminating evidence.
- `MEDIATED_DEPENDENCE` - dependence through an explicit intermediary or mediating channel.
- `SHARED_SOURCE` - two recipients derive relevant material from a third source without creating recipient-to-recipient dependence.
- `INHERITED_COMMONPLACE` - a widely transmitted formulation, distinction, or pattern that does not discriminate one particular source.
- `CONCEPTUAL_AFFINITY` - substantive argumentative correspondence without a genealogy claim.
- `INDEPENDENT_CONVERGENCE` - positively supported independent arrival at a similar position.
- `RECEPTION` - demonstrable later engagement with earlier material.
- `TRANSFORMATION` - demonstrable reception plus a change in form, function, scope, configuration, or doctrinal role.
- `REVIVAL` - demonstrable recovery or renewal after relevant discontinuity.
- `REJECTION` - demonstrable engagement with and rejection of earlier material.

Relation type answers what kind of relation is claimed. Qualitative confidence answers how securely the claim is supported. Never change one to encode the other. Never use a numerical probability.

## Structured construction

1. Validate each endpoint as a reference to an accepted Phase 3 dossier, argument-component, or proposition.
2. Record relation scope as phrase, proposition, argument-component, argument, or unresolved.
3. Record positive evidence, discriminating features, counterevidence, evidence roots, chronology, access, provenance, and audit rationale.
4. Preserve unresolved alternative relation types instead of forcing a winner.
5. Attach relevant Phase 4 uncertainty through validated future-consumer views. Keep irrelevant uncertainty explicitly irrelevant.
6. Validate relation-specific minimum evidence.
7. Serialize only the validated Historical Relation Graph result.

For an active `PHRASE` or `PROPOSITION` edge, both endpoints must name existing Phase 3 propositions. Bind positive or discriminating historical evidence to each endpoint's **own recorded proposition source span**. On an item in `positive_evidence` or `discriminating_features`, `endpoint_spans` is a list of `{ "node_id": "...", "representation_id": "...", "source_span": ... }` objects; `source_span` must reproduce an exact `source_links[].source_span` value of the proposition named by that endpoint, and `representation_id` must match that same source link. A single evidence item may bind to multiple relevant source spans for an argument component. Evidence elsewhere on the same page, in the same representation, or under the same evidence root is insufficient. If no validated proposition represents the historical feature, leave the relation unestablished rather than inventing a new proposition or repurposing an unrelated one.

For an active `DIRECT_QUOTATION` at `PHRASE` or `PROPOSITION` scope, a `QUOTATION_MATCH` positive evidence item requires `matched_text`, and its `endpoint_spans` must bind **both** endpoint nodes. Two valid source-link forms need different checks:

- A string `source_span` containing `matched_text`, or a structured `source_span` with an explicit `text` value containing it, can verify the phrase directly. A string is not inherently a locator. The phrase must occur in the recorded span text at both endpoints.
- A string without `matched_text`, or a structured span with only `locator`, can serve as a **locator**, not a transcription. For each such endpoint, record `observation_locator` in its evidence binding. It must identify that exact recorded span locator. The validated proposition's `content` must itself explicitly record the matched phrase, and the source link must uniquely identify that proposition among the dossier's propositions. A statement in historical-evidence prose alone cannot stand in for this proposition-level record. If the quotation or proposition membership cannot be established from this typed inspected evidence, leave the active claim unlicensed. If the proposition paraphrases or translates the phrase without recording its original wording, refine its source link or proposition in a separate scholarly step before claiming an active quotation.

The `QUOTATION_MATCH` item's `evidence_roots` must equal the union of evidence roots of the endpoint source links selected by its bindings. A root appearing in only one endpoint, or an unrelated extra root, cannot license two-sided quotation correspondence. `OCR_LOCATOR` cannot stand in for inspected quotation text in either source-link form. A common evidence root does not prove independent witnesses. These generic evidence fields illustrate a literal-span case, not a claim about a supplied source:

An active quotation naming a `PROPOSITION` node also needs the same span bindings if a broader scope was asserted. Widening scope does not turn evidence elsewhere on the page into evidence for the named proposition.

```json
{
  "evidence_id": "H1",
  "kind": "QUOTATION_MATCH",
  "inspection_level": "PRIMARY_PASSAGE",
  "description": "The same inspected phrase appears within both recorded proposition spans.",
  "evidence_roots": ["source-root", "recipient-root"],
  "provenance": {"origin": "inspected_passages", "locator": "bounded passages"},
  "matched_text": "sample phrase",
  "endpoint_spans": [
    {"node_id": "source-node", "representation_id": "source-image",
     "source_span": {"text": "The source contains sample phrase here."}},
    {"node_id": "recipient-node", "representation_id": "recipient-image",
     "source_span": {"text": "The recipient repeats sample phrase here."}}
  ]
}
```

The two `source_span` objects above must already belong to the respective validated dossier source links; inserting them only in historical evidence cannot create a new endpoint or amend a Phase 3 proposition. Relation scope `ARGUMENT_COMPONENT` or `ARGUMENT` retains its broader documented behavior and may draw on several proposition spans where the accepted argument component supports the asserted relation. An uncertain locator or missing endpoint remains a candidate or unresolved claim; do not mark it `SUPPORTED` or `ESTABLISHED` by borrowing a different proposition's span.

For a **locator** case, use the same endpoint bindings with a recorded `source_span` such as `"opening lines"` and add `"observation_locator": "opening lines"` to that endpoint binding. The asserted `matched_text` must come from actual inspection of the specified passages, with the corresponding inspection level and evidence roots. The locator does not become a transcription, verified original wording, another witness, an identified edition, or evidence of dependence beyond the narrow edge. Do not add a fictitious `text` field to the source link. When two propositions use the same representation and locator, including one string form and one `{"locator": "opening lines"}` form, that location is shared even though the objects differ. A structured span with both `text` and `locator` also counts as occupying that locator when another proposition asserts a locator-based quotation there. A literal-text endpoint that contains the quotation retains its literal-text check. The only permitted disambiguation of a shared endpoint uses an already recorded **distinct source-link provenance** for the named proposition: include its exact `source_link_provenance` object and use that source link's specific `provenance.locator` as `observation_locator`. That specific locator must differ from the shared span locator, and the selected proposition's `content` must explicitly contain `matched_text` even when the shared span has a `text` field. If the candidate links' provenance is identical, has no specific locator, or does not select exactly one proposition, the active quotation fails closed. A page-wide provenance locator is insufficient to distinguish two propositions. Never create or revise Phase 3 provenance merely to make an active edge pass.

Candidate discovery signals such as machine similarity, embedding similarity, n-gram overlap, keywords, thematic similarity, generic agreement, shared biblical text, chronology alone, or failure to find a source cannot establish an active historical edge.

## Direction and scope

Directional relations use antecedent or source as `source_node_id` and recipient or descendant as `target_node_id`. `SHARED_SOURCE`, `CONCEPTUAL_AFFINITY`, and `INDEPENDENT_CONVERGENCE` use canonical lexical endpoint order because they are symmetric at this graph level.

Impossible chronology rejects an active directional claim. Compatible chronology and plausible access remain necessary conditions where applicable, not proof. A direct quotation remains limited to its supported phrase, proposition, component, or argument scope and does not establish broader dependence automatically.

## Evidence safeguards

- Direct quotation requires quotation evidence.
- Direct dependence requires discriminating correspondence, not ordinary agreement.
- Mediated dependence retains its intermediary or channel.
- Shared source identifies the third source and does not create an edge between recipients.
- Inherited commonplace requires evidence of broad transmission.
- Conceptual affinity requires substantive correspondence and withholds genealogy.
- Independent convergence requires positive independence evidence and cannot rest on a failed search.
- Reception requires historical engagement.
- Transformation requires engagement plus demonstrated change.
- Revival requires engagement plus demonstrated recovery after discontinuity.
- Rejection requires engagement plus explicit rejection, not contradiction alone.

Repeated derivatives of one evidence root are not independent corroboration. Similar modern translations do not establish source-language dependence. A named authority is not automatically the immediate source. A historical edge cannot transfer identity, evidence, source representation, witness state, or propositions across works.

## Layer boundary

The Historical Relation Graph is distinct from:

- the Dynamic Witness Graph for textual relations;
- Phase 2 source-representation ancestry;
- the Phase 3 Proposition-Relation Graph for internal argument structure.

Do not use internal logical relations, witness relations, or representation-derivation relations as historical relation types.

Phase 5 stores typed historical claims and their evidence. It does not traverse lineages, plan historical research, adjudicate complex transmission networks, or implement reception and conceptual-history engines.

## Stage 8 explanatory bindings

The existing graph may carry `explanation_bindings` to typed CLAIM consumers in the current source-integrity argument extension. Supply the current IntegrityRegistry as the optional fourth argument to graph construction/audit. The graph preserves binding snapshots and author-owned proposition anchors while leaving every historical edge and relation type unchanged. See [historical explanation](historical-explanation.md). Targeting/context does not create source dependence, witness identity or a confessional historical relation.
