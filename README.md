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

HTI is not a linear prompt pipeline. Claude operates as the reasoning layer inside a governed architecture. The kernel and capability modules orchestrate the work, typed state preserves evidence and provenance, and deterministic Python tooling controls the mechanical path from native objects to valid publication.

```mermaid
flowchart TB

    U["Natural-language request"]

    subgraph ORCH["HTI orchestration layer"]
        R["Intent routing + operation composition"]
        K["HTI kernel"]
        M["8 capability modules"]
        R --> K
        K <--> M
    end

    subgraph CLAUDE["Claude reasoning plane"]
        C1["Source interpretation"]
        C2["Proposition + argument reconstruction"]
        C3["Historical relation assessment"]
        C4["Uncertainty + counterevidence"]
        C5["Response synthesis"]
    end

    subgraph STATE["Typed state + knowledge layer"]
        T["Task state"]
        E["Evidence + provenance"]
        S["Source representations"]
        P["Proposition-Relation Graph"]
        H["Historical Relation Graph"]
        W["Witness + work state"]
    end

    subgraph CONTROL["Deterministic Python control plane"]
        N["Native constructors"]
        B["Bindings + serialization"]
        V["Validation + preflight"]
        I["Integrity + checksums"]
        C["Completion receipts"]
        N --> B
        B --> V
        V --> I
        I --> C
    end

    PUB["Validated publication"]
    OUT["Auditable user response"]

    U --> R
    M <--> C1
    M <--> C2
    M <--> C3
    M <--> C4
    M <--> C5

    M <--> T
    M <--> E
    M <--> S
    M <--> P
    M <--> H
    M <--> W

    C1 <--> S
    C2 <--> P
    C3 <--> H
    C4 <--> E
    C5 <--> T

    T --> N
    E --> N
    S --> N
    P --> N
    H --> N
    W --> N
    C5 --> N

    C --> PUB
    PUB --> OUT

    V -. "reject invalid state" .-> T
```

The core historical-intelligence analytical spine is:

```mermaid
flowchart LR

    SR["Source representation"]
    AD["Argument Dossier"]
    PRG["Proposition-Relation Graph"]
    HRG["Historical Relation Graph"]

    DWG["Dynamic Witness Graph<br/>textual relations"]
    CONF["Confessional / Creedal Tracing"]

    EA["Evidence Ancestry"]
    UNC["Dependency-Sensitive Uncertainty"]

    SR --> AD
    AD --> PRG
    PRG --> HRG

    SR <--> DWG

    PRG --> CONF
    HRG --> CONF

    EA -. governs .-> AD
    EA -. governs .-> PRG
    EA -. governs .-> HRG

    UNC -. propagates through .-> PRG
    UNC -. propagates through .-> HRG
```

This preserves the governing HTI flow - source to Argument Dossier to Proposition-Relation Graph to Historical Relation Graph - while showing the cross-cutting structures that make the domain model non-linear. The Dynamic Witness Graph remains separate from the Historical Relation Graph so that textual-witness relations are not conflated with intellectual-historical relations. Evidence ancestry governs downstream claims, dependency-sensitive uncertainty propagates through the proposition and historical relation structures, and confessional-creedal tracing draws on both argument and historical relation analysis without being treated as evidence of historical dependence.

This separation of responsibilities is deliberate: Claude handles interpretation and scholarly judgment, while Python tooling handles state isolation, construction, serialization, validation, checksums, preflight, and completion receipts. The publication boundary prevents unvalidated state from becoming the final user-facing response.

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
