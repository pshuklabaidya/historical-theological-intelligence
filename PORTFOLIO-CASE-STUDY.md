# Portfolio Case Study - Historical-Theological Intelligence

## Executive summary

Historical-Theological Intelligence (HTI) is a Claude-native AI research system designed to perform complex historical and theological analysis while preserving evidence provenance, uncertainty, source boundaries, and reproducible publication controls.

The difficult part of the project was not getting a language model to produce sophisticated prose. The difficult part was building a delivery architecture in which model judgment and deterministic controls could work together without allowing confidence, fluency, or repeated inference to masquerade as evidence.

The result is a modular Claude Skill with a kernel, eight capability modules, typed state and relation models, native authoring transactions, deterministic validation, explicit release blockers, and reproducible candidate packaging.

## 1. Starting point - an ambiguous high-complexity problem

The initial user experience sounded simple:

> Translate these pages.

The actual requirement surface was much larger. A reliable system needed to handle damaged and difficult source material, uncertain readings, multiple textual witnesses, bibliographic identity, historical argument structure, intellectual lineage, reception, doctrinal comparison, and work-specific context.

Those concerns could not be collapsed into one prompt without making the result impossible to audit.

The first design decision was therefore to decompose the problem into evidence-bearing objects, relations, states, permissions, and operations.

## 2. Converting ambiguity into an executable system

The system was organized around a small number of durable abstractions:

- **source representations** preserve whether the system is working from an image, original text, transcription, OCR, historical translation, modern translation, quotation, edition, or prior translation;
- **argument dossiers** capture the internal architecture of historically located arguments;
- **proposition-relation graphs** represent how claims depend on, support, qualify, or constrain one another;
- **historical relation graphs** represent transmission, reception, mutation, dependence, and other historical relationships;
- **typed uncertainty and evidence ancestry** prevent downstream claims from silently becoming stronger than the evidence supporting them;
- **task state and publication gates** separate scholarly reasoning from the mechanical conditions required for a valid completion.

This created a system that could accept natural-language requests while keeping the internal execution model explicit.

## 3. Claude + deterministic control plane

HTI uses Claude for the work that genuinely requires model judgment:

- interpreting sources;
- selecting propositions;
- reconstructing argument architecture;
- assessing historical relations;
- reasoning about reception and transformation;
- identifying uncertainty and counterevidence;
- writing the final scholarly explanation.

Deterministic software handles work that should not depend on improvisation:

- state creation and isolation;
- constructor invocation;
- native object serialization;
- evidence and source bindings;
- review hashes;
- provenance snapshots;
- operation registries;
- validation;
- preflight;
- completion receipts;
- checksum manifests;
- deterministic packaging.

The separation allows the model to remain flexible without making the delivery system vague.

## 4. Delivery and governance model

The project uses an explicit operating lifecycle:

```text
scope
-> architecture
-> implementation
-> deterministic qualification
-> live acceptance
-> causal audit
-> bounded corrective
-> requalification
-> frozen candidate
```

Several practices keep that lifecycle disciplined:

**Single authoritative candidate.** Only one implementation baseline is allowed to control a corrective cycle.

**Immutable evidence.** Passing evidence is retained rather than rerun merely because another development turn begins.

**Release blockers are explicit.** Architectural bypasses, systematic execution failures, evidence-safety failures, fabricated unreadable text, and cross-work contamination are treated differently from ordinary isolated model fallibility.

**Repairs are dependency-bounded.** A defect does not automatically reopen the entire architecture. The changed surface and affected validation surface are identified first.

**Reproducible handoffs.** Candidate identity is bound by file count, SHA-256, manifests, path safety, and deterministic rebuild checks.

This operating discipline became a reusable methodology for managing complex AI development, not just a feature of the historical-theology domain.

## 5. Native authoring corrective

A key later-stage challenge was operational convergence. The underlying capability existed, but complex workflows still placed too much burden on the model to manually assemble valid native state before publication.

The corrective introduced a bounded **native-authoring transaction**. Claude supplies scholarly constructor inputs and reviewed decisions; the transaction performs the mechanical construction, binding, serialization, and preflight work.

The transaction did not weaken the evidence model or accept arbitrary prebuilt native files. It narrowed the model's responsibility to the part that actually benefits from model reasoning.

This is a recurring AI product lesson: reliability often improves not by asking the model to reason harder, but by moving deterministic work out of the model's execution burden.

## 6. Validation as product infrastructure

Validation is treated as part of the product architecture.

The current candidate reports:

| Gate | Result |
| --- | ---: |
| Inherited qualification | **63/63 PASS** |
| Negative native-authoring transaction gates | **8/8 PASS** |
| L007 blank-state local gate | **PASS** |
| L014 blank-state local gate | **PASS** |
| Internal checksum manifest | **137/137 PASS** |
| ZIP CRC | **PASS** |
| Duplicate paths | **0** |
| Unsafe paths | **0** |
| Symlinks | **0** |
| Deterministic rebuild | **BYTE-IDENTICAL PASS** |

The negative gates matter as much as the positive ones. They test whether the system correctly refuses invalid publication conditions rather than merely whether it can succeed on a happy path.

## 7. What the project demonstrates beyond the domain

Although HTI's subject matter is historical theology, the delivery problems are broadly applicable to enterprise AI:

- turning ambiguous expert workflows into structured AI engagements;
- deciding which work belongs to the model and which belongs to deterministic software;
- translating domain rules into schemas, operations, and acceptance criteria;
- designing for provenance and auditability;
- creating reusable delivery patterns rather than one-off demos;
- distinguishing product failures from model variability;
- using narrow causal correction instead of uncontrolled iteration;
- preserving stakeholder-visible simplicity over a complex internal execution model.

The domain is specialized. The systems, delivery, and operating lessons are not.

## 8. Current state

The current public candidate is:

`historical-theological-intelligence-v0.3-native-authoring-transaction-candidate.zip`

SHA-256:

`283ee82bb5a052e0f6eb51f5341f4621395e4a8cd69d0a15ded28ce0c3259085`

It is published as a qualified v0.3 production candidate. A formal release decision is not asserted beyond the evidence recorded in the repository.

## 9. Repository entry points

- [README.md](README.md) - technical and portfolio overview
- [RELEASE-STATUS.md](RELEASE-STATUS.md) - candidate identity and qualification state
- [skill/historical-theological-intelligence/SKILL.md](skill/historical-theological-intelligence/SKILL.md) - Claude Skill entrypoint
- [skill/historical-theological-intelligence/kernel/](skill/historical-theological-intelligence/kernel/) - kernel behavior
- [skill/historical-theological-intelligence/scripts/](skill/historical-theological-intelligence/scripts/) - deterministic control and validation tooling
- [dist/](dist/) - exact frozen production candidate
