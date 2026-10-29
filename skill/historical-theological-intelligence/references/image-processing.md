# Evidence-driven image inspection

Inspect the supplied original directly first. Keep its bytes unchanged. A derivative answers a consequential unresolved evidentiary question: a word affecting translation, an embedded Greek or Hebrew form, a meaning-bearing layout boundary, or a physical feature the user asks about. Already legible text and optional apparatus do not justify repeated reprocessing. Leave uncertainty visible when available pixels cannot discriminate.

## Finite question plan

Before any derivative, fill `resources/templates/image-inspection-plan.json` in the current task directory. `source` is the absolute path of the supplied original. Each question has a unique `question_id`, explicit `question`, relevance to the requested result, and a finite list of needed regions. Each region has a unique `region_id`, a reason, and view parameters in original-image coordinates.

One question may need more than one region, such as an ambiguous word and a distinct comparison letter on the same page. Separate questions may need separate regions. There is no global crop count. The finite plan is set before inspection and cannot be refilled, reopened, or renamed to repeat the same question. Plan only genuinely needed views, then reuse their observations. A later distinct question requires its own explicit relevance and finite region plan.

Register the plan:

`python3 scripts/image_inspection.py register --state-dir "$HTI_STATE_DIR" --plan "$HTI_STATE_DIR/image-inspection-plan.json"`

Generate a planned region:

`python3 scripts/image_tools.py view --state-dir "$HTI_STATE_DIR" --question-id Q1 --region-id R1`

The operation reads the registered original directly and writes the view and provenance sidecar under `<TASK_DIR>/inspection-views/`. Keep all inspection derivatives there and use this operation for their creation. Parameters may combine `box` (four pixel coordinates), `scale`, `rotation`, `contrast`, `sharpness`, and `brightness` in one operation. A `quad` uses eight original coordinates for perspective inspection instead of `box`. No derivative is used as a new input. Legacy free-standing transforms, bulk splitting, line-strip batches, and montage creation are disabled for inspection; register the actually needed regions instead.

Each region can be generated only once. An existing view is reused, never recursively cropped or enlarged. Derivative paths and hashes cannot be registered as new originals within the task; sidecar-marked derivatives are rejected. An interrupted view attempt consumes that region and can close UNRESOLVED. Unused planned regions need not be generated when the question has already resolved.

## Outcomes and ancestry

As soon as the question resolves, or when its finite planned effort cannot resolve it, close it:

`python3 scripts/image_inspection.py close --state-dir "$HTI_STATE_DIR" --question-id Q1 --outcome UNRESOLVED --finding "The word remains illegible; retain the lacuna."`

Use RESOLVED only for an adequately discriminated reading. Unused regions close with the question. Closed questions prohibit further views and cannot reopen. Record an unresolved reading in the checkpoint and response plan as uncertain, including the unresolved `finding` in the response's uncertainty or limitation text. Completion checks that this finding remains visible; closing the question is not a claim of certainty.

`image-inspection.json` retains question reasons, planned parameters, original path and SHA-256, view path and SHA-256, provenance hash, outcomes, and findings. Sidecars retain timestamp, tool schema, parameters, original ancestry, and `independent_evidence: false`. Derivatives are inspection aids, never new witnesses or independent corroboration. Derivative evidence uses `supplied_image_observation` and the original's independence group. Record its original path/hash and view path/hash in provenance. Multiple records from the same pixels do not increase independent support.

Final completion requires every registered question to close and verifies original, view, and sidecar hashes. It rejects unplanned image files in task state and derivative evidence promoted to an independent group or witness class. An original stored inside the task directory requires its exact path and hash in supplied-image evidence provenance or the inspection plan. Ordinary translation, Scholar View, rare-book work, and page-based historical work share this contract. Tasks that need no derivative use the original and require no inspection plan. Inspection does not license unsupported edition, exemplar, recto/verso, provenance, ownership, ink, or handwriting-date claims.
