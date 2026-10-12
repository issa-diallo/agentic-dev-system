"""Skills route using real scoped manifests, without implicitly reading bodies."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/agentic-skills.py"
SPEC = importlib.util.spec_from_file_location("agentic_skills", SCRIPT)
ROUTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ROUTER)


class SkillRoutingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.skills = self.root / "skills"
        self.skills.mkdir()
        for name, description in {
            "api-design": "Design REST APIs and OpenAPI contracts",
            "security-review": "Review security and authentication risks",
            "database-migrations": "Safe database migrations",
            "frontend-patterns": "React frontend patterns",
            "change-impact": "Evidence-backed change impact analysis",
            "tdd": "Test-driven development",
            "playwright": "E2E browser testing",
            "parallel-execution": "Independent parallel execution",
            "code-review": "Independent code review",
            "verification-loop": "Verify tests before delivery",
            "git-worktrees": "Git worktree management",
            "documentation-lookup": "Look up official documentation",
            "context-management": "Context and memory management",
            "handoff": "Resume from a handoff checkpoint",
            "cooking": "Prepare a dinner menu",
        }.items():
            self.skill(name, description)

    def skill(self, name, description, tier=None, body="Instructions never selected implicitly."):
        path = self.skills / name / "SKILL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        metadata = f"name: {name}\ndescription: {description}\n"
        if tier:
            metadata += "agentic_tier: " + tier + "\n"
        path.write_text("---\n" + metadata + "---\n" + body, encoding="utf-8")
        return path

    def route(self, task, files=(), phase="BUILD"):
        return ROUTER.select(task, files, [self.skills], phase)

    def names(self, result):
        return {skill["name"] for skill in result["selected"]}

    def test_api_auth_routes_only_relevant_skills(self):
        result = self.route("Design authenticated API endpoint", ["src/api/accounts.py"])
        self.assertEqual(self.names(result), {"api-design", "security-review"})
        self.assertEqual(result["missing_capabilities"], [])
        self.assertEqual(result["loaded"], [])
        self.assertEqual(result["applied"], "NOT_OBSERVED")
        self.assertTrue(all(item["state"] == "SELECTED" for item in result["selected"]))
        self.assertIn("file:src/api/accounts.py", result["selected"][0]["reasons"])

    def test_sql_migration_does_not_load_frontend(self):
        result = self.route("Add SQL migration", ["migrations/003_accounts.sql"])
        self.assertEqual(self.names(result), {"database-migrations"})
        self.assertTrue(all(item["tier"] == "LIBRARY" for item in result["library"]))

    def test_frontend_correction_does_not_select_database_or_api(self):
        result = self.route("Correct React layout", ["app/components/Profile.tsx"])
        self.assertEqual(self.names(result), {"frontend-patterns"})

    def test_explicit_core_and_library_promotion(self):
        self.skill("project-policy", "Project conventions", "CORE")
        self.skill("frontend-library", "React frontend patterns", "LIBRARY")
        result = self.route("Correct React layout")
        items = {skill["name"]: skill for skill in result["selected"]}
        self.assertEqual(items["project-policy"]["tier"], "CORE")
        self.assertEqual(items["project-policy"]["reasons"], ["metadata:CORE"])
        self.assertEqual(items["frontend-library"]["tier"], "ON_DEMAND")

    def test_missing_capabilities_are_explicit(self):
        root = self.root / "empty"
        root.mkdir()
        result = ROUTER.select("Secure API", ["api/auth.py"], [root])
        self.assertEqual(result["missing_capabilities"], ["api", "security"])
        self.assertEqual(result["selected"], [])

    def test_cross_module_changes_and_worktrees(self):
        result = self.route("Parallel independent tasks in worktrees",
                            ["backend/accounts.py", "frontend/Profile.tsx"])
        self.assertTrue({"parallel-execution", "git-worktrees", "change-impact",
                         "frontend-patterns"} <= self.names(result))
        self.assertIn("backend", result["missing_capabilities"])
        result = self.route("Update behavior", ["src/api/accounts.py", "src/models/accounts.py"])
        self.assertIn("change-impact", self.names(result))

    def test_unit_testing_does_not_route_e2e_provider(self):
        result = self.route("Add unit tests", ["tests/test_accounts.py"])
        self.assertEqual(self.names(result), {"tdd"})

    def test_stack_specific_skills_do_not_match_incidental_description_words(self):
        self.skill("terraform-best-practices", "Terraform security and maintainability")
        self.skill("django-safe-migration", "Django backend migrations and security")
        self.skill("django-best-practices", "Django backend API design and security")
        self.skill("release-notes-generator", "Features, fixes and migration guidance for releases")
        result = self.route("Correct authenticated API in Django", ["backend/api/auth.py"])
        self.assertEqual(self.names(result), {"api-design", "security-review",
                                             "django-best-practices"})
        result = self.route("Add SQL migration", ["migrations/003.sql"])
        self.assertEqual(self.names(result), {"database-migrations"})

    def test_specialized_metadata_requires_its_actual_domain(self):
        descriptions = {
            "generate": "Nano Banana image generation skill. Generates frontend designs and images.",
            "purposeful-orbit-interaction": "Design an interactive orbit and carousel. "
                "Use when objects circle and react to pointer movement in a frontend.",
            "cinematic-frontend": "Build a cinematic scroll-controlled frontend sequence. "
                "Use for cinematic transitions and scroll scrubbing.",
            "figma-frontend": "Implement frontend designs from Figma. Use for Figma translation.",
            "swift-frontend": "Implement SwiftUI frontend views. Use for iOS screens.",
            "ui-ux-pro-max": "UI/UX design intelligence and auditing. React frontend tools.",
        }
        for name, description in descriptions.items():
            self.skill(name, description)
        result = self.route("Fix React rendering", ["src/components/Profile.tsx"])
        self.assertEqual(self.names(result), {"frontend-patterns"})
        self.assertIn("cinematic-frontend", self.names(self.route("Build cinematic scroll frontend")))
        self.assertIn("figma-frontend", self.names(self.route("Implement Figma frontend design")))
        self.assertIn("swift-frontend", self.names(self.route("Build SwiftUI frontend views")))

    def test_author_profile_is_not_authentication(self):
        result = self.route("Update author profile", ["src/profile.py"])
        self.assertNotIn("security-review", self.names(result))
        for task in ("Add authentication", "Authorize API access", "API authentifiée",
                     "Authenticated API", "Fix permissions"):
            self.assertIn("security-review", self.names(self.route(task)))

    def test_equivalent_skills_select_first_root_and_preserve_provenance(self):
        other = self.root / "other" / "frontend-patterns"
        other.mkdir(parents=True)
        duplicate = other / "SKILL.md"
        original = self.skills / "frontend-patterns" / "SKILL.md"
        duplicate.write_bytes(original.read_bytes())
        for roots, expected, shadow in (([other, self.skills], duplicate, original),
                                        ([self.skills, other], original, duplicate)):
            result = ROUTER.select("Fix React rendering", ["src/Profile.tsx"], roots)
            self.assertEqual(len(result["selected"]), 1)
            selected = result["selected"][0]
            self.assertEqual(selected["path"], str(expected))
            self.assertEqual(selected["equivalent_paths"], [str(shadow)])
            source = next(item for item in result["library"] if item["path"] == str(shadow))
            self.assertEqual(source["duplicate_of"], str(expected))

    def test_testing_e2e_and_ship_review(self):
        result = self.route("Test E2E browser flows", ["tests/e2e/accounts.test.ts"], "SHIP")
        self.assertTrue({"tdd", "playwright", "verification-loop", "code-review"}
                        <= self.names(result))
        self.assertNotIn("cooking", self.names(result))

    def test_handoff_context_and_documentation(self):
        result = self.route("Resume context from documentation", phase="HANDOFF")
        self.assertEqual(self.names(result), {"handoff", "context-management",
                                             "documentation-lookup"})

    def test_symlink_duplicates_and_cycles_are_deterministic(self):
        alias = self.root / "alias"
        alias.symlink_to(self.skills, target_is_directory=True)
        (self.skills / "cycle").symlink_to(self.skills, target_is_directory=True)
        first = ROUTER.discover([alias, self.skills, alias])
        second = ROUTER.discover([self.skills, alias])
        self.assertEqual(first, second)
        self.assertEqual(len(first["skills"]), 15)
        self.assertTrue(all(Path(item["path"]).is_absolute() for item in first["skills"]))

    def test_duplicate_names_preserve_distinct_sources(self):
        extra = self.root / "another"
        extra.mkdir()
        (extra / "SKILL.md").write_text("---\nname: api-design\ndescription: API design\n---\n")
        result = ROUTER.select("API endpoint", [], [extra, self.skills])
        self.assertEqual(len(result["selected"]), 2)
        self.assertEqual(len({item["path"] for item in result["selected"]}), 2)

    def test_malformed_metadata_is_reported_without_body(self):
        invalid = ["no header", "---\nname: missing-description\n---\n",
                   "---\nname: duplicate\nname: duplicate\ndescription: API\n---\n",
                   "---\nname: a\ndescription: [API, secrets]\n---\n",
                   "---\nname: a\ndescription: 42\n---\n",
                   "---\nname: a\ndescription: 'unterminated\n---\n"]
        for index, value in enumerate(invalid):
            folder = self.skills / f"invalid-{index}"
            folder.mkdir()
            (folder / "SKILL.md").write_text(value + "SECRET_BODY")
        result = ROUTER.discover([self.skills])
        self.assertEqual(len(result["diagnostics"]), len(invalid))
        self.assertNotIn("SECRET_BODY", json.dumps(result))

    def test_multiline_and_quoted_descriptions(self):
        path = self.skill("multiline", ">-\n  Design REST APIs\n  with OpenAPI")
        result = self.route("API endpoint")
        self.assertIn("multiline", self.names(result))
        entry = next(item for item in result["selected"] if item["path"] == str(path))
        self.assertEqual(entry["description"], "Design REST APIs with OpenAPI")
        self.skill("quoted", '"Design API: contracts"')
        self.assertIn("quoted", self.names(self.route("API endpoint")))

    def test_selection_never_reads_instruction_body(self):
        self.skill("opaque-body", "API design")
        path = self.skills / "opaque-body" / "SKILL.md"
        path.write_bytes(b"---\nname: opaque-body\ndescription: API design\n---\n" + b"\xff" * 10000)
        # Discovery must not decode or inspect the body beyond the front matter.
        with patch.object(Path, "read_text", side_effect=AssertionError("body read")), \
                patch.object(Path, "read_bytes", side_effect=AssertionError("body read")):
            result = self.route("API endpoint")
        self.assertIn("opaque-body", self.names(result))

    def test_load_proves_read_and_hash_not_application(self):
        path = self.skills / "api-design" / "SKILL.md"
        result = ROUTER.load(path)
        self.assertEqual(result["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(result["state"], "LOADED")
        self.assertEqual(result["applied"], "NOT_OBSERVED")
        self.assertIn("Instructions", result["instructions"])

    def test_missing_root_and_no_implicit_global_scan(self):
        result = ROUTER.discover([])
        self.assertEqual(result, {"skills": [], "diagnostics": []})
        result = ROUTER.discover([self.root / "missing"])
        self.assertEqual(len(result["diagnostics"]), 1)

    def test_oversized_metadata_and_broken_links_are_diagnostics(self):
        folder = self.skills / "huge"
        folder.mkdir()
        (folder / "SKILL.md").write_text("---\nname: huge\ndescription: " + "x" * 20000 + "\n---")
        (self.skills / "broken").symlink_to(self.root / "absent")
        loop = self.skills / "self-link"
        loop.symlink_to(loop)
        result = ROUTER.discover([self.skills])
        self.assertEqual(len(result["diagnostics"]), 3)

    def test_cli_json_and_invalid_request(self):
        command = ["python3", str(SCRIPT), "select", "--root", str(self.skills),
                   "--task", "API endpoint", "--file", "api/accounts.py"]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.names(json.loads(result.stdout)), {"api-design"})
        result = subprocess.run(command + ["--phase", "UNKNOWN"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("error", json.loads(result.stdout))


if __name__ == "__main__":
    unittest.main()
