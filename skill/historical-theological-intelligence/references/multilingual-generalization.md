# Multilingual Generalization

## Validated language boundary

The Phase 10 validated set is exactly English (`en`), Latin (`la`), Greek (`grc`), Hebrew (`he`), German (`de`), French (`fr`), and Dutch (`nl`). Resolve profiles through `resources/languages/language-profiles.json`. An additional language may be registered only as `BEST_EFFORT` or `UNRESOLVED`; it does not acquire equal Version 0.2 validation.

## Required state

For each bounded representation or passage, retain:

- underlying source language;
- representation language;
- script and direction;
- source form and verification state;
- original string when supplied;
- derivative string when translated, transliterated, normalized, modernized, transcribed, or OCR-derived;
- parent representation and evidence roots;
- relevant uncertainty.

Mixed-language works use explicit passage, quotation, proposition, or span assignments. Do not infer every span from the document's dominant language.

## Source-form licensing

A licensed translation may support represented meaning and proposition-level analysis. It cannot by itself establish exact original wording, original spelling, source-language lexical identity, morphology, quotation form, or wording-sensitive dependence. Inspect the source-language representation before making those claims.

Historical translations may be represented simultaneously as derivative representations and historically located reception or transmission events. Keep these roles separate. A modern translation remains orientation or conceptual-analysis evidence and does not create historical transmission.

## Script, transliteration, and normalization

Preserve original Greek and Hebrew script. Preserve Greek accents and breathings where supplied. Preserve Hebrew pointing or lack of pointing, visible matres, consonantal form, and right-to-left identity. Transliteration is derivative and retains original-script ancestry. Multiple transliterations do not create independent witnesses.

Preserve historical English, Latin, German, French, and Dutch spelling. Latin diplomatic and normalized forms remain distinct, including long-s, u/v, i/j, abbreviations, and line-end divisions. Fraktur is a typographic source-form condition, not a language.

Unicode normalization, case folding, accent-insensitive indexing, and historical-spelling regularization may generate comparison candidates. They never rewrite the supplied form, establish historical equivalence, or license lexical identity or dependence.

## Same-language and cross-language analysis

Shared language does not establish dependence. Different language does not establish mediation. A cross-language relation requires the same Phase 5 historical licensing as a same-language relation. A transmission channel requires Phase 7 evidence. Phase 6 traversal may cross language boundaries only through existing validated edges.

Cross-language proposition comparison may record conceptual correspondence without lexical identity. Preserve omissions, expansions, divergences, translation identity, exact inspected spans, evidence roots, and withheld claims. Language or terminology change may coexist with Phase 8 conceptual continuity. Similar English glosses may mask conceptual discontinuity.

Phase 9 confessional comparison may use a licensed translation for bounded doctrinal analysis while withholding uninspected original-language wording. Shared translation vocabulary does not establish shared original terminology or historical dependence.

## Fail-closed rules

- Do not replace a supplied historical reading with an expected critical text.
- Do not add Hebrew pointing or remove evidence-bearing pointing silently.
- Do not strip Greek diacritics to manufacture identity.
- Do not count OCR, normalization, modernization, translation, or transliteration derivatives as independent evidence roots.
- Do not treat language detection, machine translation, OCR, embeddings, or search results as primary historical evidence.
- Do not claim universal OCR, Fraktur recognition, palaeography, Greek manuscript reading, or Hebrew manuscript reading.
- Keep uncertain language identification unresolved when explicit verification is unavailable.

Construct deterministic multilingual state with `scripts/hti_core/multilingual.py`. Its result references existing Phase 2-9 objects and never creates a parallel genealogy graph.
