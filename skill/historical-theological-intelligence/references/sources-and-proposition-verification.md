# Sources and Proposition Verification

Maintain a source checkpoint for each attributed quotation, maxim, anecdote, legal rule, or doctrinal proposition.

## Source Mode execution

An intent such as `Identify the author's sources.` completes in one task through the ordinary structured completion route. Keep research bounded and checkpoint each stage rather than asking the user to execute separate searches.

1. **Inventory:** inspect the supplied passage first. Copy `resources/templates/source-checkpoint.json` into `<TASK_DIR>/source-checkpoint.json`; record each substantive printed citation, surrounding proposition, argumentative function and reading uncertainty. Recheck adjacent citations so one authority does not displace another.
2. **Prioritize:** select the citations material to the requested analysis. Routine biblical references need external research only when the argument depends on their wording or identification. Preserve doubtful citations as leads.
3. **Verify:** when external research is available and permitted, attempt primary-source inspection for prioritized citations. Save each access route and outcome before proceeding. After a failed route, use one reasonable alternative where available; stop rather than looping. Do not present an unattempted lookup as an access failure.
4. **Check the proposition:** retain the printed citation, modern identification, inspected locator and text, proposition being checked, and supported / contradicted / partly supported / unresolved assessment separately. A title or correct subject does not verify the attributed proposition.
5. **Synthesize:** run `python3 scripts/evidence_audit.py source "$HTI_STATE_DIR/source-checkpoint.json"`. Transfer only licensed findings into canonical evidence and claims, leave failed checks unresolved, then use the selected completion helper. Source-checkpoint validation does not itself license a final claim. Final publication still requires the canonical evidence, source-integrity and terminal gates.

Do not import a remembered correction, tested source answer, or specialized bibliography as verification. Cross-work reuse requires the inspected comparator passage under [cross-work research](cross-work-research.md); an index hit routes to available full text. One inaccessible source leaves the other findings usable.

Stages are `lead`, `work_identified`, `location_identified`, `passage_inspected`, and `proposition_verified`. A catalog, title, index, or contents hit can support only a lead or work identity. Mark `proposition_verified` only after inspecting a passage that supports the particular proposition.

For ancient and early-modern citations, record printed form, normalized author/work, location, inspected text, and match assessment. For Roman or canon law, preserve separately:

- the citation as printed;
- the modern standardized location;
- the proposition found at that location;
- any mismatch or unresolved abbreviation.

One unresolved source must not abort the whole response. Report verified items and isolate the unresolved one.

## Current accountable publication

The common `publication_contract` and response-plan digest in [output templates](output-templates.md) govern this feature's substantive output and selected-operation outcome. A retained result is not fulfillment of a new request. Publish selected current exact projections or reviewed current derivations; disclose a current PARTIAL/UNRESOLVED/BLOCKED reason when a selected operation cannot be completed. Preserve native source, ownership, uncertainty, identity and relation licenses. Unrequested operations remain optional. All research, source inspection, corrections, preparation and progress updates precede the committed response. Design R selects transport from exact UTF-8 bytes: DIRECT_STDOUT at or below 24,000 bytes emits the committed answer and stops with no later tool; READ_COMMITTED_FILE above that ceiling emits a short current-publication path/hash/byte-count stub, followed only by one exact Read with allow_large=true, exact relay and stop. No other post-stub tool, narration, editing or new publication is permitted. Later truthful recovery preserves the same commit and repeats its direct payload or bound stub, never scholarship.

Link Source Mode checks to research-plan decision questions rather than treating search breadth as resolution. Reuse source-checkpoint inventory/prioritize/verify/assess and full-text alternatives. A material accessible source gets inspection or a specific incomplete reason; one failed route does not abort independent research. An inspected proposition remains source-level evidence with its actual permissions. Do not turn TOC, metadata, locator, downloaded text or OCR discovery into verification. Selected source-verification work reaches a current governed result or explicit reasoned incomplete outcome.
