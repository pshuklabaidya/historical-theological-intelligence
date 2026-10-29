# Research State

For sustained work, initialize `resources/templates/` with `python scripts/research_state.py init DIRECTORY --work-id ID`. The state set includes:

- work dossier;
- edition, exemplar, and witness registries;
- evidence and source checkpoints;
- image manifest and glyph atlas;
- append-only research ledger;
- generated research index.

Every record carries `work_id`. Reject cross-work references unless explicitly typed as a comparison edge. Append ledger events instead of silently rewriting conclusions. Generate the index from current files with `python scripts/research_state.py index DIRECTORY`; validate with `python scripts/research_state.py validate DIRECTORY`.

Promote identity through `python scripts/research_state.py transition DIRECTORY STATE --claim-id ID`. The command enforces prerequisites and does not infer an edition or exemplar from a secure work claim.

## Task-local and persistent state

A task directory is temporary state for the exact current `HTI_STATE_DIR`, not a work dossier or research-memory registry. Do not discover sibling tasks under the shared temporary root or read, copy, execute or reuse their checkpoints, final-response plans, build scripts, image-inspection files or temporary specialization contexts. Same-work identity does not license sibling state. Use the shipped templates, references and helpers for file shape.

Research persistence requires the existing explicit directory or storage binding, verified work identity and scope, integrity checks and provenance. The work dossier, append-only ledger and derived index remain governed by their existing validation operations. An explicitly linked later scheduled turn of the same case may retain its earlier task state. With no validated persistent state bound, state its absence and continue, or initialize this licensed research-state mechanism. Never compensate by searching temporary siblings.

## Current accountable publication

The common `publication_contract` and response-plan digest in [output templates](output-templates.md) govern this feature's substantive output and selected-operation outcome. A retained result is not fulfillment of a new request. Publish selected current exact projections or reviewed current derivations; disclose a current PARTIAL/UNRESOLVED/BLOCKED reason when a selected operation cannot be completed. Preserve native source, ownership, uncertainty, identity and relation licenses. Unrequested operations remain optional. All research, source inspection, corrections, preparation and progress updates precede the committed response. Design R selects transport from exact UTF-8 bytes: DIRECT_STDOUT at or below 24,000 bytes emits the committed answer and stops with no later tool; READ_COMMITTED_FILE above that ceiling emits a short current-publication path/hash/byte-count stub, followed only by one exact Read with allow_large=true, exact relay and stop. No other post-stub tool, narration, editing or new publication is permitted. Later truthful recovery preserves the same commit and repeats its direct payload or bound stub, never scholarship.

The existing ledger accepts research_plan_snapshot details {publication_contract, sha256}; hash the canonical contract. Such snapshots are historical, not new result authorization. Unknown novelty anchors and plans remain in the exact owned task; `validate_task_snapshot` rejects their admission as verified-work persistent state. The backend and independently licensed persistence admission are unchanged. Established Novelty snapshots resolve native work scope; anchor snapshots resolve task scope. Retain actual prior publication receipts and current source-span references for a delta. Source/proposition changes require affected claim revalidation, not automatic snapshot refresh.

Completed publication turnover preserves its input-bound checkpoint, plan and source-integrity bytes in the existing owned publication history. Retained source references must match historical and current span snapshots. A changed span is new/corrected material requiring review and selected correction; unchanged independent spans may remain retained. Older receipts without a saved substrate may prove retention only when their recorded source-integrity hash equals the unchanged current bytes; never manufacture a historical snapshot. These archives confer no current identity or evidence license.
