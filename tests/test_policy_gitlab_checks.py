"""Policy-v2 GitLab check receipt coverage."""
import copy
import contextlib
import hashlib
import io
import importlib.util
from pathlib import Path
import unittest
import json
import subprocess
import tempfile
from unittest.mock import patch
from test_gitlab_ci import Transport
from test_project_policy import cloud

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/verify-before-push/scripts'
def load(name):
    spec = importlib.util.spec_from_file_location('_checks_test_' + name, SCRIPTS / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result
p = load('policy_gitlab_ci')
c = load('policy_gitlab_checks')
v = load('verify_before_push')

class MappingV2Tests(unittest.TestCase):
    def test_explicit_v2_maps_enabled_background_checks(self):
        config = dict(checks=[dict(name='unit'), dict(name='slow', required=False)],
                      gitlab_ci=dict(version=2, host='gitlab.example.test', project_id=10,
                                     remote='origin', mr_iid=2, checks=dict(unit=['unit'], slow=['slow'])))
        self.assertEqual(p.validate_gitlab_ci_policy(config), config['gitlab_ci'])

    def test_v2_requires_exact_enabled_catalog_and_unique_jobs(self):
        config = dict(checks=[dict(name='unit'), dict(name='slow', required=False)],
                      gitlab_ci=dict(version=2, host='gitlab.example.test', project_id=10,
                                     remote='origin', mr_iid=2, checks=dict(unit=['unit'], slow=['slow'])))
        for mutate in (lambda d: d['gitlab_ci']['checks'].pop('slow'),
                       lambda d: d['gitlab_ci']['checks'].update(slow=['unit']),
                       lambda d: d['checks'][1].update(required='false'),
                       lambda d: d['checks'][0].update(enabled=False),
                       lambda d: d['gitlab_ci'].update(version=True),
                       lambda d: d['gitlab_ci'].update(extra=True)):
            changed = copy.deepcopy(config)
            mutate(changed)
            with self.assertRaises(p.EvidenceError):
                p.validate_gitlab_ci_policy(changed)

    def test_complete_nul_diff_preserves_rename_deletion_and_type_change(self):
        self.assertEqual(c.parse_changes(b'A\0new.py\0M\0a.py\0D\0gone.py\0R100\0old/a.py\0new/a.py\0T\0link.py\0'), [
            dict(kind='added', old_path=None, new_path='new.py'),
            dict(kind='modified', old_path='a.py', new_path='a.py'),
            dict(kind='deleted', old_path='gone.py', new_path=None),
            dict(kind='renamed', old_path='old/a.py', new_path='new/a.py'),
            dict(kind='type_changed', old_path='link.py', new_path='link.py')])
        for raw in (b'M\0../escape\0', b'C100\0a\0b\0', b'U\0a\0', b'M\0bad\xff\0', b'R100\0a\0', b'M\0a', b'M\0x\\y\0'):
            with self.subTest(raw=raw), self.assertRaises(c.EvidenceError):
                c.parse_changes(raw)
        self.assertEqual(c.parse_changes(b'R050\0app/a.py\0else/a.py\0')[0]['kind'], 'renamed')

    def test_wrapper_v5_summary_reports_background_without_claiming_all_pass(self):
        report = dict(version=5, evaluation=dict(blocking_state='satisfied', background_counts=dict(failed=1)))
        output = io.StringIO()
        with patch.object(p, 'collect_evidence', return_value=report), contextlib.redirect_stdout(output):
            self.assertEqual(p.main(['collect', '--project-root', '.', '--repository', 'application', '--operation', 'push']), 0)
        self.assertIn('satisfied', output.getvalue())
        self.assertIn("'failed': 1", output.getvalue())
        self.assertIn('authorization not granted', output.getvalue())
        self.assertNotIn('PASS', output.getvalue())


class CheckReceiptTests(unittest.TestCase):
    """Own real-Git fixture; deliberately does not inherit the legacy suite."""
    def git(self, *args):
        result = subprocess.run(['git', *args], cwd=self.root, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        return result.stdout.decode().strip()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = (Path(self.temp.name) / 'source').resolve()
        self.root.mkdir()
        self.remote = (Path(self.temp.name) / 'remote.git').resolve()
        self.git('init', '-b', 'feature/test')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.test')
        self.config_path = self.root / '.agents/verify-before-push/config.json'
        self.policy_path = self.root / '.agents/kolabse/project-policy.json'
        self.config_path.parent.mkdir(parents=True)
        self.policy_path.parent.mkdir(parents=True)
        self.config = dict(version=1, repositories=[dict(name='application', path='.', require_clean=True, require_upstream_current=True)],
            checks=[dict(name='unit', command=['DO-NOT-EXECUTE']), dict(name='infra', required=False, command=['DO-NOT-EXECUTE'])],
            gitlab_ci=dict(version=2, host='gitlab.example.test', project_id=10, remote='origin', mr_iid=2,
                           checks=dict(unit=['unit'], infra=['infra'])))
        self.policy = cloud()
        self.policy['schema_version'] = 2
        self.policy['verification'].pop('required_at')
        self.policy['verification']['checks'] = [dict(id='unit', blocks=['merge'], scope=dict(repositories=['application'],
            include_paths=['app/**'], exclude_paths=[], change_types=['added', 'modified', 'deleted', 'renamed', 'type_changed'])),
            dict(id='infra', blocks=[], scope=dict(repositories=['application'], include_paths=['infra/**'],
                exclude_paths=[], change_types=['added', 'modified', 'deleted', 'renamed', 'type_changed']))]
        self.write_config()
        (self.root / '.gitignore').write_text('/.agents/verify-before-push/gitlab-check-evidence.json\n/.agents/verify-before-push/gitlab-ci-evidence.json\n')
        (self.root / 'app').mkdir()
        (self.root / 'app/main.py').write_text('base\n')
        self.git('add', '.')
        self.git('commit', '-m', 'base')
        self.base = self.git('rev-parse', 'HEAD')
        self.git('branch', 'main')
        self.git('clone', '--bare', str(self.root), str(self.remote))
        self.git('remote', 'add', 'origin', 'https://gitlab.example.test/group/project.git')
        self.git('config', 'branch.feature/test.remote', 'origin')
        self.git('config', 'branch.feature/test.merge', 'refs/heads/feature/test')
        (self.root / 'app/main.py').write_text('changed\n')
        (self.root / 'infra').mkdir()
        (self.root / 'infra/main.tf').write_text('infrastructure\n')
        self.transport = Transport()
        self.transport.jobs.append(dict(id=21, name='infra', status='failed', pipeline=dict(id=9, project_id=10, sha=''),
                                       web_url='https://gitlab.example.test/j/21'))
        self.publish()
        self.transport.mr['diff_refs'].update(base_sha=self.base, start_sha=self.base)
        old_get = self.transport.get
        def provider(endpoint):
            if endpoint == 'projects/10':
                return dict(id=10, path_with_namespace='group/project')
            if '/repository/branches/' in endpoint:
                self.transport.calls.append(endpoint)
                return dict(name='main', commit=dict(id=self.base))
            return old_get(endpoint)
        self.transport.get = provider
        real_git = v.git
        def local_git(root, *argv, **kwargs):
            if argv[:1] == ('fetch',):
                if '--no-tags' in argv:
                    argv = ('fetch', '--no-tags', str(self.remote), argv[-1])
                else:
                    argv = ('fetch', '--prune', str(self.remote), '+refs/heads/*:refs/remotes/origin/*')
            if argv[:1] == ('ls-remote',):
                argv = ('ls-remote', '--exit-code', str(self.remote), argv[-1])
            return real_git(root, *argv, **kwargs)
        self.addCleanup(patch.stopall)
        patch.object(v, 'git', side_effect=local_git).start()
        original_sibling = p.sibling
        patch.object(p, 'sibling', side_effect=lambda name: v if name == 'verify_before_push' else original_sibling(name)).start()
        self.no_local = patch.object(v, 'execute_checks', side_effect=AssertionError('local execution forbidden')).start()

    def write_config(self):
        self.config_path.write_text(json.dumps(self.config))
        self.policy_path.write_text(json.dumps(self.policy))

    def publish(self):
        self.git('add', '.')
        self.git('commit', '-m', 'change')
        self.sha = self.git('rev-parse', 'HEAD')
        self.git('push', str(self.remote), 'HEAD:refs/heads/feature/test')
        self.git('update-ref', 'refs/remotes/origin/feature/test', self.sha)
        self.git('update-ref', 'refs/remotes/origin/main', self.base)
        self.transport.mr['sha'] = self.sha
        self.transport.mr['diff_refs']['head_sha'] = self.sha
        self.transport.pipeline['sha'] = self.sha
        for job in self.transport.jobs:
            job['pipeline']['sha'] = self.sha

    def collect(self, **kwargs):
        return p.collect_evidence(self.root, 'application', transport=self.transport, **kwargs)

    def verify(self, **kwargs):
        return p.verify_evidence(self.root, 'application', transport=self.transport, **kwargs)

    def test_mandatory_success_background_failure_is_visible_and_nonblocking(self):
        self.transport.pipeline['status'] = 'failed'
        result = self.collect()
        self.assertEqual(result['version'], 5)
        self.assertEqual(result['evaluation']['blocking_state'], 'satisfied')
        self.assertEqual(result['evaluation']['background_counts']['failed'], 1)
        rows = {r['id']: r for r in result['evaluation']['checks']}
        self.assertEqual((rows['unit']['classification'], rows['unit']['status']), ('mandatory', 'passed'))
        self.assertEqual((rows['infra']['classification'], rows['infra']['status']), ('background', 'failed'))
        self.assertEqual(result['binding']['contract']['required_jobs'], ['unit'])
        self.assertFalse(result['gate_authorized'])
        self.assertEqual(result['authorization'], 'not_granted')
        self.no_local.assert_not_called()

    def test_background_progress_returns_current_report_preserves_stored_receipt(self):
        self.transport.jobs[1]['status'] = 'running'
        result = self.collect()
        path = self.root / c.DEFAULT_EVIDENCE
        original = path.read_bytes()
        self.transport.jobs[1].update(id=22, status='failed', duration=12.5)
        self.transport.pipeline['status'] = 'failed'
        fresh = self.verify()
        self.assertEqual(fresh['evaluation']['background_counts']['failed'], 1)
        self.assertEqual(result['evaluation']['background_counts']['running'], 1)
        self.assertEqual(path.read_bytes(), original)
        self.assertNotEqual(result['receipt_sha256'], fresh['receipt_sha256'])

    def test_background_changes_during_collection_are_not_required_proof(self):
        self.transport.jobs[1]['status'] = 'running'
        seen = [0]
        def progress(transport, endpoint):
            if '/jobs?' in endpoint:
                seen[0] += 1
                if seen[0] == 2:
                    transport.jobs[1].update(id=22, status='failed')
                    transport.pipeline['status'] = 'failed'
        self.transport.mutate = progress
        self.assertEqual(self.collect()['evaluation']['background_counts']['failed'], 1)

    def test_docs_only_complete_inventory_has_no_mandatory_pipeline(self):
        self.git('restore', '--source', self.base, '--', 'app/main.py')
        self.git('rm', 'infra/main.tf')
        (self.root / 'README.md').write_text('documentation\n')
        # Keep the infrastructure deletion outside this check scope.
        self.policy['verification']['checks'][1]['scope']['change_types'] = ['added']
        self.write_config()
        self.publish()
        self.transport.pipelines = []
        result = self.collect()
        self.assertEqual(result['evaluation']['blocking_state'], 'not_required')
        self.assertIsNone(result['evaluation']['checks_satisfied'])
        self.assertIsNone(result['observation']['pipeline'])
        self.assertEqual(result['observation']['pipeline_observation'], 'not_needed')

    def test_renames_and_deletion_use_both_complete_git_endpoints(self):
        self.git('mv', 'app/main.py', 'outside.py')
        self.publish()
        result = self.collect()
        self.assertTrue(result['binding']['applicability']['mandatory_ids'])
        changes = result['binding']['change_inventory']['changes']
        # Content changed since base, so Git may represent this as A+D.
        self.assertTrue(any(r['old_path'] == 'app/main.py' for r in changes))
        self.assertIn('app/main.py', result['binding']['applicability']['check_decisions'][0]['matched_paths'])

    def test_required_retry_and_target_movement_reject_historical_receipt(self):
        self.collect()
        self.transport.jobs[0]['id'] += 1
        with self.assertRaises(p.EvidenceError):
            self.verify()
        self.transport.jobs[0]['id'] -= 1
        self.transport.pipelines.append(dict(id=10))
        with self.assertRaises(p.EvidenceError):
            self.verify()
        self.transport.pipelines.pop()
        self.transport.mr['diff_refs']['base_sha'] = 'c' * 40
        with self.assertRaises(p.EvidenceError):
            self.verify()

    def test_failed_mandatory_and_unknown_coverage_fail_closed(self):
        self.transport.jobs[0]['status'] = 'failed'
        with self.assertRaises(p.EvidenceError):
            self.collect()
        self.transport.jobs[0]['status'] = 'success'
        self.transport.mr['diff_refs']['start_sha'] = 'c' * 40
        with self.assertRaises(p.EvidenceError):
            self.collect()
        self.transport.mr['diff_refs']['start_sha'] = self.base
        (self.root / '.git/shallow').write_text(self.base + '\n')
        with self.assertRaises(p.EvidenceError):
            self.collect()

    def test_policy_catalog_role_and_v1_consumer_cannot_downgrade(self):
        self.config['checks'][0]['required'] = False
        self.write_config()
        self.publish()
        with self.assertRaises(p.EvidenceError):
            self.collect()
        self.config['checks'][0]['required'] = True
        self.config['gitlab_ci'].pop('version')
        self.config['gitlab_ci']['checks'].pop('infra')
        self.write_config()
        self.publish()
        with self.assertRaises(p.EvidenceError):
            self.collect()

    def test_ignored_gitlink_cannot_hide_an_applicable_mandatory_check(self):
        self.policy['verification']['checks'][0]['scope']['include_paths'] = ['infra/module']
        self.write_config()
        (self.root / 'infra/module').mkdir()
        self.git('update-index', '--add', '--cacheinfo', '160000,' + self.base + ',infra/module')
        self.git('config', 'diff.ignoreSubmodules', 'all')
        self.publish()
        result = self.collect()
        self.assertEqual(result['evaluation']['blocking_state'], 'satisfied')
        self.assertTrue(any(row['new_path'] == 'infra/module' for row in result['binding']['change_inventory']['changes']))

    def test_replace_refs_do_not_change_the_sha_bound_inventory(self):
        replacement = self.git('commit-tree', self.git('rev-parse', self.sha + '^{tree}'),
                               '-m', 'local replacement of base tree')
        self.git('replace', self.base, replacement)
        self.assertEqual(self.git('status', '--porcelain'), '')
        result = self.collect()
        self.assertEqual(result['binding']['applicability']['mandatory_ids'], ['unit'])
        self.assertIn({'kind': 'modified', 'old_path': 'app/main.py', 'new_path': 'app/main.py'},
                      result['binding']['change_inventory']['changes'])

    def test_nonmerge_background_only_absence_is_not_required(self):
        self.transport.pipelines = []
        result = self.collect(operation='build')
        self.assertEqual(result['evaluation']['blocking_state'], 'not_required')
        self.assertIsNone(result['evaluation']['checks_satisfied'])
        self.assertEqual(result['observation']['pipeline_observation'], 'absent')
        self.assertEqual(result['evaluation']['background_counts']['not_observed'], 1)
        self.assertEqual(result['binding']['applicability']['deferred_ids'], ['unit'])

    def test_v2_host_config_race_and_foreign_output_fail_before_provider(self):
        self.transport.host = 'foreign.example.test'
        with self.assertRaises(p.EvidenceError):
            self.collect()
        self.assertEqual(self.transport.calls, [])
        del self.transport.host
        stale = copy.deepcopy(self.config)
        stale['gitlab_ci']['host'] = 'stale.example.test'
        original_read = Path.read_bytes
        first = [True]
        def read(path, *args, **kwargs):
            if path == self.config_path and first[0]:
                first[0] = False
                return json.dumps(stale).encode()
            return original_read(path, *args, **kwargs)
        with patch.object(Path, 'read_bytes', read):
            with self.assertRaises(p.EvidenceError):
                self.collect()
        self.assertEqual(self.transport.calls, [])
        for value in ('.git/config', '.agents/verify-before-push/config.json', '../escape.json'):
            with self.subTest(value=value), self.assertRaises(p.EvidenceError):
                self.collect(evidence_file=value)
        path = self.root / c.DEFAULT_EVIDENCE
        path.write_text(json.dumps(dict(version=4, source='gitlab-ci', scope='ci-checks-only')))
        original = path.read_bytes()
        with self.assertRaises(p.EvidenceError):
            self.collect()
        self.assertEqual(path.read_bytes(), original)

    def test_crlf_configuration_and_resealed_invalid_receipt(self):
        self.config_path.write_bytes(json.dumps(self.config, indent=2).replace('\n', '\r\n').encode())
        self.publish()
        result = self.collect()
        self.assertEqual(result['binding']['config_raw_sha256'], hashlib.sha256(self.config_path.read_bytes()).hexdigest())
        path = self.root / c.DEFAULT_EVIDENCE
        result['gate_authorized'] = True
        result['receipt_sha256'] = p.g.digest({k: val for k, val in result.items() if k != 'receipt_sha256'})
        path.write_text(json.dumps(result))
        with self.assertRaises(p.EvidenceError):
            self.verify()

if __name__ == '__main__':
    unittest.main()
