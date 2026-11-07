import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    'detect', Path(__file__).resolve().parents[1] / 'scripts' / 'agentic-detect.py')
detect = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(detect)


def write(root, name, text=''):
    path = Path(root) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class DetectTests(unittest.TestCase):
    def fullstack(self):
        root = tempfile.mkdtemp()
        write(root, 'web/package.json', json.dumps({
            'dependencies': {'react': '1'},
            'scripts': {'test': 'vitest run', 'lint': 'eslint .', 'typecheck': 'tsc --noEmit'}}))
        write(root, 'web/pnpm-lock.yaml')
        write(root, 'api/pyproject.toml', '[tool.pytest.ini_options]\n[tool.ruff]\n')
        write(root, 'api/app/main.py')
        return root

    def test_front_gets_front_checks_only(self):
        result = detect.detect(self.fullstack(), ['web/src/components/A.tsx'])
        self.assertEqual(result['profiles'], ['front'])
        argvs = [c['argv'] for c in result['commands']]
        self.assertIn(['pnpm', '--dir', 'web', 'run', 'test'], argvs)
        self.assertFalse(any(a[0] == 'python3' for a in argvs))

    def test_back_gets_python_checks(self):
        result = detect.detect(self.fullstack(), ['api/app/main.py'])
        self.assertEqual(result['profiles'], ['back'])
        argvs = [c['argv'] for c in result['commands']]
        self.assertIn(['python3', '-m', 'pytest', '-q', 'api'], argvs)

    def test_placeholder_test_script_ignored_and_reported(self):
        root = tempfile.mkdtemp()
        write(root, 'package.json', json.dumps({'scripts': {'test': 'echo "no test specified" && exit 1'}}))
        result = detect.detect(root, ['src/a.js'])
        self.assertEqual(result['commands'], [])
        self.assertTrue(result['missing'])

    def test_docs_only_needs_no_command(self):
        result = detect.detect(self.fullstack(), ['README.md'])
        self.assertEqual(result['profiles'], ['docs'])
        self.assertEqual(result['commands'], [])
        self.assertEqual(result['missing'], [])

    def test_contract_and_data_profiles(self):
        self.assertEqual(detect.profile_of('api/openapi.yaml', set()), 'contract')
        self.assertEqual(detect.profile_of('db/migrations/001.sql', set()), 'data')


if __name__ == '__main__':
    unittest.main()
