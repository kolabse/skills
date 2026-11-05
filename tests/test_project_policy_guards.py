"""Focused policy/legacy boundaries; no real check commands or provider calls."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from test_project_policy import standard, cloud

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/verify-before-push/scripts'


def load(path):
    spec = importlib.util.spec_from_file_location('isolated_guard_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PolicyGuardTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.verifier = load(SCRIPTS / 'verify_before_push.py')
        self.receipt = self.root / 'receipt.json'
        self.config = {'repositories': [{'name': 'app', 'path': '.'}], 'checks': []}
        self.context = (self.config, self.config, self.root, self.receipt, 'binding')
        for name, value in {
            'load_execution_context': self.context, 'validate_config_document': None,
            'refresh_required_upstreams': None, 'capture_states': [], 'reuse_identity': None,
            'execute_checks': [], 'validate_github_ci_policy': {}, 'collect_github_ci': {},
            'github_ci_results': [], 'validate_receipt': None,
            'validate_github_ci_receipt': None,
            'validate_repository_entry': ('app', self.root, True, True),
        }.items():
            mocked = self.enterContext(patch.object(self.verifier, name, return_value=value))
            setattr(self, name, mocked)

    def write_policy(self, value):
        path = self.root / '.agents/kolabse/project-policy.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value if isinstance(value, str) else json.dumps(value), encoding='utf-8')

    def test_no_policy_preserves_all_legacy_receipt_versions(self):
        self.verifier.run_verification(self.root)
        self.assertEqual(set(json.loads(self.receipt.read_text())),
                         {'version', 'config_sha256', 'checked_at', 'repositories', 'checks'})
        self.assertEqual(json.loads(self.receipt.read_text())['version'], 1)
        self.receipt.unlink()
        self.reuse_identity.return_value = {'fixture': 'identity'}
        self.verifier.run_verification(self.root)
        self.assertEqual(json.loads(self.receipt.read_text())['version'], 2)
        self.assertTrue(self.verifier.verify_evidence(self.root))
        self.receipt.unlink()
        self.verifier.run_github_ci_verification(self.root)
        self.assertEqual(set(json.loads(self.receipt.read_text())),
                         {'version', 'source', 'config_sha256', 'checked_at', 'repositories',
                          'checks', 'github_ci', 'receipt_sha256'})
        self.assertTrue(self.verifier.verify_evidence(self.root))

    def test_present_policy_blocks_before_check_or_provider(self):
        for policy in ('{', standard(), cloud(), dict(standard(), schema_version=999)):
            for run in (self.verifier.run_verification, self.verifier.run_github_ci_verification):
                with self.subTest(policy=policy, run=run.__name__):
                    self.write_policy(policy)
                    with self.assertRaisesRegex(self.verifier.VerificationError, 'Project policy'):
                        run(self.root)
        self.execute_checks.assert_not_called()
        self.collect_github_ci.assert_not_called()
        self.refresh_required_upstreams.assert_not_called()

    def test_explicit_local_cli_cannot_override_ci_only(self):
        self.write_policy(cloud())
        self.assertEqual(self.verifier.main(['run', '--project-root', str(self.root), '--source', 'local']), 1)
        self.execute_checks.assert_not_called()

    def test_old_receipt_cannot_satisfy_configured_contract(self):
        self.verifier.run_verification(self.root)
        self.write_policy(standard())
        with self.assertRaisesRegex(self.verifier.VerificationError, 'Project policy'):
            self.verifier.verify_evidence(self.root)
        self.validate_receipt.assert_not_called()

    def test_policy_appearing_during_local_checks_prevents_receipt(self):
        self.execute_checks.side_effect = lambda *a, **k: (self.write_policy(cloud()) or [])
        with self.assertRaisesRegex(self.verifier.VerificationError, 'Project policy'):
            self.verifier.run_verification(self.root)
        self.assertFalse(self.receipt.exists())

    def test_policy_appearing_after_first_command_blocks_second_command(self):
        # Exercise the actual executor with its own module globals and a harmless fake subprocess.
        executor_module = load(SCRIPTS / 'verify_before_push.py')
        config = {'repositories': [{'name': 'app', 'path': '.'}], 'checks': [
            {'name': 'one', 'command': ['fixture']}, {'name': 'two', 'command': ['fixture']}]}
        def first_command(*args, **kwargs):
            self.write_policy(cloud())
            return subprocess.CompletedProcess(args, 0, b'', b'')
        with patch.object(executor_module, 'run_process', side_effect=first_command) as process, \
             patch.object(executor_module, 'validate_repository_entry', return_value=('app', self.root, True, True)):
            with self.assertRaisesRegex(executor_module.VerificationError, 'Project policy'):
                executor_module.execute_checks(config, self.root)
            self.assertEqual(process.call_count, 1)

    def test_policy_appearing_during_ci_collection_prevents_receipt(self):
        self.collect_github_ci.side_effect = lambda *a, **k: (self.write_policy(cloud()) or {})
        with self.assertRaisesRegex(self.verifier.VerificationError, 'Project policy'):
            self.verifier.run_github_ci_verification(self.root)
        self.assertFalse(self.receipt.exists())

    def test_policy_appearing_during_receipt_acceptance_blocks_all_versions(self):
        for version, validator in ((1, self.validate_receipt), (2, self.validate_receipt),
                                   (3, self.validate_github_ci_receipt)):
            with self.subTest(version=version):
                path = self.root / '.agents/kolabse/project-policy.json'
                path.unlink(missing_ok=True)
                self.receipt.write_text(json.dumps({'version': version}))
                validator.side_effect = lambda *a, **k: self.write_policy(cloud())
                with self.assertRaisesRegex(self.verifier.VerificationError, 'Project policy'):
                    self.verifier.verify_evidence(self.root)
                validator.side_effect = None

    def test_policy_appearing_during_reuse_blocks_local_and_ci(self):
        for run, validator in ((self.verifier.run_verification, self.validate_receipt),
                               (self.verifier.run_github_ci_verification, self.validate_github_ci_receipt)):
            with self.subTest(run=run.__name__):
                (self.root / '.agents/kolabse/project-policy.json').unlink(missing_ok=True)
                self.receipt.write_text('{}')
                self.reuse_identity.return_value = {'fixture': 'identity'}
                validator.side_effect = lambda *a, **k: self.write_policy(cloud())
                with self.assertRaisesRegex(self.verifier.VerificationError, 'Project policy'):
                    run(self.root)
                self.assertFalse(self.receipt.exists())
                validator.side_effect = None

    def test_unrelated_repository_gate_still_bypasses_policy(self):
        self.write_policy('{')
        with patch.object(self.verifier, 'git_root', return_value=self.root / 'unrelated'):
            self.assertFalse(self.verifier.verify_evidence(self.root, self.root / 'unrelated'))
        self.refresh_required_upstreams.assert_not_called()

    def test_workspace_mapping_does_not_hide_canonical_policy(self):
        mapped = self.root / 'mapped'
        mapped.mkdir()
        self.load_execution_context.return_value = (self.config, self.config, mapped, self.receipt, 'binding')
        self.write_policy(cloud())
        with self.assertRaisesRegex(self.verifier.VerificationError, 'Project policy'):
            self.verifier.run_verification(self.root, workspace_map=self.root / 'map.json')
        self.execute_checks.assert_not_called()

    def test_explicit_repository_policy_blocks_parent_project_checks(self):
        child = self.root / 'app'
        policy = child / '.agents/kolabse/project-policy.json'
        policy.parent.mkdir(parents=True)
        policy.write_text(json.dumps(cloud()))
        self.config['repositories'][0]['path'] = 'app'
        with self.assertRaisesRegex(self.verifier.VerificationError, 'Project policy'):
            self.verifier.run_verification(self.root)
        self.execute_checks.assert_not_called()
        self.refresh_required_upstreams.assert_not_called()

    def test_map_preserves_source_repository_policy_and_effective_repository_policy(self):
        source = {'repositories': [{'name': 'app', 'path': 'source-app'}], 'checks': []}
        effective = {'repositories': [{'name': 'app', 'path': 'mapped-app'}], 'checks': []}
        workspace = self.root / 'workspace'
        workspace.mkdir()
        self.load_execution_context.return_value = (source, effective, workspace, self.receipt, 'binding')
        for owner in (self.root / 'source-app', workspace / 'mapped-app'):
            with self.subTest(owner=owner.name):
                policy = owner / '.agents/kolabse/project-policy.json'
                policy.parent.mkdir(parents=True)
                policy.write_text(json.dumps(cloud()))
                with self.assertRaisesRegex(self.verifier.VerificationError, 'Project policy'):
                    self.verifier.run_verification(self.root, workspace_map=self.root / 'map.json')
                policy.unlink()
        self.execute_checks.assert_not_called()

    def test_unsafe_or_broken_policy_parent_link_is_not_absence(self):
        for name in ('outside', 'missing'):
            with self.subTest(name=name):
                selected = self.root / name
                selected.mkdir()
                target = self.root / (name + '-target')
                if name == 'outside':
                    target.mkdir()
                try:
                    os.symlink(target, selected / '.agents', target_is_directory=True)
                except OSError as error:
                    if os.name != 'nt':
                        self.skipTest('Directory symlinks unavailable: ' + str(error))
                    target.mkdir(exist_ok=True)
                    result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(selected / '.agents'), str(target)],
                                            capture_output=True)
                    if result.returncode:
                        self.skipTest('Directory links unavailable')
                    if name == 'missing':
                        target.rmdir()
                with self.assertRaisesRegex(self.verifier.VerificationError, 'Project policy'):
                    self.verifier.guard_project_policy(selected)

    def test_installed_copy_imports_without_checkout_or_sys_path_hacks(self):
        installed = self.root / 'installed'
        shutil.copytree(SCRIPTS.parent, installed)
        self.verifier = load(installed / 'scripts/verify_before_push.py')
        self.write_policy(cloud())
        with patch.object(self.verifier, 'load_execution_context', return_value=self.context):
            with self.assertRaisesRegex(self.verifier.VerificationError, 'Project policy'):
                self.verifier.run_verification(self.root)

    def test_standalone_legacy_copy_only_requires_guard_when_policy_present(self):
        standalone = self.root / 'verify_before_push.py'
        shutil.copyfile(SCRIPTS / 'verify_before_push.py', standalone)
        copied = load(standalone)
        # The no-policy legacy path must not import absent sibling modules.
        with patch.object(copied, 'load_execution_context', return_value=self.context), \
             patch.object(copied, 'validate_config_document', side_effect=RuntimeError('legacy path')):
            with self.assertRaisesRegex(RuntimeError, 'legacy path'):
                copied.run_verification(self.root)
            self.write_policy(cloud())
            with self.assertRaisesRegex(copied.VerificationError, 'Project policy'):
                copied.run_verification(self.root)


class OperationPlanTests(unittest.TestCase):
    def test_pure_plan_keeps_action_separate_and_never_authorizes_configured_execution(self):
        planner = load(SCRIPTS / 'project_policy_plan.py')
        for status in ('configured', 'invalid'):
            report = {'status': status, 'repository': 'app', 'operation': 'push',
                      'active_profile': None, 'effective_digest': 'policy',
                      'source_snapshot_digest': 'snapshot', 'dependent_action_blockers': {}}
            plan = planner.plan_operation(report, repository='app', operation='push', action='collect_ci')
            self.assertEqual(plan['decision'], 'blocked')
            self.assertEqual(plan['action'], 'collect_ci')
            self.assertEqual(plan['operation'], 'push')
            self.assertEqual(plan['provider_confirmation'], 'unconfirmed')
        report['status'] = 'absent'
        self.assertEqual(planner.plan_operation(report, repository='app', operation='push',
                                               action='execute_local_check')['decision'], 'legacy')


if __name__ == '__main__':
    unittest.main()
