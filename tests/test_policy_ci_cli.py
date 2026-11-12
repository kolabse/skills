"""The opt-in CI-only route must never fall through to local verification."""
import contextlib
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


SCRIPT = Path(__file__).resolve().parents[1] / 'skills/verify-before-push/scripts/verify_before_push.py'
spec = importlib.util.spec_from_file_location('policy_ci_cli_verifier', SCRIPT)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class PolicyCIRoutingTests(unittest.TestCase):
    def test_config_accepts_explicit_gitlab_mapping(self):
        config = {'version': 1, 'repositories': [{'name': 'application', 'path': '.'}],
                  'checks': [{'name': 'unit', 'command': ['python', '-m', 'unittest']}],
                  'gitlab_ci': {'host': 'gitlab.example.test', 'project_id': 10,
                                'remote': 'origin', 'mr_iid': 2, 'checks': {'unit': ['unit']}}}
        root = Path.cwd().resolve()
        with patch.object(verifier, 'validate_repository_entry', return_value=('application', root, True, True)):
            self.assertEqual(verifier.validate_config_document(config, root, validate_checks=False),
                             root / '.agents/verify-before-push/evidence.json')

    def dispatch(self, delegate):
        provider = SimpleNamespace(main=delegate)
        spec = SimpleNamespace(loader=SimpleNamespace(exec_module=Mock()))
        args = ['policy-ci', 'collect', '--project-root', 'selected-project',
                '--repository', 'application', '--operation', 'merge']
        with patch.object(verifier.importlib.util, 'spec_from_file_location', return_value=spec), \
                patch.object(verifier.importlib.util, 'module_from_spec', return_value=provider), \
                patch.object(verifier, 'run_verification') as local, \
                contextlib.redirect_stderr(io.StringIO()) as error:
            try:
                result = verifier.main(args)
            except SystemExit as exc:
                result = exc.code
            local.assert_not_called()
        return result, args[1:], error.getvalue()

    def test_explicit_ci_route_preserves_context_without_local_execution(self):
        delegate = Mock(return_value=0)
        result, args, _ = self.dispatch(delegate)
        self.assertEqual(result, 0, 'explicit policy CI collection must be supported')
        delegate.assert_called_once_with(args)

    def test_ci_rejection_is_not_replaced_with_local_success(self):
        delegate = Mock(return_value=1)
        result, args, _ = self.dispatch(delegate)
        self.assertEqual(result, 1)
        delegate.assert_called_once_with(args)

    def test_unexpected_adapter_error_blocks_without_exporting_diagnostics(self):
        result, _, error = self.dispatch(Mock(side_effect=RuntimeError('private provider diagnostic')))
        self.assertEqual(result, 1)
        self.assertIn('VERIFICATION_FAILED', error)
        self.assertNotIn('private provider diagnostic', error)


if __name__ == '__main__':
    unittest.main()
