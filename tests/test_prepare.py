import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

S = Path(__file__).resolve().parents[1] / 'scripts'
spec = importlib.util.spec_from_file_location('prepare', S / 'agentic-prepare.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


def project():
    root = tempfile.mkdtemp()
    (Path(root) / 'web').mkdir()
    (Path(root) / 'web/package.json').write_text(json.dumps(
        {'dependencies': {'react': '1'}, 'scripts': {'test': 'vitest run'}}))
    return root


class PrepareTests(unittest.TestCase):
    def test_front_ticket_keeps_ui_and_marks_backend_na(self):
        text = prepare.init('T1', ['web/src/components/A.tsx'], project())
        self.assertIn('npm --prefix web run test', text)
        self.assertIn('## BACKEND_SCHEMA\nN/A', text)
        self.assertNotIn('## UX_UI_BRIEF\nN/A', text)

    def test_docs_ticket_marks_ui_na(self):
        text = prepare.init('T2', ['README.md'], project())
        self.assertIn('## UX_UI_BRIEF\nN/A', text)

    def test_fresh_skeleton_is_blocked_until_filled(self):
        result = prepare.check(prepare.init('T3', ['web/src/a.tsx'], project()))
        self.assertEqual(result['verdict'], 'BLOCKED')

    def test_filled_plan_ready_and_blocking_question_blocks(self):
        text = prepare.init('T4', ['README.md'], project())
        text = text.replace('TODO', 'ok').replace('| ok | ok |', '| AC1 | pytest x |')
        text = text.replace('Verdict : DRAFT. Preuves : ok. Blockers : ok.', 'Verdict : DRAFT.')
        self.assertEqual(prepare.check(text)['verdict'], 'READY')
        text = text.replace('|---|---|---|---|\n', '|---|---|---|---|\n| Q ? | oui | ouverte | |\n')
        self.assertEqual(prepare.check(text)['verdict'], 'BLOCKED')

    def test_business_rule_needs_a_unit_test_unless_motivated_exception(self):
        text = prepare.init('T5', ['README.md'], project()).replace('TODO', 'ok')
        text = text.replace('| ok | ok |', '| AC1 | pytest x |', 1).replace('| RM1 | ok | ok |', '| RM1 | règle | |')
        self.assertIn('business rule without unit test: RM1', prepare.check(text)['problems'])
        text = text.replace('| RM1 | règle | |\n', '').replace(
            '## TRD', 'Exception TDD : documentation\n\n## TRD', 1)
        self.assertNotIn('no business rules', ' '.join(prepare.check(text)['problems']))

    def test_units_contract_first_and_trivial(self):
        root = project()
        got = prepare.units(['api/openapi.yaml', 'api/app/main.py', 'web/src/components/A.tsx'], root)
        ids = [u['id'] for u in got]
        self.assertEqual(ids, ['contract', 'back', 'front'])
        self.assertEqual(got[1]['depends_on'], ['contract'])
        self.assertIn('back', got[2]['depends_on'])
        self.assertTrue(prepare.is_trivial(['a.py'], 5, ['back']))
        self.assertFalse(prepare.is_trivial(['a.py'], 5, ['back', 'front']))


if __name__ == '__main__':
    unittest.main()
