"""Quality gates detect defects and reject stale or self-approved evidence."""
import copy
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    "quality", Path(__file__).resolve().parents[1] / "scripts/agentic-quality.py")
QUALITY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(QUALITY)


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")
        (self.repo / "value").write_text("correct")
        self.git("add", "value")
        self.git("commit", "-qm", "fixture")
        self.command = [[sys.executable, "-c", "from pathlib import Path; assert Path('value').read_text() == 'correct'"]]

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True)

    def run_checks(self):
        return QUALITY.run_checks(self.repo, self.command)

    def review(self, evidence):
        return {"reviewer": "reviewer", "snapshot": evidence["snapshot"], "verdict": "PASS",
                "findings": [], "evidence": "Real diff examined",
                "runtime_evidence": {"agent_id": "observed-reviewer", "verified_by_orchestrator": True},
                "ci": {"source": "external", "status": "PASS",
                       "head": evidence["snapshot"]["head"], "evidence": "CI run URL"}}

    def test_controlled_defect_blocks_then_correction_reverified(self):
        (self.repo / "value").write_text("defect")
        bad = self.run_checks()
        self.assertEqual(bad["verdict"], "BLOCKED")
        self.assertEqual(QUALITY.assess(self.repo, bad, self.review(bad), "author"), "BLOCKED")
        (self.repo / "value").write_text("correct")
        good = self.run_checks()
        self.assertEqual(QUALITY.assess(self.repo, good, self.review(good), "author"), "PASS")

    def test_stale_after_edit_commit_and_untracked_content(self):
        for change in ("edit", "head", "untracked"):
            evidence = self.run_checks()
            if change == "edit":
                (self.repo / "value").write_text("correct\n")
            elif change == "head":
                self.git("commit", "--allow-empty", "-qm", "new head")
            else:
                (self.repo / "extra").write_text("one")
            self.assertEqual(QUALITY.assess(self.repo, evidence, self.review(evidence), "author"), "BLOCKED")
            (self.repo / "value").write_text("correct")
        evidence = self.run_checks()
        (self.repo / "extra").write_text("two")
        self.assertEqual(QUALITY.assess(self.repo, evidence, self.review(evidence), "author"), "BLOCKED")

    def test_timeout_and_check_that_mutates_workspace_block(self):
        result = QUALITY.run_checks(self.repo, [[sys.executable, "-c", "import time; time.sleep(1)"]], timeout=.01)
        self.assertTrue(result["checks"][0]["timed_out"])
        self.assertEqual(result["verdict"], "BLOCKED")
        result = QUALITY.run_checks(self.repo, [[sys.executable, "-c", "from pathlib import Path; Path('extra').write_text('changed')"]])
        self.assertFalse(result["unchanged"])
        self.assertEqual(result["verdict"], "BLOCKED")

    def test_output_limit_blocks_without_raw_logs(self):
        result = QUALITY.run_checks(self.repo, [[sys.executable, "-c", "print('x' * 2000000)"]])
        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertTrue(result["checks"][0]["output_limit_exceeded"])

    def test_review_independence_major_and_explicit_ci(self):
        evidence = self.run_checks()
        original = self.review(evidence)
        for mutation in ("self", "major", "provenance", "ci"):
            review = copy.deepcopy(original)
            if mutation == "self":
                review["reviewer"] = "author"
            elif mutation == "major":
                review["findings"] = [{"severity": "Major", "status": "OPEN"}]
            else:
                review.pop("runtime_evidence" if mutation == "provenance" else "ci")
            self.assertEqual(QUALITY.assess(self.repo, evidence, review, "author"), "BLOCKED")

    def test_malformed_commands_and_injection_not_interpreted(self):
        for commands in ([], ["echo ok"], [[""]]):
            with self.assertRaises(ValueError):
                QUALITY.run_checks(self.repo, commands)
        secret = "secret-token"
        result = QUALITY.run_checks(self.repo, [[sys.executable, "-c", "import sys; print(sys.argv[1])", secret + "; touch injected"]])
        self.assertFalse((self.repo / "injected").exists())
        self.assertNotIn(secret, str(result))
        self.assertEqual(result["verdict"], "PASS")


if __name__ == "__main__":
    unittest.main()
