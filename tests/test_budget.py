"""Keep the first-read instructions small: every added line costs every agent session."""
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1]
# AGENTS.md has its own budget in test_context.
BUDGETS = {'docs/agentic/README.md': 4000, 'docs/agentic/DELEGATION.md': 6500, 'claude/CLAUDE.md': 100}


class BudgetTests(unittest.TestCase):
    def test_entry_documents_stay_within_their_byte_budget(self):
        for name, limit in BUDGETS.items():
            size = len((SOURCE / name).read_bytes())
            self.assertLessEqual(size, limit, '%s is %d bytes, budget %d' % (name, size, limit))

    def test_local_markdown_links_in_new_documents_resolve(self):
        import re
        for name in ('docs/agentic/DELEGATION.md', 'README.md'):
            base = (SOURCE / name).parent
            for target in re.findall(r'\]\(([^)#\s]+)', (SOURCE / name).read_text()):
                if '://' not in target:
                    self.assertTrue((base / target).exists(), name + ' -> ' + target)


if __name__ == '__main__':
    unittest.main()
