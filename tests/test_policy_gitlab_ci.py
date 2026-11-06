"""Policy-bound GitLab CI receipts: read-only, deliberately not merge authority."""
import copy
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/verify-before-push/scripts'

def load(name):
    spec = importlib.util.spec_from_file_location('_policy_test_' + name, SCRIPTS / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

g = load('gitlab_ci')

class BasePolicyCollectorTests(unittest.TestCase):
    def test_base_policy_contract_is_nullable_and_project_identity_read_is_allowed(self):
        contract = dict(version=1, host='gitlab.example.test', project_id=10, mr_iid=2,
                        source_sha='a'*40, target_branch='main', subject_kind='source_sha',
                        required_jobs=['unit'], require_non_draft=True,
                        require_pipeline_success=True, require_ready_at_start=False,
                        require_source_review=False, repository='application', profile=None,
                        operation='merge', effective_policy_digest='1'*64,
                        source_snapshot_digest='2'*64, check_map_digest='3'*64)
        self.assertIsNone(g.validate_contract(contract)['profile'])
        schema = __import__('json').loads((SCRIPTS.parent / 'schemas/gitlab-ci-contract.schema.json').read_text())
        self.assertIn('null', schema['properties']['profile']['type'])
        with patch.object(g.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '{"id":10}', '')):
            self.assertEqual(g.GlabTransport(contract['host']).get('projects/10'), {'id': 10})


# Receipt integration uses real clean Git repositories and a local bare remote;
# only provider transport and HTTPS routing are replaced by deterministic fixtures.
import json
import tempfile
from test_gitlab_ci import Transport
from test_project_policy import cloud

p = load('policy_gitlab_ci')
v = load('verify_before_push')


class PolicyReceiptTests(unittest.TestCase):
    def git(self, *argv, cwd=None):
        result = subprocess.run(['git', *argv], cwd=cwd or self.root, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        return result.stdout.decode().strip()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        # Git and the consumer resolve aliases such as macOS /var -> /private/var.
        self.root = (Path(self.temp.name) / 'source').resolve()
        self.root.mkdir()
        self.remote = Path(self.temp.name) / 'remote.git'
        self.git('init', '-b', 'feature/test')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.test')
        (self.root / '.agents/kolabse').mkdir(parents=True)
        (self.root / '.agents/verify-before-push').mkdir(parents=True)
        self.config_path = self.root / '.agents/verify-before-push/config.json'
        self.policy_path = self.root / '.agents/kolabse/project-policy.json'
        self.config = dict(version=1, repositories=[dict(name='application', path='.', require_clean=True,
                                                       require_upstream_current=True)],
                           checks=[dict(name='unit', command=['DO-NOT-EXECUTE'])],
                           gitlab_ci=dict(host='gitlab.example.test', project_id=10, remote='origin', mr_iid=2,
                                          checks=dict(unit=['unit'])))
        self.policy = cloud()
        self.config_path.write_text(json.dumps(self.config))
        self.policy_path.write_text(json.dumps(self.policy))
        (self.root / '.gitignore').write_text('/.agents/verify-before-push/gitlab-ci-evidence.json\n')
        self.git('add', '.')
        self.git('commit', '-m', 'fixture')
        self.sha = self.git('rev-parse', 'HEAD')
        self.git('clone', '--bare', str(self.root), str(self.remote))
        self.git('remote', 'add', 'origin', 'https://gitlab.example.test/group/project.git')
        self.git('update-ref', 'refs/remotes/origin/feature/test', self.sha)
        self.git('config', 'branch.feature/test.remote', 'origin')
        self.git('config', 'branch.feature/test.merge', 'refs/heads/feature/test')
        self.transport = Transport()
        self.transport.mr['sha'] = self.sha
        self.transport.mr['diff_refs']['head_sha'] = self.sha
        self.transport.pipeline['sha'] = self.sha
        self.transport.jobs[0]['pipeline']['sha'] = self.sha
        original_get = self.transport.get
        self.transport.get = lambda endpoint: (dict(id=10, path_with_namespace='group/project')
                                              if endpoint == 'projects/10' else original_get(endpoint))
        real_git = v.git
        def local_git(root, *argv, **kwargs):
            if argv[:1] == ('fetch',):
                argv = ('fetch', '--prune', str(self.remote))
            if argv[:1] == ('ls-remote',):
                argv = ('ls-remote', '--exit-code', str(self.remote), argv[-1])
            return real_git(root, *argv, **kwargs)
        self.addCleanup(patch.stopall)
        patch.object(v, 'git', side_effect=local_git).start()
        real_sibling = p.sibling
        patch.object(p, 'sibling', side_effect=lambda name: v if name == 'verify_before_push' else real_sibling(name)).start()
        self.no_local = patch.object(v, 'execute_checks', side_effect=AssertionError('local execution prohibited')).start()

    def collect(self, **kwargs):
        return p.collect_evidence(self.root, 'application', transport=self.transport, **kwargs)

    def verify(self, **kwargs):
        return p.verify_evidence(self.root, 'application', transport=self.transport, **kwargs)

    def commit_configuration(self):
        self.config_path.write_text(json.dumps(self.config))
        self.policy_path.write_text(json.dumps(self.policy))
        self.git('add', '.')
        self.git('commit', '-m', 'configuration')
        self.sha = self.git('rev-parse', 'HEAD')
        self.git('push', str(self.remote), 'HEAD:refs/heads/feature/test')
        self.git('update-ref', 'refs/remotes/origin/feature/test', self.sha)
        self.transport.mr['sha'] = self.sha
        self.transport.mr['diff_refs']['head_sha'] = self.sha
        self.transport.pipeline['sha'] = self.sha
        self.transport.jobs[0]['pipeline']['sha'] = self.sha

    def test_actual_separate_git_metadata_is_never_an_evidence_destination(self):
        import shutil
        metadata = self.root / 'metadata'
        shutil.move(str(self.root / '.git'), str(metadata))
        (self.root / '.git').write_text('gitdir: metadata\n')
        with (metadata / 'info/exclude').open('a') as stream:
            stream.write('\n/metadata/\n')
        with self.assertRaises(p.EvidenceError):
            p.safe_evidence(v, self.root, 'metadata/new-ci-receipt.json')

    def test_transport_host_cannot_come_from_stale_initial_configuration(self):
        stale = copy.deepcopy(self.config)
        stale['gitlab_ci']['host'] = 'stale.example.test'
        original_read = Path.read_bytes
        first = [True]
        def read(path, *args, **kwargs):
            if path == self.config_path and first[0]:
                first[0] = False
                return json.dumps(stale).encode()
            return original_read(path, *args, **kwargs)
        def transport(host):
            self.transport.host = host
            return self.transport
        with patch.object(Path, 'read_bytes', read), patch.object(p.g, 'GlabTransport', side_effect=transport):
            with self.assertRaises(p.EvidenceError):
                p.collect_evidence(self.root, 'application')

    def test_known_injected_transport_host_must_match(self):
        self.transport.host = 'foreign.example.test'
        with self.assertRaises(p.EvidenceError):
            self.collect()

    def test_git_metadata_and_existing_ignored_config_are_preserved(self):
        metadata = self.root / '.git/config'
        old = metadata.read_bytes()
        with (self.root / '.git/info/exclude').open('a') as stream:
            stream.write('\n/.git/config\n/custom-config.json\n')
        custom = self.root / 'custom-config.json'
        custom.write_text('{"some_configuration":true}')
        for value in ('.git/config', 'custom-config.json'):
            with self.subTest(value=value), self.assertRaises(p.EvidenceError):
                self.collect(evidence_file=value)
        self.assertEqual(metadata.read_bytes(), old)
        self.assertEqual(custom.read_text(), '{"some_configuration":true}')

    def test_head_change_during_provider_reads_cannot_create_receipt(self):
        real = self.transport.get
        changed = [False]
        def mutate(endpoint):
            value = real(endpoint)
            if '/jobs?' in endpoint and not changed[0]:
                changed[0] = True
                self.git('commit', '--allow-empty', '-m', 'race')
            return value
        self.transport.get = mutate
        with self.assertRaises((p.EvidenceError, v.VerificationError)):
            self.collect()
        self.assertFalse((self.root / p.DEFAULT_EVIDENCE).exists())

    def test_stable_committed_crlf_configuration_collects_successfully(self):
        self.config_path.write_bytes(json.dumps(self.config, indent=2).replace('\n', '\r\n').encode())
        self.git('add', '.')
        self.git('commit', '-m', 'CRLF configuration')
        self.sha = self.git('rev-parse', 'HEAD')
        self.git('push', str(self.remote), 'HEAD:refs/heads/feature/test')
        self.git('update-ref', 'refs/remotes/origin/feature/test', self.sha)
        self.transport.mr['sha'] = self.sha
        self.transport.mr['diff_refs']['head_sha'] = self.sha
        self.transport.pipeline['sha'] = self.sha
        self.transport.jobs[0]['pipeline']['sha'] = self.sha
        self.assertEqual(self.collect()['binding']['contract']['source_sha'], self.sha)

    def test_clean_source_receipt_recollects_and_grants_only_ci_check_scope(self):
        result = self.collect()
        self.assertEqual(result['version'], 4)
        self.assertEqual(result['scope'], 'ci-checks-only')
        self.assertFalse(result['gate_authorized'])
        self.assertEqual(result['authorization'], 'not_granted')
        self.assertIsNone(result['binding']['profile'])
        self.assertEqual(result['binding']['contract']['source_sha'], self.sha)
        self.assertEqual(result['observation']['unconfirmed_conditions'], ['ready_at_start', 'source_review'])
        self.assertEqual(self.verify(), result)
        self.assertGreaterEqual(self.transport.calls.count('projects/10/merge_requests/2'), 4)
        self.no_local.assert_not_called()
        with self.assertRaises(v.VerificationError):
            v.guard_project_policy(self.root, self.config)

    def test_provider_retry_and_new_pipeline_replace_old_success(self):
        for kind in ('retry', 'pipeline', 'target', 'source_branch', 'project'):
            with self.subTest(kind=kind):
                self.collect()
                original_get = self.transport.get
                old_jobs = copy.deepcopy(self.transport.jobs)
                old_pipelines = copy.deepcopy(self.transport.pipelines)
                if kind == 'retry':
                    self.transport.jobs[0]['id'] += 1
                elif kind == 'pipeline':
                    self.transport.pipelines.append(dict(id=10))
                elif kind == 'source_branch':
                    self.transport.mr['source_branch'] = 'other'
                elif kind == 'project':
                    self.transport.get = lambda endpoint: dict(id=11, path_with_namespace='group/project') if endpoint == 'projects/10' else original_get(endpoint)
                else:
                    def changed(endpoint):
                        value = original_get(endpoint)
                        if '/repository/branches/' in endpoint:
                            value['commit']['id'] = 'c'*40
                        return value
                    self.transport.get = changed
                with self.assertRaises((p.EvidenceError, v.VerificationError)):
                    self.verify()
                self.transport.jobs = old_jobs
                self.transport.pipelines = old_pipelines
                self.transport.mr['source_branch'] = 'feature/test'
                self.transport.get = original_get

    def test_policy_profile_and_operation_bindings(self):
        self.policy['profiles'] = dict(final=dict(version=1, reason='final policy',
            scope=dict(repositories=['application'], operations=['merge']), expires_on='2099-01-01', overrides={}))
        self.commit_configuration()
        self.collect(profile='final')
        with self.assertRaises(p.EvidenceError):
            self.verify()
        with self.assertRaises(p.EvidenceError):
            self.verify(profile='final', operation='push')
        self.assertEqual(self.verify(profile='final')['binding']['profile'], 'final')
        self.policy['profiles']['final']['expires_on'] = '2000-01-01'
        self.policy_path.write_text(json.dumps(self.policy))
        with self.assertRaises((p.EvidenceError, v.VerificationError)):
            self.verify(profile='final')

    def test_remote_identity_and_current_source_are_required(self):
        for option, value in [('remote.origin.pushurl', 'https://gitlab.example.test/other/project.git'),
                              ('remote.origin.url', 'https://secret@gitlab.example.test/group/project.git'),
                              ('remote.origin.url', 'https://gitlab.example.test:443/group/project.git'),
                              ('remote.origin.url', 'https://evil.test/group/project.git'),
                              ('branch.feature/test.pushRemote', 'foreign'),
                              ('branch.feature/test.remote', 'foreign')]:
            with self.subTest(option=option, value=value):
                previous = self.git('config', '--get', option) if option in ('remote.origin.url', 'branch.feature/test.remote') else None
                self.git('config', option, value)
                with self.assertRaises((p.EvidenceError, v.VerificationError)):
                    self.collect()
                self.git('config', '--unset-all', option)
                if previous:
                    self.git('config', option, previous)
        self.git('commit', '--allow-empty', '-m', 'unpublished')
        with self.assertRaises((p.EvidenceError, v.VerificationError)):
            self.collect()

    def test_policy_and_configuration_change_during_reads_fail_closed(self):
        for path in (self.policy_path, self.config_path):
            with self.subTest(path=path):
                old = path.read_text()
                real = self.transport.get
                def mutate(endpoint):
                    result = real(endpoint)
                    if '/jobs?' in endpoint:
                        path.write_text(old + ' ')
                    return result
                self.transport.get = mutate
                with self.assertRaises((p.EvidenceError, v.VerificationError)):
                    self.collect()
                path.write_text(old)
                self.transport.get = real

    def test_remote_change_during_reads_and_wrong_mr_source_fail_closed(self):
        real = self.transport.get
        def mutate(endpoint):
            result = real(endpoint)
            if '/jobs?' in endpoint:
                self.git('config', 'remote.origin.pushurl', 'https://gitlab.example.test/foreign/project.git')
            return result
        self.transport.get = mutate
        with self.assertRaises(p.EvidenceError):
            self.collect()
        self.git('config', '--unset-all', 'remote.origin.pushurl')
        self.transport.get = real
        self.transport.mr['source_branch'] = 'other'
        with self.assertRaises(p.EvidenceError):
            self.collect()

    def test_resealed_malformed_receipt_and_changed_config_cannot_be_authority(self):
        result = self.collect()
        path = self.root / p.DEFAULT_EVIDENCE
        for mutate in (lambda r: r.update(unknown=True),
                       lambda r: r.update(gate_authorized=True),
                       lambda r: r['binding']['config'].update(version=True),
                       lambda r: r['observation']['pipeline'].update(id=True),
                       lambda r: r.update(checked_at='not-a-time')):
            tampered = copy.deepcopy(result)
            mutate(tampered)
            tampered['receipt_sha256'] = g.digest({k: val for k, val in tampered.items() if k != 'receipt_sha256'})
            path.write_text(json.dumps(tampered))
            with self.assertRaises(p.EvidenceError):
                self.verify()
        path.write_text(json.dumps(result))
        self.config['checks'].append(dict(name='new-required', command=['DO-NOT-EXECUTE']))
        self.config_path.write_text(json.dumps(self.config))
        with self.assertRaises((p.EvidenceError, v.VerificationError)):
            self.verify()

    def test_evidence_must_be_ignored_inside_root_and_never_configuration(self):
        for value in ('../escape.json', '.agents/verify-before-push/config.json', '.agents/kolabse/project-policy.json', 'unignored.json'):
            with self.subTest(value=value), self.assertRaises(p.EvidenceError):
                self.collect(evidence_file=value)
        self.assertEqual(json.loads(self.config_path.read_text()), self.config)
        self.assertEqual(json.loads(self.policy_path.read_text()), self.policy)

    def test_policy_invalid_unsupported_and_failed_pipeline_never_fallback(self):
        for mutate in (lambda d: d['verification'].update(reuse_successful_result=False),
                       lambda d: d['verification'].update(subject='merge_result_sha'),
                       lambda d: d['verification'].update(provider='github'),
                       lambda d: d['publication']['pipeline'].update(event='push'),
                       lambda d: d.update(unknown=True)):
            old = copy.deepcopy(self.policy)
            mutate(self.policy)
            self.policy_path.write_text(json.dumps(self.policy))
            with self.assertRaises((p.EvidenceError, v.VerificationError)):
                self.collect()
            self.policy = old
            self.policy_path.write_text(json.dumps(old))
        self.transport.pipeline['status'] = 'failed'
        with self.assertRaises(p.EvidenceError):
            self.collect()
        self.no_local.assert_not_called()


class MappingValidationTests(unittest.TestCase):
    def test_strict_mapping_and_no_missing_new_required_checks(self):
        config = dict(checks=[dict(name='unit')], gitlab_ci=dict(host='gitlab.example.test',
            project_id=10, remote='origin', mr_iid=2, checks=dict(unit=['unit'])))
        self.assertIsNone(p.validate_gitlab_ci_policy({}))
        self.assertEqual(p.validate_gitlab_ci_policy(config), config['gitlab_ci'])
        for change in (lambda c: c['checks'].append(dict(name='new')),
                       lambda c: c['gitlab_ci']['checks'].update(unit=[]),
                       lambda c: c['gitlab_ci']['checks'].update(unit=['unit', 'unit']),
                       lambda c: c['gitlab_ci'].update(project_id=True),
                       lambda c: c['checks'][0].update(enabled=False),
                       lambda c: c['gitlab_ci'].update(unknown=True)):
            changed = copy.deepcopy(config)
            change(changed)
            with self.assertRaises(p.EvidenceError):
                p.validate_gitlab_ci_policy(changed)


if __name__ == '__main__':
    unittest.main()
