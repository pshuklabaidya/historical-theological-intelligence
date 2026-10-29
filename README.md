# Historical-Theological Intelligence

**Historical-Theological Intelligence (HTI)** is a production-oriented AI research system built for **Claude's Skill System**. It combines model reasoning with deterministic state, provenance, validation, typed evidence, graph-based argument modeling, and controlled publication so that complex historical research can remain auditable rather than relying on fluent model output alone.

> **Portfolio summary:** HTI began as a difficult domain problem - translating and interpreting early-modern theological sources under strict evidence constraints - and grew into a modular AI system with a kernel, eight capability modules, typed operational state, native authoring transactions, deterministic validation, live acceptance gates, and reproducible release packaging.

## What this project demonstrates

HTI is not just a prompt or a document workflow. It is an example of taking an ambiguous AI use case from problem definition through architecture, implementation, validation, operational correction, and a reusable delivery framework.

The work demonstrates:

- **AI transformation architecture** - converting an open-ended knowledge-work problem into a structured system that teams can actually operate.
- **Claude-native development** - the production target is Claude's Skill System, with natural-language invocation and modular capability routing.
- **LLM + deterministic software design** - Claude performs scholarly judgment while deterministic code handles state, validation, provenance, serialization, and publication controls.
- **Evaluation engineering** - positive, negative, adversarial, regression, blank-state, and packaging gates are treated as first-class product requirements.
- **Delivery governance** - scope locks, explicit release blockers, immutable candidates, bounded corrective cycles, and evidence-preserving handoffs prevent "fix until green" development.
- **Reusable operating infrastructure** - the project includes validators, state machinery, registries, manifests, transaction tooling, and repeatable qualification patterns rather than one-off demonstrations.
- **Cross-functional translation** - complex subject-matter requirements are turned into concrete product behavior, schemas, tests, acceptance criteria, and user-facing workflows.

## The problem

Historical-theological research is a useful stress test for enterprise AI because the hard part is not generating plausible prose. The system must preserve distinctions such as:

- what a supplied source visibly says versus what another witness suggests;
- observation versus reconstruction versus conjecture;
- similarity versus genealogy;
- chronology versus influence;
- citation versus proof of immediate source;
- textual-witness relations versus intellectual-historical relations;
- doctrinal correspondence versus historical dependence;
- relation type versus confidence;
- direct evidence versus downstream inference.

A model can sound convincing while silently collapsing those distinctions. HTI therefore treats evidence discipline as a systems problem, not merely a prompting problem.

## System architecture

```mermaid
flowchart LR
    A["Natural-language request"] --> B["Routing / operation selection"]
    B --> C["HTI kernel"]
    C --> D["Capability modules"]
    D --> E["Typed evidence + task state"]
    E --> F["Native authoring transaction"]
    F --> G["Validation + preflight"]
    G --> H["Deterministic publication"]
    H --> I["Auditable user response"]
```

The historical-intelligence layer then organizes research around:

```mermaid
flowchart LR
    S["Source / page / text"] --> A["Argument Dossier"]
    A --> P["Proposition-Relation Graph"]
    P --> H["Historical Relation Graph"]
```

The textual witness graph remains separate from the historical relation graph so that textual dependence and intellectual dependence are not conflated.

## Operating model

The project was managed through a staged delivery model designed to preserve hard-earned evidence while allowing targeted correction:

```text
problem definition
    -> scope and invariants
    -> architecture
    -> implementation
    -> deterministic qualification
    -> live acceptance
    -> causal diagnosis
    -> bounded corrective
    -> requalification
    -> frozen candidate
```

Each candidate is treated as an immutable artifact with explicit checksums. A failed gate does not authorize broad redesign by default. Repairs are bounded to the demonstrated failure surface, and previously earned evidence is retained unless the changed dependency surface invalidates it.

That operating model is as important as the code: it turns a complex AI build into a repeatable delivery practice rather than an open-ended experimentation loop.

## Current validation profile

The current v0.3 production candidate is:

`historical-theological-intelligence-v0.3-native-authoring-transaction-candidate.zip`

Its published qualification state includes:

- **63/63 inherited qualification checks passing**
- **8/8 negative native-authoring transaction gates passing**
- **L007 blank-state local gate passing**
- **L014 blank-state local gate passing**
- **137/137 internal checksum manifest entries passing**
- **clean extracted tree equal to packaged source tree byte-for-byte**
- **deterministic rebuild passing**
- **ZIP CRC, path-safety, duplicate-path, and symlink checks passing**

The repository deliberately distinguishes a qualified production candidate from a formal release decision. See [RELEASE-STATUS.md](RELEASE-STATUS.md).

## Example user requests

HTI is designed for ordinary natural-language interaction rather than requiring users to learn internal mode names:

```text
Using HTI, translate these pages.

Using HTI, what is this argument made of?

Using HTI, trace this argument backward and forward.

Using HTI, where did this distinction come from?

Using HTI, how did this source reach the author?

Using HTI, trace this locus through the Reformed confessions.
```

Underneath those requests, the system selects and composes structured operations while preserving evidence permissions and publication requirements.

## Core capabilities

The current v0.3 line includes:

- argument architecture reconstruction;
- proposition-relation analysis;
- dependency-sensitive uncertainty;
- bidirectional intellectual lineage tracing;
- source-transmission forensics;
- immediate-source adjudication;
- reception and mutation analysis;
- conceptual-history tracking;
- evidence-ancestry tracking;
- confessional and creedal locus tracing;
- confessional formulation comparison;
- work-specific historical-theological specialization.

The validated language set includes **English, Latin, Greek, Hebrew, German, French, and Dutch**.

## Repository layout

```text
.
├── README.md
├── PORTFOLIO-CASE-STUDY.md
├── RELEASE-STATUS.md
├── STATUS.md
├── dist/
│   └── historical-theological-intelligence-v0.3-native-authoring-transaction-candidate.zip
├── skill/
│   └── historical-theological-intelligence/
│       ├── SKILL.md
│       ├── kernel/
│       ├── references/
│       ├── scripts/
│       └── ...
└── .github/
    └── workflows/
        └── unpack-production-candidate.yml
```

The exact production candidate is preserved under `dist/`. GitHub Actions verifies the outer candidate SHA-256 and complete internal checksum manifest before exposing the unpacked source tree.

For the shorter end-to-end project narrative, see [PORTFOLIO-CASE-STUDY.md](PORTFOLIO-CASE-STUDY.md).

## Project lineage

HTI grew from a deeply validated workflow for printed early-modern Latin biblical commentaries and related exegetical-theological works. Its architecture was progressively generalized so that the evidence discipline could transfer across works, periods, languages, and source forms without making one author's witnesses or assumptions normative.

The frozen `Vermigli-Judges-Translator` v1.3 implementation remains a separate reference implementation and is intentionally excluded from the general HTI production package.

## Target platform

**Claude's Skill System**

HTI is not being redefined here as a ChatGPT Skill.
