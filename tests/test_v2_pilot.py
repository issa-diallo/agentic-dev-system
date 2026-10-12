"""A–H integration pilot over installed scripts and temporary Git repositories.

Runtime callbacks, reviewer identities and external CI attestations are simulated.
Real native-runtime observations belong to V2_VALIDATION.md, never to these tests.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from test_scheduler import SimulatedAdapter

SOURCE = Path(__file__).resolve().parents[1]
CHECKS = [[sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests"],
          ["git", "diff", "--check"]]
MODEL_FIXTURE = {"runtime_overrides": True, "models": [
    {"id": "fixture-low", "max_level": "LOW", "efforts": ["low"], "cost_rank": 0},
    {"id": "fixture-medium", "max_level": "MEDIUM", "efforts": ["medium"], "cost_rank": 1},
    {"id": "fixture-high", "max_level": "EXTRA_HIGH", "efforts": ["high", "xhigh"],
     "cost_rank": 2}]}


class V2PilotTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="agentic-pilot-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / "team project"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")
        (self.repo / "AGENTS.md").write_text("Team rules remain authoritative.\n")
        self.git("add", "AGENTS.md")
        self.git("commit", "-qm", "fixture")
        self.install(self.repo)
        self.method = self.repo / ".agentic-local"
        self.runtime = self.module("scheduler")
        self.quality = self.module("quality")
        self.manifest = self.method / "pilot-plan.json"
        self.state = self.method / "pilot-state.json"
        self.plan = {"version": 1, "story": "pilot", "capabilities": [], "prs": []}

    def git(self, *args, repo=None):
        return subprocess.run(["git", "-C", str(repo or self.repo), *args],
                              check=True, capture_output=True, text=True).stdout.strip()

    def install(self, target):
        result = subprocess.run(["bash", str(SOURCE / "install-agentic.sh"),
                                 "--local", "--existing", str(target)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def module(self, name):
        spec = importlib.util.spec_from_file_location(
            "pilot_" + name, self.method / ("scripts/agentic-" + name + ".py"))
        result = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(result)
        return result

    def add_unit(self, name, *, files=None, reason=None, dependencies=()):
        tree = self.root / name
        self.git("worktree", "add", "-q", "-b", "feat/" + name, str(tree))
        unit = {"id": name, "reason": reason or "Deliver " + name,
                "capabilities": [name], "files": files or [name + ".py"],
                "acceptance": ["Expected behavior for " + name],
                "tests": ["python3 -B -m unittest discover -s tests", "git diff --check"],
                "contracts": [], "depends_on": list(dependencies),
                "branch": "feat/" + name, "worktree": str(tree),
                "implementer": "fixture-author-" + name}
        self.plan["capabilities"].append(name)
        self.plan["prs"].append(unit)
        self.write_plan()
        return unit

    def write_plan(self):
        self.manifest.write_text(json.dumps(self.plan))

    def scheduler(self, **options):
        return self.runtime.Scheduler(self.manifest, self.repo, self.state, **options)

    def owners(self):
        with self.runtime.WORKSPACE.registry(self.repo) as owners:
            return copy.deepcopy(owners)

    def start(self, scheduler, name, identity):
        scheduler.prepare(name)
        scheduler.load_skills(name)
        return scheduler.receipt(name, {"agent_id": identity, "runtime": "simulated",
                                       "launch_observed": True, "identity_verified": True})

    def stop(self, scheduler, name, identity, outcome="COMPLETED", result=None):
        return scheduler.handoff(name, {"agent_id": identity, "identity_verified": True,
                                        "stopped_confirmed": True, "outcome": outcome,
                                        "result": result or "Simulated runtime handoff"})

    def acceptance(self, scheduler, name, checks):
        current = scheduler.resume()
        return {"status": checks["verdict"], "orchestrator_verified": True,
                "source": "Fixture orchestrator; real subprocess checks, simulated identity",
                "criteria": ["Behavior checked in temporary worktree"],
                "tests": ["Actual unittest subprocess and git diff --check"],
                "head": checks["snapshot"]["head"], "snapshot": checks["snapshot"],
                "plan_sha256": current["plan_sha256"]}

    def review_fixture(self, checks, author):
        # Schema validation only: this is not a real independent review or CI run.
        return {"reviewer": "simulated-reviewer", "implementer": author,
                "snapshot": checks["snapshot"], "verdict": "PASS", "findings": [],
                "evidence": "Simulated independent review for contract integration",
                "runtime_evidence": {"agent_id": "simulated-review-session",
                                     "verified_by_orchestrator": True},
                "ci": {"source": "external", "status": "PASS",
                       "head": checks["snapshot"]["head"],
                       "evidence": "SIMULATED external CI attestation; no native CI run"}}

    def test_a_bad_split_blocks_before_execute(self):
        unit = self.add_unit("combined")
        self.plan["capabilities"] = ["login", "profile"]
        unit["capabilities"] = ["login", "profile"]
        self.write_plan()
        adapter = SimulatedAdapter()
        with self.assertRaisesRegex(self.runtime.Blocked, "separable capabilities"):
            self.scheduler().dispatch(adapter)
        self.assertEqual(adapter.calls, [])
        self.assertEqual(self.owners(), {})
        self.assertEqual(self.git("status", "--porcelain", repo=self.root / "combined"), "")

    def test_b_independent_assignments_reserve_isolated_resources_before_collection(self):
        for name in ("labels", "csv"):
            unit = self.add_unit(name)
            unit["resources"] = [{"type": "api", "name": "fixture-" + name}]
        self.write_plan()
        pilot = self

        class ObservingSimulation(SimulatedAdapter):
            def launch(self, task):
                reservations = pilot.owners()
                pilot.assertIn(task["owner"]["id"], reservations)
                pilot.assertIsNone(task["agent_id"])
                pilot.assertEqual(task["state"], "ASSIGNED")
                return super().launch(task)

            def wait(self, task):
                if not any(call[0] == "wait" for call in self.calls):
                    reservations = list(pilot.owners().values())
                    pilot.assertEqual(len(reservations), 2)
                    pilot.assertEqual(len({r["worktree"] for r in reservations}), 2)
                    pilot.assertEqual(len({r["id"] for r in reservations}), 2)
                    apis = {resource["name"] for r in reservations
                            for resource in r["resources"] if resource["type"] == "api"}
                    pilot.assertEqual(apis, {"fixture-labels", "fixture-csv"})
                return super().wait(task)

        adapter = ObservingSimulation()
        state = self.scheduler().dispatch(adapter)
        self.assertEqual(adapter.calls, [("launch", "labels"), ("launch", "csv"),
                                         ("wait", "labels"), ("wait", "csv")], state)
        self.assertTrue(all(t["state"] == "COMPLETED" and not t["accepted"]
                            and t["runtime"] == "simulated" for t in state["tasks"].values()))
        self.assertEqual(self.owners(), {})

    def test_c_api_sql_react_load_only_selected_installed_instructions(self):
        cases = [("api", "Add authenticated API", "api/users.py", "api-design-backend-security"),
                 ("sql", "Add SQL migration", "migrations/001.sql", "database-migrations"),
                 ("react", "Fix React rendering", "src/Profile.tsx", "frontend-patterns")]
        for name, reason, path, _ in cases:
            self.add_unit(name, files=[path], reason=reason)
        scheduler = self.scheduler(skill_roots=[self.method / "skills"])
        for name, _, _, expected in cases:
            with self.subTest(domain=name):
                assigned = scheduler.prepare(name)
                self.assertEqual({s["name"] for s in assigned["skills"]["selected"]}, {expected})
                self.assertEqual(assigned["skills"]["loaded"], [])
                self.assertEqual(assigned["skills"]["applied"], [])
                loaded = scheduler.load_skills(name)
                self.assertEqual(len(loaded), 1)
                raw = Path(loaded[0]["path"]).read_bytes()
                self.assertEqual(loaded[0]["sha256"], hashlib.sha256(raw).hexdigest())
                self.assertEqual(loaded[0]["bytes"], len(raw))
                self.assertEqual(loaded[0]["applied"], "NOT_OBSERVED")
                self.stop(scheduler, name, None, "BLOCKED", "Routing only; runtime never started")

    def test_d_routes_levels_and_synthetic_capacity_escalation_without_observed_model(self):
        models = self.module("models")
        cases = [({"type": "read", "complexity": "simple"}, "LOW", "fixture-low"),
                 ({"type": "implementation"}, "MEDIUM", "fixture-medium"),
                 ({"complexity": "complex"}, "HIGH", "fixture-high")]
        for task, level, model in cases:
            result = models.route(task, MODEL_FIXTURE)
            self.assertEqual((result["level"], result["recommendation"]["model"]), (level, model))
            self.assertFalse(result["applied"])
            for metric in ("tokens", "api_cost", "codex_quota", "duration_seconds"):
                self.assertIsNone(result["metrics"][metric])
        attempt = {"task_id": "resistant", "outcome": "FAIL", "level": "MEDIUM",
                   "diagnosis_kind": "capacity", "diagnosis": "Synthetic capacity policy fixture"}
        routed = models.route({"id": "resistant"}, MODEL_FIXTURE, [attempt])
        self.assertEqual(routed["level"], "HIGH")
        self.assertEqual(routed["attempt_history"], [attempt])
        self.add_unit("standard")
        scheduler = self.scheduler(models=MODEL_FIXTURE)
        task = self.start(scheduler, "standard", "simulated-standard")
        self.assertEqual(task["model_requested"], {"model": "fixture-medium", "effort": "medium"})
        self.assertIsNone(task["model_observed"])
        self.assertFalse(task["model_applied"])
        self.stop(scheduler, "standard", "simulated-standard")

    def test_e_real_defect_blocked_corrected_requeued_and_fresh_quality_required(self):
        unit = self.add_unit("defect", files=["value.py", "tests/test_value.py"])
        tree = self.root / "defect"
        scheduler = self.scheduler()
        self.start(scheduler, "defect", "simulated-defect-1")
        (tree / "tests").mkdir()
        (tree / "tests/test_value.py").write_text(
            "import unittest\nfrom value import normalize\n"
            "class ValueTests(unittest.TestCase):\n"
            "    def test_normalization(self):\n"
            "        self.assertEqual(normalize('  HELLO  '), 'hello')\n")
        (tree / "value.py").write_text("def normalize(value):\n    return value\n")
        self.git("add", "value.py", "tests/test_value.py", repo=tree)
        self.git("commit", "-qm", "controlled defect", repo=tree)
        bad = self.quality.run_checks(tree, CHECKS)
        self.assertEqual(bad["verdict"], "BLOCKED")
        self.assertNotEqual(bad["checks"][0]["returncode"], 0)
        stopped = self.stop(scheduler, "defect", "simulated-defect-1", "BLOCKED", bad)
        self.assertEqual(stopped["state"], "BLOCKED")
        (tree / "value.py").write_text("def normalize(value):\n    return value.strip().casefold()\n")
        self.git("add", "value.py", repo=tree)
        self.git("commit", "-qm", "correct controlled defect", repo=tree)
        good = self.quality.run_checks(tree, CHECKS)
        self.assertEqual(good["verdict"], "PASS")
        review = self.review_fixture(good, unit["implementer"])
        self.assertEqual(self.quality.assess(tree, bad, review, unit["implementer"]), "BLOCKED")
        self.assertEqual(self.quality.assess(tree, good, review, unit["implementer"]), "PASS")
        self_review = {**review, "reviewer": unit["implementer"]}
        self.assertEqual(self.quality.assess(tree, good, self_review, unit["implementer"]), "BLOCKED")
        scheduler.requeue("defect", {"orchestrator_verified": True, "reason": "Defect corrected",
                                     "proof": "New Git commit and real unittest PASS",
                                     "snapshot": good["snapshot"],
                                     "plan_sha256": scheduler.resume()["plan_sha256"],
                                     "agent_id": "simulated-defect-1", "identity_verified": True,
                                     "stopped_confirmed": True})
        self.start(scheduler, "defect", "simulated-defect-2")
        completed = self.stop(scheduler, "defect", "simulated-defect-2", result=good)
        self.assertEqual(completed["history"][0]["task"]["agent_id"], "simulated-defect-1")
        self.assertTrue(scheduler.accept("defect", self.acceptance(scheduler, "defect", good))["accepted"])
        self.git("commit", "--allow-empty", "-qm", "new head requires fresh evidence", repo=tree)
        self.assertEqual(self.quality.assess(tree, good, review, unit["implementer"]), "BLOCKED")
        self.assertFalse(scheduler.resume()["tasks"]["defect"]["accepted"])
        fresh = self.quality.run_checks(tree, CHECKS)
        self.assertEqual(self.quality.assess(tree, fresh, self.review_fixture(fresh, unit["implementer"]),
                                           unit["implementer"]), "PASS")
        self.assertTrue(scheduler.accept("defect", self.acceptance(scheduler, "defect", fresh))["accepted"])

    def test_f_installation_in_linked_worktree_preserves_index_team_and_personal_files(self):
        self.add_unit("install")
        tree = self.root / "install"
        paths = ["AGENTS.md", ".codex/config.toml", ".agents/skills/team/SKILL.md", "draft.txt"]
        for path in paths:
            target = tree / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("Personal or team content: " + path)
        self.git("add", "AGENTS.md", ".codex/config.toml", repo=tree)
        before_status = self.git("status", "--porcelain", repo=tree)
        index_path = Path(self.git("rev-parse", "--path-format=absolute", "--git-path", "index", repo=tree))
        before_index = index_path.read_bytes()
        before_worktrees = self.git("worktree", "list", "--porcelain")
        saved = {path: (tree / path).read_bytes() for path in paths}
        self.install(tree)
        self.assertEqual(index_path.read_bytes(), before_index)
        self.assertEqual(self.git("status", "--porcelain", repo=tree), before_status)
        self.assertEqual(self.git("worktree", "list", "--porcelain"), before_worktrees)
        self.assertEqual({p: (tree / p).read_bytes() for p in paths}, saved)
        check = subprocess.run(["bash", "scripts/agentic-check.sh", "--existing"],
                               cwd=tree / ".agentic-local", capture_output=True)
        self.assertEqual(check.returncode, 0, check.stderr)
        self.git("add", "-A", repo=tree)
        self.assertNotIn(".agentic-local", self.git("diff", "--cached", "--name-only", repo=tree))

    def test_g_restart_retains_actual_git_identity_and_blocks_outside_scope_without_relaunch(self):
        self.add_unit("resume")
        scheduler = self.scheduler()

        class InterruptedSimulation(SimulatedAdapter):
            def wait(self, task):
                return None  # Simulate disconnect while runtime remains active.

        adapter = InterruptedSimulation()
        running = scheduler.dispatch(adapter)["tasks"]["resume"]
        owner = running["owner"]["id"]
        tree = self.root / "resume"
        (tree / "resume.py").write_text("actual scoped modification\n")
        self.git("add", "resume.py", repo=tree)
        self.git("commit", "-qm", "actual progress before disconnect", repo=tree)
        for _ in range(2):
            resumed = self.scheduler().dispatch(adapter)["tasks"]["resume"]
            self.assertEqual(resumed["agent_id"], running["agent_id"])
            self.assertEqual(resumed["owner"]["id"], owner)
            self.assertEqual(resumed["state"], "RUNNING")
            self.assertIn(owner, self.owners())
        self.assertEqual(adapter.calls, [("launch", "resume")])
        outside = tree / "personal.txt"
        outside.write_text("Preserve this unrelated work.\n")
        blocked = self.scheduler().dispatch(adapter)["tasks"]["resume"]
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertTrue(blocked["active"])
        self.assertIn(owner, self.owners())
        self.assertEqual(adapter.calls, [("launch", "resume")])
        self.assertEqual(outside.read_text(), "Preserve this unrelated work.\n")
        self.stop(scheduler, "resume", running["agent_id"], "BLOCKED")
        self.assertEqual(self.owners(), {})

    def test_h_context_measurement_records_bytes_without_token_or_causal_gain_claim(self):
        router = self.module("skills")
        skills = self.method / "skills"
        started = time.perf_counter()
        selected = router.select("Fix React rendering", ["src/Profile.tsx"], [skills])
        loads = [router.load(item["path"]) for item in selected["selected"]]
        measurement = {"method": "Identical installed library; selected bodies versus all bodies",
                       "selected_bytes": sum(item["bytes"] for item in loads),
                       "all_library_bytes": sum(p.stat().st_size for p in skills.glob("*/SKILL.md")),
                       "duration_seconds": time.perf_counter() - started,
                       "tokens": None, "api_cost": None, "codex_quota": None,
                       "causal_runtime_gain": None}
        roundtrip = json.loads(json.dumps(measurement))
        self.assertEqual(roundtrip["selected_bytes"],
                         sum(len(Path(item["path"]).read_bytes()) for item in loads))
        self.assertGreater(roundtrip["all_library_bytes"], roundtrip["selected_bytes"])
        self.assertGreaterEqual(roundtrip["duration_seconds"], 0)
        self.assertIsNone(roundtrip["causal_runtime_gain"])
        self.assertTrue(all(roundtrip[key] is None for key in ("tokens", "api_cost", "codex_quota")))


if __name__ == "__main__":
    unittest.main()
