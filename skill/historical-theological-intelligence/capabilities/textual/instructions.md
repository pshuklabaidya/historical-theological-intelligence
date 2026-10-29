# Textual capability

Only the kernel may validate and publish the final response and receipt. Native constructors and typed state remain subject to the bound composition.

## Translate this page

`Translate this page.` and `Translate these pages.` select ordinary translation directly. Read [translation task](../../references/translation-task.md), [core workflow](../../references/core-workflow.md), and [typography and transcription](../../references/typography-and-transcription.md). Analyze the supplied source, fill `<TASK_DIR>/evidence-checkpoint.json` and `<TASK_DIR>/final-response-plan.json` from their templates, and complete with `python3 scripts/complete_commentary_task.py --state-dir "$HTI_STATE_DIR"`. No historical module is needed to select translation. Give the complete readable translation, consequential uncertainty, useful notes, and supported identification through that response.

## Scholar View and image inspection

`Give me scholar view.` selects [Scholar View](../../references/scholar-view.md). Fill `<TASK_DIR>/scholar-view-task.json` from its template; bind the actual source anchor and prepare the helper-owned long-s review only for an actual image as documented there, then complete with `python3 scripts/complete_scholar_view_task.py --state-dir "$HTI_STATE_DIR"`. Preserve the compact interface, independently inspected comparator evidence, and separate historical description and Westminster comparison. Never substitute ordinary translation for an explicit Scholar View request.

For any image derivative, read [image processing](../../references/image-processing.md) before creating it. Register explicit evidentiary questions and their finite needed regions. Generate each view directly from the original through `scripts/image_tools.py view`; close each question as RESOLVED or UNRESOLVED before completion. Multiple needed regions are permitted. Reuse views; do not recursively crop or count derivatives as independent witnesses. Rare-book, marginalia, handwriting, and reader-mark requests also use [rare-book evidence](../../references/rare-book-evidence.md). Signatures and catchwords are distinct evidence classes. Physical appearance alone does not establish physical history.
