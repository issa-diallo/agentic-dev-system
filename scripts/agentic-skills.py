#!/usr/bin/env python3
"""Discover scoped skill metadata and route capabilities without loading instructions."""
import argparse
from fnmatch import fnmatchcase
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import unicodedata


# Each capability has task triggers, file triggers, and skill metadata matches.
CAPABILITIES = {
    "security": (r"\b(auth|authenticat(?:ion|e[ds]?|ing|ed)|authoriz(?:ation|e[ds]?|ing)|"
                 r"authentifi(?:cation|é(?:e|s|es)?|er)|autoris(?:ation|é(?:e|s|es)?|er)|"
                 r"permissions?|security|sécurité|tenant|secrets?|vulnerabilities)\b|vulnérab",
                 r"(^|[/_.-])(auth|authentication|authorization|permissions?|security)([/_.-]|$)",
                 r"security|sécurité|vulnerab|secure.web"),
    "api": (r"\bapi\b|endpoint|openapi|graphql|\brest\b",
            r"(^|/)(api|routes?)/|openapi|graphql",
            r"api.design|api.pattern|design.*api|openapi|graphql|rest.*design"),
    "backend": (r"backend|django|fastapi|laravel|server",
                r"(^|/)(backend|server)/", r"backend|django|fastapi|laravel"),
    "migration": (r"migration|\bsql\b|schema|schéma",
                  r"(^|/)migrations?/|\.sql$",
                  r"database|base.de.données|schema.migration|sql.migration|"
                  r"migrat.*(postgres|sql|schema)"),
    "frontend": (r"frontend|react|\bnext(\.js|js)?\b|\bui\b|interface utilisateur",
                 r"\.(tsx|jsx|vue|svelte)$|(^|/)(frontend|components)/",
                 r"frontend|react|\bnext(\.js|js)?\b|ui.ux|interface.*design"),
    "impact": (r"cross.module|plusieurs modules|change.impact|refactor",
               r"(?!)", r"change.impact|impact.analysis|analyse.*impact"),
    "testing": (r"\btests?\b|tdd|test.driven",
                r"(^|/)(tests?|__tests__)/|test_|\.test\.",
                r"test.driven|tdd|unit.test|integration.test|test.*patterns|"
                r"testing.(patterns|strategy|workflow|best)|test.collaboration"),
    "e2e": (r"\be2e\b|end.to.end|browser|navigateur|playwright",
            r"(^|/)(e2e|playwright)/|playwright.config", r"e2e|end.to.end|playwright"),
    "parallel": (r"parallel|parallèl|independent tasks|tâches indépendantes|multi.agent",
                 r"(?!)", r"parallel|parallèl|agent.team|orchestration"),
    "review": (r"review|relecture|revue|pr ready|pr prête",
               r"(?!)", r"code.review|reviewer|revue|relecture"),
    "verification": (r"verif|vérif|pr ready|pr prête|quality.gate",
                     r"(?!)", r"verif|vérif|quality.gate"),
    "worktrees": (r"worktrees?|isolation|isolated branches",
                  r"(?!)", r"worktrees?|workspace.manager"),
    "documentation": (r"documentation|lookup|research|recherche|\bdocs\b",
                      r"(^|/)docs/|\.md$", r"documentation|docs|researcher|lookup"),
    "context": (r"context|contexte|memory|mémoire|compact",
                r"(?!)", r"context|contexte|compact|memory|mémoire"),
    "handoff": (r"handoff|interruption|resume|reprise|checkpoint",
                r"(?!)", r"handoff|checkpoint|resume|reprise"),
    # An API contract spec (OpenAPI, Swagger) is not a feature specification.
    "planning": (r"(?<!openapi )(?<!api )(?<!swagger )\bspecs?\b|\bspecifications?\b|spécification|"
                 r"\bprd\b|breakdown|découpage|découper|user stor(?:y|ies)|\bplanning\b|"
                 r"planification|implementation.plan|plan d.implémentation",
                 r"(?!)", r"spec.driven|planning|task.breakdown|specification|planification"),
}
METADATA_LIMIT = 16384
STACKS = {
    "django": r"django|manage\.py",
    "terraform": r"terraform|opentofu|\.tf\b",
    "fastapi": r"fastapi",
    "laravel": r"laravel|artisan",
    "react": r"react|next\.?js|\.(tsx|jsx)\b",
    "swift": r"swift|ios|\.swift\b",
    "flutter": r"flutter|\.dart\b",
}
# Restrictions use declared purpose, not installation paths or a global whitelist.
SPECIALIZED_PURPOSES = (
    (r"image.generation|image.edit|nano.banana", r"image|photo|illustration|nano.banana"),
    (r"\borbit\b|\bcarousel\b|layered visual stage", r"orbit|carousel|carrousel|circular"),
    (r"cinematic|scroll.controlled|scroll.scrub|pinned.*scroll",
     r"cinematic|cinématique|scroll|scrub|pinned"),
    (r"figma", r"figma|\.fig(ma)?\b"),
    (r"\bswift(ui)?\b|\bios\b", r"swift|ios|iphone|ipad|\.swift\b"),
    (r"ui.ux.*audit|ui.ux.*auditing",
     r"audit|review|revue|accessib|ux|ui|design"),
)


def _scalar(value):
    value = value.strip()
    if value.startswith('"'):
        value = json.loads(value)
    elif value.startswith("'"):
        if len(value) < 2 or not value.endswith("'"):
            raise ValueError("unterminated quoted scalar")
        value = value[1:-1].replace("''", "'")
    elif not value or value.startswith(("[", "{", "&", "*", "!")):
        raise ValueError("expected a non-empty scalar")
    else:
        value = re.split(r"\s+#", value, maxsplit=1)[0].rstrip()
        if value.lower() in ("null", "true", "false", "~") or re.fullmatch(r"[-+]?\d+(\.\d+)?", value):
            raise ValueError("expected a string")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("expected a non-empty string")
    return value.strip()


def _metadata(path):
    """Read only bounded front matter; never read the instruction body here."""
    lines, size = [], 0
    with path.open("rb") as stream:
        if stream.readline(METADATA_LIMIT + 1).strip() != b"---":
            raise ValueError("missing front matter")
        while True:
            line = stream.readline(METADATA_LIMIT + 1)
            size += len(line)
            if not line or size > METADATA_LIMIT:
                raise ValueError("missing or oversized front matter terminator")
            if line.strip() == b"---":
                break
            lines.append(line.decode("utf-8").rstrip("\r\n"))
    result = {}
    for index, line in enumerate(lines):
        match = re.match(r"^(name|description|agentic_tier):\s*(.*)$", line)
        if not match:
            continue
        key, value = match.groups()
        if key in result:
            raise ValueError("duplicate metadata field: " + key)
        if value in ("|", ">", "|-", ">-", "|+", ">+"):
            block = []
            for following in lines[index + 1:]:
                if following and not following[0].isspace():
                    break
                block.append(following.strip())
            value = ("\n" if value.startswith("|") else " ").join(block)
        result[key] = _scalar(value)
    if not all(key in result for key in ("name", "description")):
        raise ValueError("name and description are required")
    tier = result.pop("agentic_tier", "ON_DEMAND").upper()
    if tier not in ("CORE", "ON_DEMAND", "LIBRARY"):
        raise ValueError("invalid agentic_tier")
    return {**result, "path": str(path), "tier": tier}


def _excluded_origin(value):
    """Recognize the collection namespace in a path, repository or skill name."""
    prefixes = ("superpowers:", "superpowers@", "superpowers-", "superpowers.")
    return any(part in ("superpowers", "using-superpowers") or part.startswith(prefixes)
               for part in re.split(r"[/\\]", str(value).casefold()))


def discover(roots):
    """Discover only supplied roots; canonical paths deduplicate links and loops."""
    pending = list(reversed([(index, Path(root).expanduser())
                             for index, root in enumerate(roots)]))
    visited, candidates, diagnostics = set(), {}, []
    while pending:
        root_index, path = pending.pop()
        try:
            if _excluded_origin(path):
                continue
            path = path.resolve()
            if _excluded_origin(path) or path in visited:
                continue
            visited.add(path)
            if path.is_file() and path.name == "SKILL.md":
                candidates.setdefault(path, root_index)
            elif path.is_dir():
                manifest = path / "SKILL.md"
                if manifest.is_file():
                    pending.append((root_index, manifest))
                else:
                    pending.extend((root_index, child)
                                   for child in sorted(path.iterdir(), reverse=True))
            elif not path.exists():
                diagnostics.append({"path": str(path), "error": "missing root or broken link"})
        except (OSError, RuntimeError):
            diagnostics.append({"path": str(path), "error": "unreadable path"})
    skills = []
    for path in sorted(candidates, key=lambda path: (candidates[path], str(path))):
        try:
            entry = _metadata(path)
            if not _excluded_origin(entry["name"]):
                skills.append({**entry, "root_index": candidates[path]})
        except (ValueError, OSError, UnicodeError):
            diagnostics.append({"path": str(path), "error": "invalid skill metadata"})
    return {"skills": skills, "diagnostics": sorted(diagnostics, key=lambda item: item["path"])}


def _requirements(task, files, phase):
    requirements = {}
    for capability, (task_pattern, file_pattern, _) in CAPABILITIES.items():
        reasons = []
        if re.search(task_pattern, task, re.I):
            reasons.append("task:" + capability)
        matches = [path for path in files if re.search(file_pattern, path, re.I)]
        reasons.extend("file:" + path for path in sorted(set(matches)))
        if reasons:
            requirements[capability] = reasons
    modules = set()
    for path in files:
        parts = path.strip("/").split("/")
        if len(parts) < 2 or parts[0] in ("test", "tests", "docs"):
            continue
        depth = 2 if parts[0] in ("src", "app", "lib") and len(parts) > 2 else 1
        modules.add("/".join(parts[:depth]))
    if len(modules) > 1:
        requirements.setdefault("impact", []).append("files:multiple modules")
    if phase in ("VERIFY", "REVIEW", "SHIP"):
        requirements.setdefault("verification", []).append("phase:" + phase)
    if phase in ("REVIEW", "SHIP"):
        requirements.setdefault("review", []).append("phase:" + phase)
    if phase == "HANDOFF":
        requirements.setdefault("handoff", []).append("phase:HANDOFF")
    return requirements


def _providers(skill, context):
    """A specialized skill does not provide every domain its description mentions."""
    name = skill["name"]
    purpose = re.split(r"\.\s+", skill["description"], maxsplit=1)[0]
    specialization = name + " " + purpose
    for requirement, trigger in SPECIALIZED_PURPOSES:
        if re.search(requirement, specialization, re.I) and not re.search(trigger, context, re.I):
            return set()
    for stack, pattern in STACKS.items():
        if stack in name.lower() and not re.search(pattern, context, re.I):
            return set()
    providers = {capability for capability, (_, _, pattern) in CAPABILITIES.items()
                 if re.search(pattern, name, re.I)}
    if re.search(r"migration|database|schema", name, re.I):
        providers.add("migration")
    if "migration" in providers:
        providers.discard("backend")
    if not providers:
        providers = {capability for capability, (_, _, pattern) in CAPABILITIES.items()
                     if re.search(pattern, purpose, re.I)}
    return providers


def _legacy_select(task, files, roots, phase):
    """Return actual available paths and explain unavailable requested capabilities."""
    phase = phase.upper()
    if phase not in ("PREPARE", "BUILD", "VERIFY", "REVIEW", "SHIP", "HANDOFF"):
        raise ValueError("unsupported phase")
    inventory = discover(roots)
    requirements = _requirements(task, [str(path).replace("\\", "/") for path in files], phase)
    selected, library, covered, equivalents = [], [], set(), {}
    for skill in inventory["skills"]:
        identity = (skill["name"], " ".join(skill["description"].split()), skill["tier"])
        if identity in equivalents:
            original = equivalents[identity]
            original.setdefault("equivalent_paths", []).append(skill["path"])
            library.append({**skill, "tier": "LIBRARY", "state": "AVAILABLE",
                            "duplicate_of": original["path"]})
            continue
        providers = _providers(skill, task + " " + " ".join(map(str, files)))
        matched = [capability for capability in requirements if capability in providers]
        reasons = [reason for capability in matched for reason in requirements[capability]]
        if skill["tier"] == "CORE":
            reasons.insert(0, "metadata:CORE")
        if reasons:
            covered.update(matched)
            item = {**skill, "tier": "CORE" if skill["tier"] == "CORE" else "ON_DEMAND",
                    "capabilities": matched, "reasons": reasons, "state": "SELECTED"}
            equivalents[identity] = item
            selected.append(item)
        else:
            library.append({**skill, "tier": "LIBRARY", "state": "AVAILABLE"})
    return {"phase": phase, "selected": selected, "library": library,
            "missing_capabilities": sorted(set(requirements) - covered),
            "diagnostics": inventory["diagnostics"], "loaded": [], "applied": "NOT_OBSERVED"}


# CORE remains a project decision. Mission-specific references share a small budget.
ON_DEMAND_LIMIT = 3
LEGACY_CAPABILITIES = {"context-optimization": "context", "memory": "context",
                       "multi-agent": "parallel"}


def _words(value):
    plain = "".join(c for c in unicodedata.normalize("NFKD", value.casefold())
                    if not unicodedata.combining(c))
    return " " + " ".join(re.findall(r"[^\W_]+", plain)) + " "


def _matches(term, objective):
    phrase = _words(term)
    return bool(phrase.strip()) and phrase in objective


def _managed_reasons(row, objective, files, needs):
    capability = row["capability"]
    if capability in needs:
        reasons = ["need:" + capability]
    else:
        reasons = []
        for group in row["triggers"]:
            term = next((term for term in group if _matches(term, objective)), None)
            if term is None:
                return []
            reasons.append("task:" + term)
        if not reasons:
            return []
    reasons.extend("file:" + path for path in files
                   if any(fnmatchcase(path, pattern) for pattern in row["files"]))
    return reasons


def _managed_candidates(rows, task, files, agent, needs):
    objective = _words(task)
    candidates, requested = [], set(needs)
    available, excluded = False, set()
    for row in rows:
        if row["status"] not in ("approved", "blocked"):
            continue  # A removed pin retains attribution but no longer has routing metadata.
        if any(_excluded_origin(row[field]) for field in ("id", "repo", "name", "path")):
            continue
        usable = (row["status"] == "approved" and agent in row["agents"]
                  and all(row[key] is True for key in ("enabled", "available", "installed")))
        available = available or usable
        if any(_matches(term, objective) for term in row["excludes"]):
            excluded.add(row["capability"])
            continue
        reasons = _managed_reasons(row, objective, files, needs)
        if not reasons:
            continue
        capability = row["capability"]
        requested.add(capability)
        if not usable:
            continue
        item = {key: row[key] for key in ("id", "name", "description", "capability",
                                          "commit", "extracted_sha256")}
        item.update(managed=True, path=row["id"], tier="ON_DEMAND", capabilities=[capability],
                    reasons=reasons, state="SELECTED")
        evidence_count = sum(reason.startswith("file:") for reason in reasons)
        rank = (capability not in needs, -row["priority"], -evidence_count, row["id"])
        candidates.append((rank, item))
    ranked = [item for _, item in sorted(candidates, key=lambda pair: pair[0])]
    return ranked, requested, available, excluded


def select(task, files, roots, phase="BUILD", *, managed=(), agent=None, needs=()):
    """Route reviewed installed references alongside providers in explicit legacy roots."""
    files = [str(path).replace("\\", "/") for path in files]
    result = _legacy_select(task, files, roots, phase)
    if not managed and not needs:
        return result
    needs = set(needs)
    candidates, requested, available, excluded = _managed_candidates(managed, task, files, agent, needs)
    legacy = result["selected"]
    requested.update(set(result["missing_capabilities"]) - excluded)
    if not available and not excluded:
        covered = {cap for item in legacy for cap in item["capabilities"]}
        result["missing_capabilities"] = sorted(requested - covered)
        return result
    requirements = _requirements(task, files, phase.upper())
    intent = set(_requirements(task, [], phase.upper())) | needs
    selected = [item for item in legacy if item["tier"] == "CORE"]
    covered = {cap for item in selected for cap in item["capabilities"]}
    used = 0
    for item in candidates + [entry for entry in legacy if entry["tier"] != "CORE"]:
        if item.get("managed"):
            useful = set(item["capabilities"]) - covered
        else:
            useful = set(item["capabilities"]) - covered - excluded
            if available:
                useful &= intent
            # In a focused task, FastAPI/Django identifies the stack. An additional backend
            # provider requires actual backend work before loading its generic instructions.
            if candidates and "backend" not in needs and not re.search(r"\b(backend|server)\b", task, re.I):
                useful.discard("backend")
        requested.update(useful)
        if not useful or (available and used >= ON_DEMAND_LIMIT):
            if not item.get("managed"):
                result["library"].append({**item, "tier": "LIBRARY", "state": "AVAILABLE"})
            continue
        if not item.get("managed"):
            caps = [cap for cap in item["capabilities"] if cap in useful]
            reasons = [why for cap in caps for why in requirements[cap]]
            item = {**item, "capabilities": caps, "reasons": list(dict.fromkeys(reasons))}
        selected.append(item)
        used += 1
        covered.update(useful)
        if item.get("managed") and item["capability"] in LEGACY_CAPABILITIES:
            covered.add(LEGACY_CAPABILITIES[item["capability"]])
    for index, item in enumerate(selected):
        item["role"] = "primary" if index == 0 else "complementary"
    result["selected"] = selected
    result["missing_capabilities"] = sorted(requested - covered)
    return result


def _project_inventory(repo):
    script = Path(__file__).with_name("agentic-skill-store.py")
    spec = importlib.util.spec_from_file_location("agentic_skill_store", script)
    store = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(store)
    try:
        return store.inventory(repo)
    except (subprocess.CalledProcessError, sqlite3.Error) as error:
        raise ValueError("project inventory unavailable") from error


def load(path):
    """Read instructions explicitly and return evidence of this read, not application."""
    if _excluded_origin(path):
        raise ValueError("excluded skill collection")
    path = Path(path).expanduser().resolve()
    if _excluded_origin(path):
        raise ValueError("excluded skill collection")
    if path.name != "SKILL.md":
        raise ValueError("load requires a SKILL.md path")
    if _excluded_origin(_metadata(path)["name"]):
        raise ValueError("excluded skill collection")
    content = path.read_bytes()
    return {"path": str(path), "state": "LOADED", "sha256": hashlib.sha256(content).hexdigest(),
            "bytes": len(content), "instructions": content.decode("utf-8"),
            "applied": "NOT_OBSERVED"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("discover", "select"):
        child = commands.add_parser(command)
        child.add_argument("--root", action="append", required=command == "discover", default=[])
        if command == "select":
            child.add_argument("--task", required=True)
            child.add_argument("--file", action="append", default=[])
            child.add_argument("--phase", default="BUILD")
            child.add_argument("--repo", help="Git project with a managed skill store")
            child.add_argument("--agent", help="actual agent adapter (codex or claude)")
            child.add_argument("--need", action="append", default=[], help="required capability")
    commands.add_parser("load").add_argument("path")
    args = parser.parse_args()
    try:
        if args.command == "discover":
            result = discover(args.root)
        elif args.command == "select":
            if args.repo and not args.agent:
                raise ValueError("project selection requires an agent adapter")
            managed = _project_inventory(args.repo) if args.repo else ()
            result = select(args.task, args.file, args.root, args.phase, managed=managed,
                            agent=args.agent, needs=args.need)
        else:
            result = load(args.path)
    except (ValueError, OSError, UnicodeError, RuntimeError):
        print(json.dumps({"error": "invalid request or unreadable skill"}))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
