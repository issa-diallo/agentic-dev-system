import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location(
    'agentic_brief', Path(__file__).resolve().parents[1] / 'scripts/agentic-brief.py')
BRIEF = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BRIEF)
FENCE = '`' * 3

DELEGATION = {'pr': 'PR1', 'objective': 'Add CSV export', 'acceptance': ['Header row first'],
              'files': ['export.py', 'tests/test_export.py'], 'tests': ['Export behavior tests'],
              'branch': 'feat/export', 'prohibitions': ['Do not merge']}


def reply(body):
    return 'done\n' + FENCE + 'handoff\n' + body + '\n' + FENCE + '\n'


class BriefTests(unittest.TestCase):
    def test_render_is_closed_scope_with_exact_commands(self):
        text = BRIEF.render(DELEGATION, [['python3', '-m', 'unittest', 'tests/x y.py']])
        for expected in ('# Mission PR1', 'Add CSV export', 'Header row first', '- export.py',
                         '- tests/test_export.py', 'feat/export', "`python3 -m unittest 'tests/x y.py'`",
                         'Ne commite pas', 'BLOCKED', FENCE + 'handoff'):
            self.assertIn(expected, text)

    def test_skill_instructions_are_capped(self):
        skill = {'path': '/x/skills/tdd/SKILL.md', 'instructions': 'a' * 500}
        text = BRIEF.render(DELEGATION, None, [skill], max_skill_chars=100)
        self.assertIn('## Instructions : tdd', text)
        self.assertIn('(tronqué)', text)
        self.assertNotIn('a' * 101, text)

    def test_parse_handoff_accepts_valid_reply_and_last_block_wins(self):
        first = '{"status":"BLOCKED","summary":"no"}'
        last = '{"status":"COMPLETED","summary":"yes","files":["a.py"],"tests":[{"command":"t","result":"PASS"}]}'
        parsed = BRIEF.parse_handoff(reply(first) + reply(last))
        self.assertEqual(parsed['status'], 'COMPLETED')
        self.assertEqual(parsed['files'], ['a.py'])
        self.assertEqual(parsed['blockers'], [])

    def test_parse_handoff_rejects_malformed_replies_without_raising(self):
        for bad in (None, 42, 'no block', reply('not json'), reply('[]'),
                    reply('{"status":"DONE"}'), reply('{"status":"COMPLETED","files":"a.py"}'),
                    reply('{"status":"COMPLETED","tests":["x"]}')):
            self.assertIsNone(BRIEF.parse_handoff(bad))

    def test_malformed_last_block_falls_back_to_previous_valid_one(self):
        good = reply('{"status":"COMPLETED","summary":"ok"}')
        self.assertEqual(BRIEF.parse_handoff(good + reply('oops'))['summary'], 'ok')


if __name__ == '__main__':
    unittest.main()
