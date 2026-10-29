# Ordinary translation task


`Translate this page.` and `Translate these pages.` go directly to ordinary translation. Read [core workflow](core-workflow.md), [evidence and uncertainty](evidence-and-uncertainty.md), and [typography and transcription](typography-and-transcription.md); consult [image processing](image-processing.md) when needed. No historical analysis module is needed to select this route.

Complete the translation through the structured task workflow:

1. Inspect page regions and reading order; fill `source-integrity.json` using [source representations](source-representations.md), retaining source spans, scripts, derivation links and relevant risks. Bind the translation representation and consequential unresolved notices to the answer. Analyze the supplied page and write the evidence checkpoint using `resources/templates/evidence-checkpoint.json` to `<TASK_DIR>/evidence-checkpoint.json`.
2. Write the response plan using `resources/templates/final-response-plan.json` to `<TASK_DIR>/final-response-plan.json`.
3. From the installed Skill root, run `python3 scripts/complete_commentary_task.py --state-dir "$HTI_STATE_DIR"`.

If the helper reports an error, repair the structured files and rerun it. Scholar View preflight batches independent blockers. The task and completion boundary in SKILL.md governs stdout and interruption. Never offer an ordinary-translation substitute for an explicit Scholar View request. See [output templates](output-templates.md) for response-plan structure and renderer-owned Identification.

Give a complete readable-page translation, consequential uncertainties, a few useful notes, and supported identity status. Inspect the original first. Use [image processing](image-processing.md) for a consequential unresolved reading, layout boundary, embedded language, or requested physical feature. Every needed view belongs to a finite evidentiary-question plan. Keep the scholarly apparatus internal unless it changes the user's understanding.

## Body-span accounting

Fill body dispositions in the [proposition integrity](proposition-integrity.md) extension of source-integrity.json. Ordinary translation requires body coverage without an Argument Dossier. Preserve quotation, interlocutor material and source-language spans; expose any lost or intentionally omitted block through the helper-rendered uncertainty or notes.
