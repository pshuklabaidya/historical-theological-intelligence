# Evidence and Uncertainty

## Evidence classes

Use exactly these classes in state:

- `supplied_image_observation`
- `bibliography`
- `other_witness`
- `historical_translation`
- `external_authority`
- `inference_reconstruction`

Record a concrete description, source locator, independence group, and confidence. Confidence is a judgment within a class, never a promotion into another class. Multiple crops or enlargements from one image share one independence group.

An evidence item in `resources/templates/evidence-checkpoint.json` uses the exact field names `evidence_id`, `evidence_class`, `description`, `source_locator`, `independence_group`, and `confidence`. Do not use `class`. For example, after inspecting an actual supplied page, record `{"evidence_id":"E-page","evidence_class":"supplied_image_observation","description":"Inspected supplied page","source_locator":"page-1","independence_group":"supplied-image-1","confidence":"possible"}`. This is a shape example, not evidence for any particular reading or identity. Record diagnostic checks and page states separately where required.

Unaudited model memory is not an evidence class. Put it, if needed, in `identity_hypotheses` as a non-evidentiary search lead with `user_visible: false` and `admissible_as_identity_evidence: false`. It cannot satisfy a work-identity gate.

## Typed page evidence

Use `PAGE_VISIBLE`, `PAGE_UNCERTAIN`, `PAGE_OBSCURED`, and `PAGE_LOST` for the supplied-page state of a region. Fully opaque, unreadable or lost supplied-page content has no contextual completion: preserve its gap and refuse unsupported guessing, even when requested or labeled `CONJECTURE`. Partial visible letterforms remain `PAGE_UNCERTAIN`; evidence-based probable readings and unrelated conjectural discussion remain possible. The forbidden transition is `PAGE_OBSCURED` or `PAGE_LOST` to `PAGE_VISIBLE`. Enhancement and repeated inspection of the same pixels cannot supply an independent witness.

For every blocked `legibility_regions` entry, `output_spans` must bind its literal placeholder to every published supplied-page layer. Each binding is exactly `{"field":"translation","start":0,"end":12}` with actual zero-based Python Unicode character offsets into that layer; field is `translation`, `diplomatic_latin`, or `normalized_latin`. The example offsets are shape only. Bind the actual `[unreadable]`, `[obscured]`, `[missing]`, `[illegible]`, `[lacuna]` or `[...]` token, never a semantic completion. Latin section offsets address the joined page_text/linebreak segments, with two newlines between blocks. Ordinary translation and compact Scholar View use the same checkpoint-region bindings; compact input carries them in `legibility_regions`. Every secure surrounding passage stays in its original layer. Completion rejects absent, overlapping, stale or filled gap bindings and supplies the refusal/limitation itself.

Recovery requires `reconstruction.evidence_state: WITNESS_RECONSTRUCTION`, `relationship: RECONSTRUCTS`, `recovery_kind: wording` or `sense`, `text`, `evidence_ids`, `witness_passage`, and `alignment_note`. A supporting evidence item needs `witness_id`, `representation_type`, `source_locator`, `passage_locator`, `provenance`, `root_id`, `independence_group`, `passage_inspected: true`, the actually inspected `passage_text`, and its exact UTF-8 `passage_sha256`. The quoted `witness_passage` must occur in that text. Wording recovery must occur literally in the witness quote. Textual support is `other_witness` with ORIGINAL_TEXT, SCHOLARLY_EDITION, DIPLOMATIC_TRANSCRIPTION or FACSIMILE_SCAN; a HISTORICAL_TRANSLATION item has class `historical_translation` and permits `sense` only. Its English sense cannot establish exact missing Latin. Record any `derived_from_root_ids`; source-integrity ancestry must independently confirm the supporting source is not derived from supplied pixels. Bind each evidence item to its actual registered source representation.

Witness recovery is rendered separately by the finalizer, with its witness locator. It never replaces the placeholder in translation, diplomatic or normalized supplied-page text. The blocked page remains unresolved even when a separately labeled witness supports wording or sense.

The finalizer derives `output.transcription_spans` from the bound gaps in ordinary translation as well as diplomatic and normalized output. Separate recovery requires the inspected witness contract above; `CONJECTURE` never licenses a completion of fully blocked supplied-page content.

## Claim sufficiency

- Translation sense may rely on the visible text plus ordinary linguistic analysis; flag where the reading drives the sense.
- An exact ambiguous glyph requires supplied-image observation and a diagnostic visual or witness check such as a same-page glyph pattern, glyph atlas, or same-edition image. Lexical plausibility and positional convention may interpret a word but do not independently establish its printed glyph. A historical translation alone is insufficient.
- Proper names, Greek, Hebrew, numerals, signatures, citations, and rare terms require an explicit check or visible uncertainty.
- Orientation requires direct page structure or bibliographic sequence evidence. A catchword alone is insufficient.
- A named probable or established work identity requires a discriminating match: explicit author/title/imprint evidence, a distinctive verified phrase, page-level textual correspondence, secure sequence correspondence, or bibliographic metadata combined with textual evidence. Final named identity output also records the identity state, verification availability, claim, evidence provenance, discriminating type, and `identity_admissible: true`. When verification is unavailable or not used, only supplied-page, registered local-witness, or already verified dossier discriminators qualify. Theology, genre, city, printer milieu, style, generic layout, subject, model recollection, or exclusion of one candidate are leads, not identity evidence. Edition identity requires edition-discriminating evidence. Exemplar or provenance requires copy-specific evidence.
- A proposition is verified only when the cited source passage containing that proposition has been inspected.
- A physically obscured, missing, cropped, or otherwise unreadable glyph has no observational reading. Record it in `legibility_regions` with `physical_visibility`, placeholders in `observational_text`, `diplomatic_text`, and `normalized_text`, and the bound output gaps above. No unsupported contextual wording or semantic clause belongs in that region's reconstruction. Inspected witness recovery stays separate. Context, enhancement, and repeated crops do not turn blocked pixels into observation or independent evidence.
- Every textual relationship class, including direct reuse, quotation, parallel, paraphrase, adaptation, related topic, and non-reuse, requires inspection of the comparator passage. Record `comparator_passage_inspected: true` or `evidence_level: full_text_compared` in `textual_relationships` or `direct_reuse_claims`. A catalog, contents, index, cross-reference, snippet, or recollection is only a lead. Without a comparator, classify the relationship as `UNRESOLVED`.
- A signature may support a `signature_face` claim only with the observed mark and an established signature convention. A catchword may support `catchword_continuity` only. Quire size, gathering structure or formula, conjugacy, and internal quire pagination require their own physical or independently verified structural evidence; generic printing practice is background, not evidence about the supplied object.
- A page-visible physical description is not a physical-history claim. Brown writing, apparently handwritten writing, a date-like visible sequence, location, orientation, and visually distinct writing styles can be observed cautiously from the supplied image. Ownership, reader or annotator identity, named hand, handwriting date or century, ink composition, provenance, institutional ownership, binding, acquisition, and historical-person attribution require independent documentary, catalog, structural, or material evidence. A visible numeral is not automatically a date attribution.

## Response completion

Complete the response from the evidence checkpoint and response plan with `python3 scripts/complete_commentary_task.py --state-dir "$HTI_STATE_DIR"`. The completion helper validates the recorded evidence before rendering the response. If a claim cannot be supported at its required level, leave it unresolved or reduce it to the supported state and run the completion helper again.

Use `secure`, `probable`, `possible`, `unresolved`, or `illegible` for confidence. Never convert an unresolved reading into smooth unmarked prose. Give a useful answer when some items remain unresolved.
