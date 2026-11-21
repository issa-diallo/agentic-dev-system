"""Mission-level routing contracts against the same registry distributed to projects."""
import importlib.util
import json
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/agentic-skills.py"
SPEC = importlib.util.spec_from_file_location("skill_selection", SCRIPT)
ROUTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ROUTER)


class ManagedSelectionTests(unittest.TestCase):
    def setUp(self):
        # Contracts for this standalone PR; deployment also exercises the real registry.
        rules = [
            ("anthropic/frontend-design", "frontend", [["créer"], ["interface", "landing page"]]),
            ("marketing/copywriting", "copywriting",
             [["créer", "rédiger"], ["landing page"], ["commerciale"]]),
            ("claude-seo/seo-page", "seo-page", [["optimiser", "auditer"], ["seo"], ["page"]]),
            ("claude-seo/seo-audit", "seo-audit", [["auditer"], ["seo"], ["site"]]),
            ("claude-seo/seo-geo", "geo", [["optimiser"], ["geo"]]),
            ("context/context-optimization", "context-optimization",
             [["optimiser", "réduire"], ["contexte", "tokens"]]),
            ("context/memory-systems", "memory", [["réduire"], ["mémoire persistante"]]),
            ("context/multi-agent-patterns", "multi-agent", [["coordination"], ["multi-agent"]]),
            ("owasp/owasp-security", "security", [["sécurité", "authentication"]]),
            ("showcase/systematic-debugging", "debugging", [["bug"], ["corriger", "investigate"]]),
            ("anthropic/canvas-design", "canvas", [["créer"], ["affiche"]]),
            ("remotion/video", "video", [["vidéo"], ["remotion"]]),
        ]
        self.inventory = [
            {"id": skill_id, "name": skill_id.split("/")[1], "description": capability,
             "category": "test", "capability": capability, "repo": skill_id, "commit": "a" * 40,
             "path": "source/SKILL.md", "agents": ["claude", "codex"],
             "status": "blocked" if capability == "video" else "approved",
             "excludes": [], "priority": 20 - index, "files": ["*.tsx"],
             "depends_on": [], "triggers": groups, "extracted_sha256": "c" * 64,
             "installed": True, "enabled": True, "available": True}
            for index, (skill_id, capability, groups) in enumerate(rules)]

    def route(self, objective, files=(), agent="codex", needs=(), roots=()):
        return ROUTER.select(objective, files, roots, managed=self.inventory,
                             agent=agent, needs=needs)

    def test_project_scenarios_select_only_required_skills(self):
        cases = [
            ("Créer une landing page SaaS commerciale pour Packing Factory", ["app/Page.tsx"],
             {"anthropic/frontend-design", "marketing/copywriting"}),
            ("Automatiser la synchronisation des commandes Packing Factory", ["tasks/orders.py"],
             set()),
            ("Créer une interface React et optimiser le SEO de la page immobilière DossierClé",
             ["app/Annonce.tsx"], {"anthropic/frontend-design", "claude-seo/seo-page"}),
            ("Auditer la sécurité des droits d’accès aux documents de CustomsFlow",
             ["api/permissions.py"], {"owasp/owasp-security"}),
            ("Corriger un bug Python de conversion documentaire dans Doc2XML", ["src/convert.py"],
             {"showcase/systematic-debugging"}),
            ("Investigate a FastAPI authentication bug", ["auth.py"],
             {"showcase/systematic-debugging", "owasp/owasp-security"}),
            ("Optimiser le contexte de l’orchestrateur Agentic Dev System", [],
             {"context/context-optimization"}),
            ("Réduire les tokens consommés par la coordination multi-agent et la mémoire "
             "persistante de l’orchestrateur", ["scripts/scheduler.py"],
             {"context/context-optimization", "context/multi-agent-patterns",
              "context/memory-systems"}),
            ("Créer une affiche graphique", [], {"anthropic/canvas-design"}),
            ("Auditer le SEO du site", [], {"claude-seo/seo-audit"}),
            ("Auditer le SEO de la landing page SaaS", [], {"claude-seo/seo-page"}),
            ("Mesurer le trafic de la landing page SaaS", ["app/Page.tsx"], set()),
            ("Optimiser la visibilité GEO", [], {"claude-seo/seo-geo"}),
        ]
        inventories = [("fixture", self.inventory)]
        catalog = ROOT / "skills/catalog.json"
        if catalog.exists():
            rows = json.loads(catalog.read_text())["skills"]
            installed = [dict(row, installed=True, available=True, enabled=True) for row in rows]
            inventories.append(("distributed", installed))
        for source, inventory in inventories:
            self.inventory = inventory
            for task, files, expected in cases:
                for agent in ("codex", "claude"):
                    with self.subTest(source=source, task=task, agent=agent):
                        selected = self.route(task, files, agent, roots=[ROOT / "skills"])["selected"]
                        self.assertEqual({row["id"] for row in selected}, expected)
                        if selected:
                            self.assertEqual([row["role"] for row in selected],
                                             ["primary"] + ["complementary"] * (len(selected) - 1))

    def test_budget_compatibility_priority_exclusion_and_no_body_read(self):
        wide = ["frontend", "copywriting", "security", "context-optimization", "memory"]
        for row in self.inventory:
            if row["capability"] == "frontend":
                row["agents"] = ["claude"]
            if row["capability"] == "copywriting":
                row["enabled"] = False
        with patch.object(Path, "read_bytes", side_effect=AssertionError("body read")), \
                patch.object(Path, "read_text", side_effect=AssertionError("body read")):
            result = self.route("Projet documentaire", ["app/Page.tsx"], needs=wide)
        self.assertEqual({row["capability"] for row in result["selected"]},
                         {"security", "context-optimization", "memory"})
        self.assertEqual(result["loaded"], [])
        self.assertEqual(result["applied"], "NOT_OBSERVED")
        self.assertIn("frontend", result["missing_capabilities"])
        self.assertNotIn("instructions", json.dumps(result))
        for skill in result["selected"]:
            self.assertTrue(skill["managed"])
            self.assertEqual(len(skill["extracted_sha256"]), 64)
            self.assertTrue(skill["reasons"])

        for row in self.inventory:
            row.update(agents=["codex"], enabled=True)
        self.assertEqual(len(self.route("Projet documentaire", needs=wide)["selected"]), 3)
        self.assertFalse(self.route("Simple mise à jour", ["src/Page.tsx"])["selected"])
        seo = next(row for row in self.inventory if row["capability"] == "geo")
        seo["excludes"] = ["sans GEO"]
        self.assertFalse(self.route("Mission sans GEO", needs=["geo"])["selected"])
        result = self.route("Créer une vidéo programmée Remotion", needs=["video"])
        self.assertFalse(result["selected"])

    def test_duplicates_and_legacy_overlap(self):
        original = next(row for row in self.inventory if row["capability"] == "frontend")
        duplicate = dict(original, id="alternate/frontend-design", priority=original["priority"] - 1)
        self.inventory.insert(0, duplicate)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "SKILL.md"
            path.write_text("---\nname: frontend-patterns\ndescription: React patterns\n---\nlegacy")
            selected = self.route("Créer une interface React", roots=[folder])["selected"]
        self.assertEqual([row.get("id") for row in selected], [original["id"]])

    def test_partial_legacy_provider_covers_actual_openapi_intent(self):
        result = self.route("Auditer la sécurité et le contrat OpenAPI", roots=[ROOT / "skills"])
        selected = {row["name"]: row for row in result["selected"]}
        fallback = selected["api-design-backend-security"]
        self.assertEqual(fallback["capabilities"], ["api"])
        self.assertNotIn("api", result["missing_capabilities"])

    def test_negative_domain_cannot_return_through_legacy_provider(self):
        frontend = next(row for row in self.inventory if row["capability"] == "frontend")
        frontend["excludes"] = ["sans interface", "backend uniquement"]
        result = self.route("Concevoir le backend uniquement, sans interface React",
                            ["src/Page.tsx"], roots=[ROOT / "skills"])
        self.assertNotIn("frontend", {cap for row in result["selected"] for cap in row["capabilities"]})
        self.assertNotIn("frontend", result["missing_capabilities"])
        self.assertIn("backend", {cap for row in result["selected"] for cap in row["capabilities"]})

    def test_project_inventory_errors_are_json(self):
        with tempfile.TemporaryDirectory() as folder:
            script = Path(folder) / SCRIPT.name
            shutil.copyfile(SCRIPT, script)
            for statement in ("raise sqlite3.DatabaseError('db')",
                              "raise subprocess.CalledProcessError(128, 'git')"):
                with self.subTest(statement=statement):
                    script.with_name("agentic-skill-store.py").write_text(
                        "import sqlite3, subprocess\ndef inventory(repo):\n    " + statement + "\n")
                    result = subprocess.run([sys.executable, script, "select", "--repo", folder,
                                             "--agent", "claude", "--task", "landing page"],
                                            capture_output=True, text=True)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn("error", json.loads(result.stdout))
                    self.assertFalse(result.stderr)

    def test_blocked_unavailable_and_unidentified_harness(self):
        self.inventory.append({"id": "removed/former", "status": "removed", "agents": [],
                               "installed": True, "enabled": True, "available": False})
        for row in self.inventory:
            row["available"] = False
        result = self.route("", needs=["frontend", "video"])
        self.assertFalse(result["selected"])
        self.assertEqual(result["missing_capabilities"], ["frontend", "video"])
        for row in self.inventory:
            row.update(available=True, installed=False)
        self.assertFalse(self.route("Créer une interface React")["selected"])
        for row in self.inventory:
            row["installed"] = True
        self.assertFalse(self.route("Créer une interface React", agent="unknown")["selected"])

    def test_exclusion_applies_to_path_metadata_symlink_and_direct_load(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "superpowers" / "skills" / "example" / "SKILL.md"
            source.parent.mkdir(parents=True)
            source.write_text("---\nname: frontend\ndescription: Frontend patterns\n---\nprivate")
            alias = root / "alias" / "SKILL.md"
            alias.parent.mkdir()
            alias.symlink_to(source)
            external = root / "package" / "SKILL.md"
            external.parent.mkdir()
            external.write_text("---\nname: superpowers:test\ndescription: Frontend\n---\nprivate")
            clean = root / "product-superpowers-insights" / "SKILL.md"
            clean.parent.mkdir()
            clean.write_text("---\nname: frontend-reports\ndescription: Frontend\n---\nordinary")
            self.assertEqual([row["path"] for row in ROUTER.discover([root])["skills"]],
                             [str(clean)])
            for path in (source, alias, external):
                with self.assertRaises(ValueError):
                    ROUTER.load(path)

    def test_fresh_project_keeps_legacy_file_and_phase_routing(self):
        for row in self.inventory:
            row.update(installed=False, available=False)
        files, roots = ["src/Page.tsx"], [ROOT / "skills"]
        before = ROUTER.select("Investigate layout", files, roots, "REVIEW")
        after = ROUTER.select("Investigate layout", files, roots, "REVIEW", managed=self.inventory,
                              agent="claude", needs=["video"])
        self.assertEqual(after["selected"], before["selected"])
        self.assertIn("video", after["missing_capabilities"])

    def test_cli_uses_project_store_without_legacy_roots(self):
        with tempfile.TemporaryDirectory() as folder:
            subprocess.run(["git", "init", "-q", folder], check=True)
            script = SCRIPT
            if not SCRIPT.with_name("agentic-skill-store.py").exists():
                script = Path(folder) / SCRIPT.name
                shutil.copyfile(SCRIPT, script)
                script.with_name("agentic-skill-store.py").write_text(
                    'from pathlib import Path\ndef inventory(repo):\n'
                    '    assert (Path(repo) / ".git").is_dir()\n    return []\n')
            result = subprocess.run([sys.executable, script, "select", "--repo", folder,
                                     "--agent", "claude", "--need", "frontend", "--task", ""],
                                    capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["selected"], [])
        self.assertIn("frontend", output["missing_capabilities"])
