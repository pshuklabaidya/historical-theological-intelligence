# Typography and Transcription

## Passes

1. Record layout, typefaces, lineation, visible punctuation, abbreviations, line-end division, and damage.
2. Make a diplomatic transcription without silently expanding or modernizing.
3. Make a normalized Latin layer: expand abbreviations in brackets or notes when uncertain; regularize u/v and i/j only in this layer; resolve line-end division; retain meaningful spelling.
4. Translate from the best-supported reading while retaining links to uncertain tokens.

For explicitly diplomatic or glyph-level output, visible long s is `ſ`, genuine f is `f`, and visible round or final s is `s`. An unresolved f/ſ distinction stays marked uncertain. The normalized layer may render `ſ` as `s`, but it must not change genuine f; it must say that it normalizes long s. Do not apply a global character substitution.

For diplomatic transcription, Scholar View diplomatic Latin, explicit long-s/f resolution, exact transcription where suspicious forms occur, or a secure ambiguous s/f glyph claim, complete the long-s checklist before response completion:

1. Make a provisional transcription.
2. Generate a checklist with `python scripts/evidence_audit.py long-s transcription.txt --text --output long-s-check.json`.
3. Inspect every listed token against the supplied image and record `long_s`, `genuine_f`, `round_s`, or `unresolved`, plus the diplomatic and normalized forms.
4. Validate it with `python scripts/evidence_audit.py long-s long-s-check.json`.
5. Copy the reviewed checks into the evidence checkpoint's `long_s_audit`, set `required: true`, `checklist_status: validated`, and `reviewed_against_supplied_image: true`, then run `python scripts/evidence_audit.py check CHECKPOINT`.

The utility does not decide readings automatically. Lexical plausibility and positional convention can guide interpretation, but they are not independent proof of an exact printed glyph. Multiple crops of the same ambiguous pixels remain one visual source. Leave an unresolved required token unresolved rather than presenting it as secure diplomatic text.

Diplomatic output must preserve visible distinctions. Normalized output must say what was normalized. Use `[...]` for supplied expansions, `[?]` for uncertain letters, and `[illegible]`, `[obscured]`, or a measured lacuna for unreadable text. Physical obstruction controls this layer: when glyphs are masked, lost, cropped out, or otherwise not visible, do not fill them from context in either diplomatic or normalized Latin. A possible completion may appear only in a separate labelled reconstruction layer as `inference_reconstruction`; it is never an observed transcription. Enlargement, enhancement, and repeat inspection of the same blocked region do not recover opaque letters or supply independent evidence.
## Scholar View compact completion

The dedicated Scholar View adapter does not eliminate the long-s/f review. After drafting the diplomatic transcription, run `python3 scripts/complete_scholar_view_task.py --prepare-long-s --state-dir "$HTI_STATE_DIR"`; this uses the same token generator as the standard long-s workflow and writes `<TASK_DIR>/long-s-check.json` with unresolved checks. Inspect every listed token against the supplied page, record `long_s`, `genuine_f`, `round_s`, or `unresolved` plus diplomatic/normalized forms, and validate by running the final Scholar View helper. Only after that explicit review set `long_s_review.reviewed_against_supplied_image: true` in the compact task. The helper copies the reviewed checks into the canonical checkpoint and runs the unchanged long-s audit. It does not infer a glyph from lexical plausibility, typography convention, or normalized Latin.

