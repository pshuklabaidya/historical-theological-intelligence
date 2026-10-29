#!/usr/bin/env python3
"""Validate the production skill package without importing its scripts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REQUIRED_REFERENCES = {
    "specialization-onboarding.md", "historical-infrastructure-sensitivity.md", "novelty.md", "cartography.md", "historical-explanation.md", "core-workflow.md", "evidence-and-uncertainty.md", "typography-and-transcription.md",
    "work-identification.md", "bibliographic-discovery.md", "witnesses-and-collation.md",
    "scripture-and-original-languages.md", "sources-and-proposition-verification.md",
    "loci-and-exegetical-method.md", "cross-work-research.md",
    "westminster-confessional-comparison.md", "pastoral-study.md", "rare-book-evidence.md",
    "citation.md", "research-state.md", "output-templates.md", "adversarial-controls.md",
    "image-processing.md", "translation-task.md",
    "source-representations.md", "specialization-core.md",
    "argument-architecture.md",
    "dependency-uncertainty.md",
    "historical-relations.md",
    "lineage-traversal.md",
    "source-transmission-forensics.md",
    "reception-conceptual-history.md",
    "confessional-creedal-locus-tracing.md",
    "multilingual-generalization.md",
    "natural-language-routing.md",
}
REQUIRED_TEMPLATES = {
    "work-dossier.json", "edition-registry.json", "exemplar-registry.json", "witness-registry.json",
    "evidence-checkpoint.json", "source-checkpoint.json", "image-manifest.json", "glyph-atlas.md",
    "research-ledger.jsonl", "research-index.md", "final-response-plan.json", "image-inspection-plan.json",
    "source-integrity.json", "specialization-registry.json", "specialization-manifest.json", "specialization-context.json",
}
REQUIRED_SCRIPTS = {"evidence_audit.py", "finalize_response.py", "complete_commentary_task.py", "research_state.py", "collate.py", "search_witness.py", "image_tools.py", "validate_skill.py", "terminal_output.py", "image_inspection.py", "task_state.py", "complete_scholar_view_task.py", "source_integrity.py", "specialization_core.py", "specialization_storage.py"}
REQUIRED_CORE_MODULES = {
    "specialization_onboarding.py", "historical_infrastructure.py", "historical_sensitivity.py", "novelty.py", "cartography.py", "historical_explanation.py", "__init__.py", "audit.py", "completion.py", "hashing.py", "manifest.py", "model.py",
    "provenance.py", "relations.py", "source_identity.py", "uncertainty.py",
    "source_representation.py",
    "argument_architecture.py",
    "dependency_uncertainty.py",
    "historical_relations.py",
    "lineage_engine.py",
    "source_transmission.py",
    "reception_history.py",
    "confessional_registry.py",
    "multilingual.py",
    "natural_language_routing.py",
}


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    if root.name != "historical-theological-intelligence":
        errors.append("root folder must be historical-theological-intelligence")
    skill = root / "SKILL.md"
    if not skill.is_file():
        return ["missing SKILL.md"]
    text = skill.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        errors.append("SKILL.md lacks YAML frontmatter")
    else:
        fm = match.group(1)
        name = re.search(r"^name:\s*(.+)$", fm, re.M)
        desc = re.search(r"^description:\s*(.+)$", fm, re.M)
        if not name or name.group(1).strip() != root.name:
            errors.append("frontmatter name does not match folder")
        if not desc or not desc.group(1).strip():
            errors.append("frontmatter description missing")
        elif len(desc.group(1).strip()) > 200:
            errors.append("description exceeds 200 characters")
        version = re.search(r"^\s+version:\s*(.+)$", fm, re.M)
        if not version or version.group(1).strip() != "0.3-composable-operational-convergence.1":
            errors.append("version must be 0.3-composable-operational-convergence.1")

    if not (root / "references/proposition-integrity.md").is_file():
        errors.append("missing proposition integrity reference")
    try:
        envelope=json.loads((root / "resources/templates/source-integrity.json").read_text())["argument_integrity"]
        if set(envelope) != {"coverage_scopes","coverage","propositions","consumers","prg"}:
            errors.append("argument integrity template fields")
    except (KeyError, ValueError, OSError):
        errors.append("missing argument integrity template")

    for name in ('specialization_core.py', 'specialization_storage.py', 'specialization_resources.py'):
        if not (root / 'scripts' / name).is_file():
            errors.append('missing specialization core script: ' + name)
    try:
        registry = json.loads((root / 'resources/templates/specialization-registry.json').read_text())
        manifest = json.loads((root / 'resources/templates/specialization-manifest.json').read_text())
        context = json.loads((root / 'resources/templates/specialization-context.json').read_text())
        if any(value.get('schema_version') != 'hti-specialization-1' for value in (registry, manifest, context)):
            errors.append('specialization template schema version')
        if registry.get('records') != {} or registry.get('storage_binding') is not None or context.get('registry') is not None:
            errors.append('specialization templates must contain no installed state')
    except (ValueError, OSError, AttributeError):
        errors.append('missing specialization core templates')

    try:
        from specialization_resources import catalog, bytes_at
        from specialization_core import manifest
        for entry in catalog(root)['entries']:
            m = manifest(json.loads(bytes_at(root, entry['manifest_locator'], entry['manifest_sha256'])))
            if m['scope'] != entry['scope'] or m['level'] != entry['level'] or m['specialization_id'] != entry['specialization_id']:
                errors.append('installed manifest scope mismatch')
            for resource in m['resources']:
                packet = json.loads(bytes_at(root, resource['locator'], resource['sha256']))
                if packet['scope'] != m['scope']:
                    errors.append('installed resource scope mismatch')
                for asset in packet['assets']:
                    bytes_at(root, asset['locator'], asset['sha256'])
    except (ValueError, OSError, KeyError, TypeError) as exc:
        errors.append('invalid installed resources: ' + str(exc))

    refs = {p.name for p in (root / "references").glob("*.md")}
    missing = REQUIRED_REFERENCES - refs
    if missing:
        errors.append("missing references: " + ", ".join(sorted(missing)))
    templates = {p.name for p in (root / "resources" / "templates").glob("*") if p.is_file()}
    missing = REQUIRED_TEMPLATES - templates
    if missing:
        errors.append("missing templates: " + ", ".join(sorted(missing)))
    scripts = {p.name for p in (root / "scripts").glob("*.py")}
    missing = REQUIRED_SCRIPTS - scripts
    if missing:
        errors.append("missing scripts: " + ", ".join(sorted(missing)))
    core_modules = {p.name for p in (root / "scripts" / "hti_core").glob("*.py")}
    missing = REQUIRED_CORE_MODULES - core_modules
    if missing:
        errors.append("missing hti_core modules: " + ", ".join(sorted(missing)))

    capability_registry = json.loads((root / "registry/capabilities.json").read_text())
    linked = {p.split("/",1)[1] for m in capability_registry["modules"].values() for p in m["instructions"] if p.startswith("references/")}
    unlinked = REQUIRED_REFERENCES - linked
    if unlinked:
        errors.append("references not routed from kernel capability registry: " + ", ".join(sorted(unlinked)))

    for path in (root / "resources" / "templates").glob("*.json"):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSON {path.name}: {exc}")
    ledger = root / "resources" / "templates" / "research-ledger.jsonl"
    if ledger.is_file():
        for n, line in enumerate(ledger.read_text(encoding="utf-8").splitlines(), 1):
            try: json.loads(line)
            except json.JSONDecodeError as exc: errors.append(f"invalid ledger line {n}: {exc}")

    registry = root / "resources" / "confessional-registry" / "initial-registry.json"
    loci = root / "resources" / "confessional-registry" / "loci.json"
    for path in (registry, loci):
        if not path.is_file():
            errors.append(f"missing Phase 9 registry resource: {path.name}")
        else:
            try: json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc: errors.append(f"invalid Phase 9 resource {path.name}: {exc}")

    languages = root / "resources" / "languages" / "language-profiles.json"
    if not languages.is_file():
        errors.append("missing Phase 10 language profile registry")
    else:
        try:
            raw_languages = json.loads(languages.read_text(encoding="utf-8"))
            validated = sorted(
                item["language_id"] for item in raw_languages.get("profiles", [])
                if item.get("validation_status") == "VALIDATED_V02"
            )
            if validated != sorted(["en", "la", "grc", "he", "de", "fr", "nl"]):
                errors.append("Phase 10 validated language set must contain exactly seven locked languages")
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            errors.append(f"invalid Phase 10 language registry: {exc}")

    for path in (root / "scripts").rglob("*.py"):
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except SyntaxError as exc:
            errors.append(f"syntax error {path.name}:{exc.lineno}: {exc.msg}")

    forbidden_dirs = {"tests", "fixtures", "development", "witnesses", "__pycache__"}
    for path in root.rglob("*"):
        if path.is_dir() and path.name in forbidden_dirs:
            errors.append(f"development directory in production: {path.relative_to(root)}")
    unfinished = re.compile(r"\b(T" + r"ODO|FIX" + r"ME|T" + r"BD)\b|<re" + r"place|place" + r"holder text", re.I)
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".md", ".py"} and unfinished.search(path.read_text(encoding="utf-8", errors="replace")):
            errors.append(f"scaffold marker in {path.relative_to(root)}")
    from validate_composition_package import validate as validate_composition
    errors.extend(validate_composition(root))
    return errors


def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parents[1]); args = p.parse_args()
    errors = validate(args.root.resolve())
    if errors:
        print("FAIL"); print("\n".join(f"- {e}" for e in errors)); return 1
    print("PASS"); return 0


if __name__ == "__main__":
    raise SystemExit(main())
