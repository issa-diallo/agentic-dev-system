"""PR gates against real Git snapshots, including stacks and hostile declarations."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]
SCRIPT = SOURCE / "scripts/agentic-pr-check.py"


def unit(identifier, files=None):
    return {"id": identifier, "reason": f"Deliver {identifier}",
            "capabilities": [identifier], "files": files or [f"{identifier}.py"],
            "acceptance": [f"AC: {identifier} works"], "tests": [f"Test {identifier}"],
            "contracts": [], "depends_on": [], "branch": f"feat/{identifier}",
            "worktree": f"worktrees/{identifier}", "implementer": f"author-{identifier}"}


def manifest(*prs):
    return {"version": 1, "story": "S01",
            "capabilities": [cap for pr in prs for cap in pr["capabilities"]],
            "prs": list(prs)}


def justification():
    return {"constraint": "Migration and reader must change together",
            "evidence": "Mixed versions fail migration test",
            "split_risk": "Partial delivery would corrupt reads", "reviewer": "reviewer"}


class PrSplitTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")
        self.write("existing.py", "old\n")
        self.base = self.commit()
        self.plan = manifest(unit("export", ["export.py", "tests/test_export.py"]))

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                              capture_output=True).stdout.decode().strip()

    def write(self, name, value):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, bytes):
            path.write_bytes(value)
        else:
            path.write_text(value)

    def commit(self):
        self.git("add", "--all")
        self.git("commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD")

    def check(self, mode="split", plan=None, review=None, base=None, head=None, target=None,
              repo=None):
        plan_path = self.root / "plan.json"
        plan_path.write_text(json.dumps(self.plan if plan is None else plan))
        args = ["python3", str(SCRIPT), mode, str(plan_path), "--repo", str(repo or self.repo)]
        if mode == "ship":
            review_path = self.root / "review.json"
            review_path.write_text(json.dumps(review))
            args += ["--pr", (plan or self.plan)["prs"][-1]["id"], "--base", base or self.base,
                     "--head", head or self.git("rev-parse", "HEAD"),
                     "--target", target or self.base, "--review", str(review_path)]
        result = subprocess.run(args, capture_output=True, text=True)
        self.assertFalse(result.stderr, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0 if output["verdict"] == "PASS" else 1)
        return output

    def review(self, plan=None, base=None, head=None, target=None):
        plan = plan or self.plan
        pr = plan["prs"][-1]
        review = {"pr": pr["id"], "plan_sha256": self.check(plan=plan)["plan_sha256"],
                  "base": base or self.base, "head": head or self.git("rev-parse", "HEAD"),
                  "target": target or base or self.base,
                  "reviewer": "independent-session", "verdict": "PASS"}
        for axis in ("scope", "no_independent_changes", "size", "indivisibility"):
            review[axis] = {"pass": True, "evidence": f"Reviewed {axis} in fixture diff"}
        review["contracts"] = [{"name": contract["name"], "pass": True,
                                "evidence": "Compatibility test PASS"} for contract in pr["contracts"]]
        review["dependencies"] = [{"pr": dep, "pass": True,
                                   "evidence": "PR URL and actual merged SHA reviewed"}
                                  for dep in pr["depends_on"]]
        return review

    def atomic_change(self):
        self.write("export.py", "export behavior\n")
        self.write("tests/test_export.py", "test export behavior\n")
        self.commit()

    def test_four_independent_capabilities_split_into_four_prs(self):
        prs = [unit(name) for name in ("registration", "profile", "sessions", "private-files")]
        split = manifest(*prs)
        mixed = copy.deepcopy(split)
        mixed["prs"] = [mixed["prs"][0]]
        mixed["prs"][0]["capabilities"] = split["capabilities"]
        self.assertEqual(self.check(plan=mixed)["verdict"], "BLOCKED")
        result = self.check(plan=split)
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(len(result["merge_order"]), 4)
        self.assertEqual(len(result["waves"]), 1)

    def test_atomic_behavior_keeps_code_tests_and_contract_files_together(self):
        pr = unit("export", ["export.py", "tests/test_export.py", "csv-schema.json"])
        plan = manifest(pr)
        self.atomic_change()
        self.write("csv-schema.json", '{"version": 1}\n')
        self.commit()
        result = self.check("ship", plan=plan, review=self.review(plan))
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["evidence"]["diff"]["files"], 3)

    def test_indivisible_migration_can_exceed_targets_with_review(self):
        files = ["migration.sql", "reader.py", "schema.py", "tests/migration.py"]
        pr = unit("migration", files)
        pr["size_exception"] = justification()
        plan = manifest(pr)
        for file in files:
            self.write(file, "migration fixture\n" * 30)
        self.commit()
        result = self.check("ship", plan=plan, review=self.review(plan))
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["evidence"]["diff"]["lines"], 120)
        del pr["size_exception"]
        result = self.check("ship", plan=plan, review=self.review(plan))
        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertEqual(result["evidence"]["diff"]["lines"], 120)

    def test_dependent_pr_waits_for_actual_parent_merge_then_checks_stack_delta(self):
        parent, child = unit("schema"), unit("reader")
        child["depends_on"] = ["schema"]
        plan = manifest(parent, child)
        self.write("schema.py", "schema\n")
        parent_head = self.commit()
        self.write("reader.py", "reader\n")
        self.commit()
        self.assertEqual(self.check(plan=plan)["waves"], [["schema"], ["reader"]])
        blocked = self.check("ship", plan=plan, review=self.review(plan))
        self.assertEqual(blocked["verdict"], "BLOCKED")
        parent["merged_commit"] = parent_head
        result = self.check("ship", plan=plan, base=parent_head, target=parent_head,
                            review=self.review(plan, base=parent_head))
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["evidence"]["diff"]["paths"], ["reader.py"])
        unreviewed = self.review(plan, base=parent_head)
        unreviewed["dependencies"] = []
        blocked = self.check("ship", plan=plan, base=parent_head, target=parent_head,
                             review=unreviewed)
        self.assertEqual(blocked["verdict"], "BLOCKED")
        self.assertIn("every merged dependency", blocked["reason"])
        blocked = self.check("ship", plan=plan, base=parent_head, target=self.base,
                             review=self.review(plan, base=parent_head))
        self.assertEqual(blocked["verdict"], "BLOCKED")

    def test_mixed_features_cannot_ship_even_in_same_file_and_below_size_limit(self):
        self.atomic_change()
        review = self.review()
        review["no_independent_changes"] = {"pass": False,
                                            "evidence": "export.py also adds billing behavior"}
        result = self.check("ship", review=review)
        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertIn("no_independent_changes", result["reason"])

    def test_light_task_uses_one_unit_without_exceptions_or_extra_agents(self):
        self.atomic_change()
        result = self.check("ship", review=self.review())
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["waves"], [["export"]])
        self.assertFalse(result["evidence"]["size_exception_required"])
        text = (SOURCE / "docs/agentic/templates/PR_SPLIT.md").read_text()
        self.assertIn("JSON temporaires", text)
        self.assertIn("aucun document à rédiger par l’utilisateur ni nouvelle review", text)

    def test_out_of_scope_file_blocked_and_proof_retained(self):
        self.atomic_change()
        self.write("billing.py", "unrelated\n")
        self.commit()
        result = self.check("ship", review=self.review())
        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertIn("billing.py", result["reason"])
        self.assertIn("billing.py", result["evidence"]["diff"]["paths"])

    def test_review_stale_after_commit_plan_or_base_change(self):
        self.atomic_change()
        review = self.review()
        self.write("export.py", "updated behavior\n")
        self.commit()
        self.assertEqual(self.check("ship", review=review)["verdict"], "BLOCKED")
        review = self.review()
        self.plan["prs"][0]["reason"] = "Revised scope"
        self.assertEqual(self.check("ship", review=review)["verdict"], "BLOCKED")
        review = self.review()
        review["base"] = self.git("rev-parse", "HEAD")
        self.assertEqual(self.check("ship", review=review)["verdict"], "BLOCKED")

    def test_review_stale_when_target_advances_with_same_merge_base(self):
        self.atomic_change()
        head = self.git("rev-parse", "HEAD")
        review = self.review()
        self.git("checkout", "--detach", self.base)
        self.write("unrelated-on-target.py", "new target behavior\n")
        target = self.commit()
        result = self.check("ship", head=head, target=target, review=review)
        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertIn("stale review", result["reason"])
        self.assertEqual(result["evidence"]["actual_base"], self.base)
        review["target"] = target
        self.assertEqual(self.check("ship", head=head, target=target, review=review)["verdict"], "PASS")

    def test_self_review_or_missing_semantic_axis_blocked(self):
        self.atomic_change()
        review = self.review()
        review["reviewer"] = self.plan["prs"][0]["implementer"]
        self.assertEqual(self.check("ship", review=review)["verdict"], "BLOCKED")
        review = self.review()
        del review["indivisibility"]
        self.assertEqual(self.check("ship", review=review)["verdict"], "BLOCKED")

    def test_contract_and_dependency_review_must_cover_every_entry(self):
        self.atomic_change()
        self.plan["prs"][0]["contracts"] = [{"name": "CSV", "compatibility": "Backward compatible",
                                             "evidence": "Contract test"}]
        review = self.review()
        self.assertEqual(self.check("ship", review=review)["verdict"], "PASS")
        review["contracts"][0]["pass"] = False
        self.assertEqual(self.check("ship", review=review)["verdict"], "BLOCKED")
        review["contracts"] = []
        self.assertEqual(self.check("ship", review=review)["verdict"], "BLOCKED")

    def test_cycles_missing_coverage_and_duplicate_capabilities_blocked(self):
        a, b = unit("a"), unit("b")
        plan = manifest(a, b)
        a["depends_on"], b["depends_on"] = ["b"], ["a"]
        self.assertEqual(self.check(plan=plan)["verdict"], "BLOCKED")
        a["depends_on"], b["depends_on"] = [], []
        plan["capabilities"].append("missing")
        self.assertEqual(self.check(plan=plan)["verdict"], "BLOCKED")
        plan["capabilities"].pop()
        b["capabilities"] = ["a"]
        self.assertEqual(self.check(plan=plan)["verdict"], "BLOCKED")

    def test_collisions_serialize_waves_and_worktree_aliases_blocked(self):
        a, b = unit("a", ["shared.py"]), unit("b", ["shared.py"])
        plan = manifest(a, b)
        self.assertEqual(self.check(plan=plan)["waves"], [["a"], ["b"]])
        b["worktree"] = "worktrees/./a"
        self.assertEqual(self.check(plan=plan)["verdict"], "BLOCKED")

    def test_worktree_symlink_aliases_resolve_against_repo_not_process_cwd(self):
        a, b = unit("a"), unit("b")
        directory = self.repo / "worktrees/a"
        directory.mkdir(parents=True)
        (self.repo / "worktrees/b").symlink_to(directory, target_is_directory=True)
        result = self.check(plan=manifest(a, b))
        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertIn("duplicate worktree", result["reason"])

    def test_indivisibility_requires_independent_review_and_ship_confirmation(self):
        pr = self.plan["prs"][0]
        pr["capabilities"].append("format-migration")
        self.plan["capabilities"].append("format-migration")
        self.assertEqual(self.check()["verdict"], "BLOCKED")
        pr["indivisibility"] = justification()
        self.assertEqual(self.check()["verdict"], "PASS")
        self.atomic_change()
        review = self.review()
        review["indivisibility"]["pass"] = False
        self.assertEqual(self.check("ship", review=review)["verdict"], "BLOCKED")
        pr["indivisibility"]["reviewer"] = pr["implementer"]
        self.assertEqual(self.check()["verdict"], "BLOCKED")

    def test_rename_checks_source_and_destination_exactly(self):
        self.git("mv", "existing.py", "renamed.py")
        self.commit()
        self.plan["prs"][0]["files"] = ["renamed.py"]
        self.assertEqual(self.check("ship", review=self.review())["verdict"], "BLOCKED")
        self.plan["prs"][0]["files"].append("existing.py")
        result = self.check("ship", review=self.review())
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["evidence"]["diff"]["changes"][0]["status"], "R100")

    def test_binary_sizes_require_exception_instead_of_zero_line_pass(self):
        self.write("image.bin", b"\0" * 2000)
        self.commit()
        self.plan["prs"][0]["files"] = ["image.bin"]
        self.assertEqual(self.check("ship", review=self.review())["verdict"], "BLOCKED")
        self.plan["prs"][0]["size_exception"] = justification()
        result = self.check("ship", review=self.review())
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["evidence"]["diff"]["binaries"],
                         [{"path": "image.bin", "base": 0, "head": 2000}])

    def test_literal_bracket_route_names_supported(self):
        name = "app/users/[id]/page.tsx"
        self.write(name, "route\n")
        self.commit()
        self.plan["prs"][0]["files"] = [name]
        self.assertEqual(self.check("ship", review=self.review())["verdict"], "PASS")

    def test_gitlink_change_not_hidden_by_ignore_submodules(self):
        self.git("update-index", "--add", "--cacheinfo", f"160000,{self.base},private-submodule")
        self.git("commit", "-qm", "gitlink")
        self.git("config", "diff.ignoreSubmodules", "all")
        result = self.check("ship", review=self.review())
        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertIn("private-submodule", result["evidence"]["diff"]["paths"])

    def test_subdirectory_and_relative_config_cannot_hide_out_of_scope_files(self):
        self.write("src/allowed.py", "allowed\n")
        self.write("billing.py", "out of scope\n")
        self.commit()
        self.git("config", "diff.relative", "true")
        self.plan["prs"][0]["files"] = ["src/allowed.py"]
        result = self.check("ship", repo=self.repo / "src", review=self.review())
        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertEqual(result["evidence"]["diff"]["paths"], ["billing.py", "src/allowed.py"])

    def test_actual_squash_merge_sha_accepted_after_child_rebase(self):
        parent, child = unit("schema"), unit("reader")
        child["depends_on"] = ["schema"]
        plan = manifest(parent, child)
        self.write("schema.py", "schema\n")
        original_parent = self.commit()
        self.git("checkout", "--detach", self.base)
        self.write("schema.py", "schema\n")
        self.git("add", "--all")
        self.git("commit", "-qm", "squash-parent")
        merged = self.git("rev-parse", "HEAD")
        self.assertNotEqual(original_parent, merged)
        parent["merged_commit"] = merged
        self.write("reader.py", "reader\n")
        self.commit()
        result = self.check("ship", plan=plan, base=merged, target=merged,
                            review=self.review(plan, base=merged))
        self.assertEqual(result["verdict"], "PASS")

    def test_invalid_refs_manifest_and_paths_fail_closed(self):
        self.atomic_change()
        self.assertEqual(self.check("ship", head="missing-ref", review=self.review())["verdict"], "BLOCKED")
        self.assertEqual(self.check(plan=[])["verdict"], "BLOCKED")
        for path in ("../outside.py", "/absolute.py", ".", ".git/config", "folder/../file"):
            plan = copy.deepcopy(self.plan)
            plan["prs"][0]["files"] = [path]
            self.assertEqual(self.check(plan=plan)["verdict"], "BLOCKED")
        path = self.root / "bad.json"
        path.write_text('{"version": 1, "version": 2}')
        output = subprocess.run(["python3", str(SCRIPT), "split", str(path)], capture_output=True, text=True)
        self.assertEqual(output.returncode, 1)
        self.assertIn("duplicate JSON", json.loads(output.stdout)["reason"])

    def test_commands_in_manifest_are_never_executed_or_git_modified(self):
        self.atomic_change()
        self.plan["prs"][0]["tests"] = [f"touch {self.root / 'executed'}"]
        before = self.git("status", "--porcelain"), self.git("rev-parse", "HEAD")
        self.assertEqual(self.check("ship", review=self.review())["verdict"], "PASS")
        self.assertFalse((self.root / "executed").exists())
        self.assertEqual(before, (self.git("status", "--porcelain"), self.git("rev-parse", "HEAD")))

    def test_arbitrary_base_cannot_hide_prior_unmerged_features(self):
        self.write("billing.py", "independent\n")
        intermediate = self.commit()
        self.atomic_change()
        result = self.check("ship", base=intermediate, review=self.review(base=intermediate))
        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertIn("actual merge-base", result["reason"])

    def test_transitive_dependencies_need_merged_evidence(self):
        a, b, c = unit("a"), unit("b"), unit("c")
        b["depends_on"], c["depends_on"] = ["a"], ["b"]
        plan = manifest(a, b, c)
        self.write("b.py", "parent\n")
        b["merged_commit"] = self.commit()
        target = b["merged_commit"]
        self.write("c.py", "child\n")
        self.commit()
        result = self.check("ship", plan=plan, base=target, target=target,
                            review=self.review(plan, base=target))
        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertIn("a: exact merged_commit", result["reason"])


if __name__ == "__main__":
    unittest.main()
