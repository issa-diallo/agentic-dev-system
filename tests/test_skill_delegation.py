"""Exercise runner -> scheduler -> brief with offline catalog/store contract fixtures."""
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
ID = 'fixture/copywriting'
DIGEST = 'b' * 64
COMMIT = 'c' * 40
SECRET_BODY = 'fixture body must never be read by the runner'
SELECTOR = '''
def select(task, files, roots, phase='BUILD', *, managed=(), agent=None, needs=()):
    from pathlib import Path
    import json
    Path(__file__).with_name('route.json').write_text(json.dumps(
        dict(task=task, phase=phase, agent=agent, managed=managed, needs=needs)))
    selected = [dict(row, managed=True, role='primary', reasons=['brief'], capability='copywriting')
                for row in managed if agent in row['agents']]
    return dict(phase=phase, selected=selected, library=[], missing_capabilities=[],
                diagnostics=[], loaded=[], applied='NOT_OBSERVED')

def load(path):
    raise AssertionError('managed content must be loaded only by the agent')
'''


class SkillDelegationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.method = self.root / "method with spaces"
        scripts = self.method / 'scripts'
        shutil.copytree(ROOT / 'scripts', scripts, ignore=shutil.ignore_patterns('__pycache__'))
        self.skill_root = self.method / 'skills'
        self.skill_root.mkdir()
        (self.skill_root / 'catalog.json').write_text('{"version":1,"skills":[],"discovery":[]}')
        (scripts / 'agentic-skills.py').write_text(SELECTOR)
        self.store = scripts / 'agentic-skill-store.py'
        row = dict(id=ID, repo='source/fixture', name='Copywriting', agents=['claude', 'codex'],
                   path='skills/copywriting/SKILL.md', commit=COMMIT, extracted_sha256=DIGEST,
                   available=True, enabled=True, installed=True)
        self.store.write_text(
            'from pathlib import Path\n'
            'def inventory(repo, catalog=None):\n'
            '    Path(__file__).with_name("inventory-root").write_text(str(repo))\n'
            f'    return [{row!r}]\n'
            'def load(*args, **kwargs):\n'
            f'    raise AssertionError({SECRET_BODY!r})\n')
        self.route = scripts / 'route.json'
        spec = importlib.util.spec_from_file_location('runner_fixture', scripts / 'agentic-run.py')
        self.run_cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.run_cli)
        self.repo = self.root / 'project'
        subprocess.run(['git', 'init', '-q', '-b', 'main', str(self.repo)], check=True)
        subprocess.run(['git', '-C', str(self.repo), '-c', 'user.name=Test', '-c',
                        'user.email=test@example.invalid', 'commit', '--allow-empty', '-qm', 'base'],
                       check=True)

    def dispatch(self, harness, name='editor', dry_run=True, allowed_tools=None):
        config = self.root / 'agentic.config.json'
        config.write_text(json.dumps({'version': 1, 'models': [
            {'id': 'chosen', 'harness': name, 'model': 'configured', 'max_level': 'MEDIUM',
             'efforts': ['medium'], 'cost_rank': 1}], 'harnesses': {name: harness},
            'run': {} if allowed_tools is None else {'allowed_tools': allowed_tools}}))
        state = self.root / 'state.json'
        report = self.run_cli.quick(
            self.repo, 'ticket', 'Créer une page', ['copy.md'], ['La promesse commerciale est précise'],
            worktree_root=self.root / 'worktrees', config_path=config, state=state,
            dry_run=dry_run, which=lambda binary: binary)
        task = json.loads(state.read_text())['tasks']['ticket']
        self.assertEqual(task['state'], 'COMPLETED', task['blockers'])
        prompt = next((self.repo / '.git' / 'agentic-runs' / 'ticket').glob('*/brief.md')).read_text()
        return task, prompt, report['tasks']['ticket']['result'].get('argv', [])

    def test_alias_resolves_to_actual_cli_and_reference_is_replayable(self):
        task, prompt, _ = self.dispatch({'preset': 'codex'})
        route = json.loads(self.route.read_text())
        self.assertEqual(route['agent'], 'codex')
        self.assertIn('promesse commerciale', route['task'] + ' '.join(route['needs']))
        self.assertEqual(route['phase'], 'BUILD')
        self.assertEqual(Path(self.store.with_name('inventory-root').read_text()).resolve(),
                         Path(task['delegation']['worktree']))
        self.assertEqual([item['id'] for item in task['skills']['selected']], [ID])
        self.assertFalse(task['skills']['loaded'])
        self.assertFalse(task['skills']['applied'])
        command_line = next(line for line in prompt.splitlines() if ' --expect ' in line)
        command = shlex.split(command_line.strip().removeprefix('- ').strip('`'))
        self.assertEqual(command[:6], [str(Path(sys.executable).resolve()), '-I', '-S',
                                       str(self.store), 'load', ID])
        for key, value in [('--repo', task['delegation']['worktree']), ('--agent', 'codex'), ('--expect', DIGEST),
                           ('--commit', COMMIT)]:
            self.assertEqual(command[command.index(key) + 1], value)
        self.assertNotIn(SECRET_BODY, prompt)
        self.assertNotIn('## Instructions : copywriting', prompt)

    def test_child_process_can_request_only_the_referenced_excerpt(self):
        with self.store.open('a') as stream:
            stream.write("if __name__ == '__main__':\n    print('fixture-excerpt-read')\n")
        executable = self.root / 'codex'
        executable.write_text(
            '#!' + sys.executable + '\nimport json,shlex,subprocess,sys\n'
            'from pathlib import Path\n'
            'brief = sys.argv[-1]\n'
            'command = next(line for line in brief.splitlines() if " --expect " in line)\n'
            'message = subprocess.check_output(shlex.split(command), text=True).strip()\n'
            'reply = {"status":"COMPLETED", "summary":message + " from " + str(Path.cwd())}\n'
            'print("```handoff\\n" + json.dumps(reply) + "\\n```")\n')
        executable.chmod(0o700)
        with patch.dict(os.environ, PATH=str(self.root) + os.pathsep + os.environ['PATH']):
            task, prompt, _ = self.dispatch({'preset': 'codex'}, dry_run=False)
        self.assertNotIn('fixture-excerpt-read', prompt)
        self.assertEqual(task['result']['handoff']['summary'],
                         'fixture-excerpt-read from ' + task['delegation']['worktree'])
        self.assertFalse(task['skills']['loaded'])
        self.assertFalse(task['skills']['applied'])

    def simulate_claude_permission_check(self, allowed_tools=None):
        fixture = self.root / 'claude'
        fixture.write_text(
            '#!' + sys.executable + '\nimport json,shlex,subprocess,sys\n'
            'prompt = sys.argv[sys.argv.index("-p")+1]\n'
            'command = next(line for line in prompt.splitlines() if " --expect " in line)\n'
            'rules = sys.argv[sys.argv.index("--allowedTools")+1:]\n'
            'permitted = [r for r in rules if r.startswith("Bash(")]\n'
            'if permitted:\n'
            '    assert permitted == ["Bash(" + command + ")"], permitted\n'
            '    subprocess.run(shlex.split(command), check=True)\n'
            '    summary = "executed permitted load"\n'
            'else:\n'
            '    assert rules == ["Read"], rules\n'
            '    summary = "load denied"\n'
            'reply = {"status":"COMPLETED","summary":summary}\n'
            'print(json.dumps({"result":"```handoff\\n"+json.dumps(reply)+"\\n```"}))\n')
        fixture.chmod(0o700)
        with patch.dict(os.environ, PATH=str(self.root) + os.pathsep + os.environ['PATH']):
            task, prompt, _ = self.dispatch({'preset': 'claude'}, dry_run=False,
                                            allowed_tools=allowed_tools)
        self.assertIn('--agent claude', prompt)
        self.assertFalse(task['skills']['loaded'])
        self.assertFalse(task['skills']['applied'])
        return task['result']['handoff']['summary']

    def test_claude_default_permits_only_the_exact_read_for_this_project(self):
        self.assertEqual(self.simulate_claude_permission_check(), 'executed permitted load')

    def test_explicit_claude_tools_are_preserved_without_granting_load(self):
        self.assertEqual(self.simulate_claude_permission_check(['Read']), 'load denied')

    def test_wildcard_in_method_path_never_enters_claude_permission_rule(self):
        moved = self.root / 'method (*)'
        self.method.rename(moved)
        script = moved / 'scripts/agentic-run.py'
        spec = importlib.util.spec_from_file_location('unusual_runner', script)
        self.run_cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.run_cli)
        _, prompt, argv = self.dispatch({'preset': 'claude'})
        self.assertIn("method (*)", prompt)
        self.assertFalse(any(arg.startswith('Bash(') for arg in argv))

    def test_symlinked_store_code_is_not_imported_or_authorized(self):
        elsewhere = self.root / 'untrusted.py'
        elsewhere.write_text("raise AssertionError('unexpected import of linked store')\n")
        self.store.unlink()
        self.store.symlink_to(elsewhere)
        task, prompt, argv = self.dispatch({'preset': 'claude'})
        self.assertFalse(task['skills']['selected'])
        self.assertNotIn(' --expect ', prompt)
        self.assertFalse(any(arg.startswith('Bash(') for arg in argv))

    def test_rule_refuses_writer_controlled_interpreter_or_script(self):
        inside = self.repo / 'local-code'
        outside = self.root / 'trusted-code'
        inside.touch()
        outside.touch()
        for python, script in [(str(inside), str(outside)), (str(outside), str(inside))]:
            with self.subTest(python=python, script=script):
                argv = [python, '-I', '-S', script, 'load', ID, '--repo', str(self.root),
                        '--agent', 'claude', '--expect', DIGEST, '--commit', COMMIT]
                self.assertIsNone(self.run_cli.claude_skill_rule(argv, self.repo))

    def test_argv_named_codex_does_not_inherit_capabilities(self):
        task, prompt, _ = self.dispatch({'argv': [sys.executable, '{prompt}']}, name='codex')
        self.assertFalse(task['skills']['selected'])
        self.assertNotIn(' --expect ', prompt)

    def test_inline_review_suppresses_skills_and_ordinary_ship_receives_actual_phase(self):
        config = {'models': [{'id': 'real', 'harness': 'codex', 'model': 'fixed',
                              'max_level': 'HIGH', 'efforts': ['high'], 'cost_rank': 1}]}
        inventory, _ = self.run_cli.build_inventory(config, which=lambda binary: binary)
        scheduler = self.run_cli.module('scheduler').Scheduler(
            self.root / 'plan', self.repo, skill_roots=[str(self.skill_root)], models=inventory)
        unit = {'routing': {'phase': 'SHIP', 'role': 'reviewer'}}
        ticket = dict(pr='review', objective='Examiner une page', files=['copy.md'],
                      acceptance=['Promesse commerciale'], worktree=str(self.repo))
        sealed = scheduler._context({**ticket, 'review_context': {'diff': 'inline'}}, unit)
        self.assertFalse(sealed['skills']['selected'])
        self.assertFalse(self.route.exists())
        ordinary = scheduler._context(ticket, unit)
        self.assertEqual(json.loads(self.route.read_text())['phase'], 'SHIP')
        self.assertEqual(ordinary['skills']['selected'][0]['id'], ID)

    def test_legacy_method_without_managed_resources_uses_original_route(self):
        self.store.unlink()
        (self.skill_root / 'catalog.json').unlink()
        self.store.with_name('agentic-skills.py').write_text(
            "def select(task, files, roots, phase='BUILD'):\n"
            "    return {'selected': [], 'loaded': [], 'applied': 'NOT_OBSERVED'}\n")
        task, prompt, _ = self.dispatch({'preset': 'codex'})
        self.assertFalse(task['skills']['selected'])
        self.assertNotIn(' --expect ', prompt)
