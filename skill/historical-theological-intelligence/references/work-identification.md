# Work Identification

Create a work dossier as claims plus evidence, not a flat profile. Keep competing candidates active until discriminating evidence resolves them.

Identity states:

- `UNIDENTIFIED`: no viable work candidate is yet supported.
- `WORK_CANDIDATE`: one or more evidence-linked candidates exist.
- `WORK_ESTABLISHED`: author and work are supported, but edition may remain unresolved.
- `EDITION_ESTABLISHED`: edition-specific evidence supports one edition.
- `EXEMPLAR_ESTABLISHED`: copy-specific evidence supports exemplar or provenance.

Do not skip states in recorded transitions. A title-page match can establish a work without proving that the supplied leaf belongs to that edition. A digitized exemplar can match an edition without proving identity with the user's physical copy.

An identity supplied by the user counts as an established premise only when the task provides a concrete bibliographic proposition and explicitly says that it is already securely or independently established. Record an established work premise as provenance-bearing `bibliography` evidence of kind `explicit_author_title`, with `identity_admissible: true` and origin `user_stipulated`, bound to an established `work_identity` claim; this licenses `WORK_ESTABLISHED` only. An established edition premise also needs a separate `edition_identity` claim with `bibliographic_discriminator` evidence, and licenses `EDITION_ESTABLISHED` only. Use `external_verification: not_applicable` when accepting a supplied premise without separate verification.

A request to promote an unnamed work supplies no identity evidence. Resemblances, suggestions, and confirmation requests remain hypotheses or candidates, not established identities. Keep competing records unresolved. A supplied premise is not `supplied_image_observation`; it does not establish an edition, exemplar, provenance, ownership, or any reading of the page beyond its stated level.

For every candidate, record supporting and conflicting evidence, discriminators, and status. A named probable or established author/work needs an explicit title or author clue, a distinctive verified phrase, page-level textual comparison, secure adjacent-page sequence, or catalog metadata joined to textual evidence. Reformed theology, prose style, commentary genre, biblical book, printer city, printing milieu, generic running head or layout, authorial interests, and excluding one candidate only generate search leads. They cannot by themselves make another candidate probable. A named `WORK_CANDIDATE` is user-visible only after positive admissible evidence is recorded. A remembered candidate may remain private as an `identity_hypothesis`; it is not a candidate claim.

When external verification is unavailable or has not been used, a user-visible named identity requires admissible local or already verified dossier evidence: explicit author/title, securely tied imprint or colophon, distinctive work-specific running title, verified local-witness phrase or page match, secure established sequence, or a provenance-bearing verified dossier fact. A generic biblical heading is not enough.

Model memory, recalled wording, remembered interpretation, theology, doctrine, style, genre, biblical book, structure, city, printer milieu, chronology, author interests, resemblance, and candidate exclusion may create an internal `identity_hypothesis` for a future search. They are non-evidentiary leads, never user-visible probable identity evidence. Record every named hypothesis considered, with useful author/title aliases, `user_visible: false`, and `admissible_as_identity_evidence: false`. This hypothesis inventory supplies a dynamic deny set during response completion; it does not make the hypothesis evidence.

If no admissible discriminator exists, keep the page `UNIDENTIFIED` and translate it. Set `identity.visible_claim_id` only for an evidence-licensed `work_identity` claim. Otherwise leave it null; the renderer supplies the unresolved Identification line.

## Typed licensing of established user premises

For specialization admission, preserve the actual evidence origin `user_stipulated`, CURRENT status, complete `ancestor_evidence_ids`, admissibility and concrete author/title proposition. The work evidence remains `bibliography` / `explicit_author_title`. Its provenance has `source: user_supplied_bibliographic_premise` and `established_premise` with exactly `status: ESTABLISHED`, `level: WORK`, `subject_id` and `proposition`. The subject equals the independently selected work claim subject and current work ID; the literal proposition equals that claim's value. Record this typed premise only when the actual user supplied the concrete identity as already established. It is not a substitute for that source and cannot turn a suggestion into evidence.

Derive exactly one selected asserted `general_identity` claim at every established level, with a stable subject and complete independently admissible ancestry. Each root retains its real origin. Reject missing/stale/cyclic ancestry, specialization/storage/model roots, conflicting selected claims and ambiguous/missing subjects. This work-premise admission does not establish edition or exemplar; their separate claims and discriminating general evidence remain required. Physical-history admission is unchanged. A convenience identity-binding file does not replace the bound current checkpoint or compact task.
