import copy
import importlib.util
import json
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'skills/verify-before-push/scripts/gitlab_ci.py'
spec = importlib.util.spec_from_file_location('gitlab_ci', MODULE)
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)
SHA = 'a' * 40
TARGET = 'b' * 40


def contract():
    return dict(version=1, host='gitlab.example.test', project_id=10, mr_iid=2,
                source_sha=SHA, target_branch='main', subject_kind='source_sha',
                required_jobs=['unit'], require_non_draft=True,
                require_pipeline_success=False, require_ready_at_start=False,
                require_source_review=False, repository='application', profile='final',
                operation='merge', effective_policy_digest='1' * 64,
                source_snapshot_digest='2' * 64, check_map_digest='3' * 64)


class Transport:
    def __init__(self):
        self.calls = []
        self.mr = dict(iid=2, project_id=10, source_project_id=10,
                       target_project_id=10, state='opened', draft=False,
                       sha=SHA, target_branch='main', source_branch='feature/test',
                       diff_refs=dict(head_sha=SHA))
        self.pipeline = dict(id=9, project_id=10, sha=SHA,
                             source='merge_request_event', ref='refs/merge-requests/2/head',
                             status='success', web_url='https://gitlab.example.test/p/9')
        self.jobs = [dict(id=20, name='unit', status='success',
                         pipeline=dict(id=9, project_id=10, sha=SHA),
                         web_url='https://gitlab.example.test/j/20')]
        self.pipelines = [dict(id=9)]
        self.mutate = None

    def get(self, path):
        self.calls.append(path)
        if self.mutate:
            self.mutate(self, path)
        base, _, query = path.partition('?')
        if base.endswith('/merge_requests/2'):
            result = self.mr
        elif '/repository/branches/' in base:
            result = dict(name='main', commit=dict(id=TARGET))
        elif base.endswith('/merge_requests/2/pipelines'):
            page = int(dict(x.split('=') for x in query.split('&'))['page'])
            result = self.pipelines[(page-1)*100:page*100]
        elif base.endswith('/jobs'):
            assert 'include_retried=false' in query
            page = int(dict(x.split('=') for x in query.split('&'))['page'])
            result = self.jobs[(page-1)*100:page*100]
        elif base.endswith('/pipelines/9'):
            result = self.pipeline
        elif base.endswith('/pipelines/10'):
            result = dict(self.pipeline, id=10, status='running')
        else:
            raise AssertionError(path)
        return copy.deepcopy(result)


class CollectorTests(unittest.TestCase):
    def test_success_and_optional_failure(self):
        t = Transport()
        t.jobs.append(dict(id=21, name='background', status='failed',
                           pipeline=dict(id=9, project_id=10, sha=SHA),
                           web_url='https://gitlab.example.test/j/21'))
        t.pipeline['status'] = 'failed'
        result = g.collect(contract(), t)
        self.assertEqual(result['kind'], 'gitlab-ci-observation')
        self.assertEqual(result['pipeline']['id'], 9)
        self.assertEqual(result['target_head'], TARGET)
        self.assertEqual(result['unconfirmed_conditions'], ['ready_at_start', 'source_review'])
        self.assertEqual(len(result['jobs']), 2)
        self.assertEqual(len(result['integrity_digest']), 64)
        self.assertEqual(g.observation_digest(result), result['integrity_digest'])

    def assert_blocked(self, mutate=None, config=None):
        t = Transport()
        if mutate:
            mutate(t)
        with self.assertRaises(g.EvidenceError):
            g.collect(config or contract(), t)

    def test_invalid_mr(self):
        for key, value in [('draft', True), ('state', 'closed'), ('sha', TARGET),
                           ('target_branch', 'other'), ('source_project_id', 11),
                           ('target_project_id', 11), ('project_id', 11), ('diff_refs', {})]:
            with self.subTest(key=key):
                self.assert_blocked(lambda t: t.mr.update({key: value}))

    def test_invalid_pipeline(self):
        for key, value in [('source', 'push'), ('sha', TARGET), ('project_id', 11),
                           ('ref', 'refs/merge-requests/2/merge'), ('ref', 'feature/test')]:
            with self.subTest(key=key, value=value):
                self.assert_blocked(lambda t: t.pipeline.update({key: value}))

    def test_required_job(self):
        for status in ['failed', 'running', 'manual', 'skipped', 'canceled']:
            self.assert_blocked(lambda t: t.jobs[0].update(status=status))
        self.assert_blocked(lambda t: t.jobs.clear())
        self.assert_blocked(lambda t: t.jobs.append(dict(t.jobs[0], id=21)))
        self.assert_blocked(lambda t: t.jobs[0]['pipeline'].update(id=8))
        self.assert_blocked(lambda t: t.jobs[0].update(retried=True))

    def test_unproved_requirements(self):
        for field, value in [('subject_kind', 'merge_result_sha'),
                             ('require_ready_at_start', True), ('require_source_review', True)]:
            self.assert_blocked(config=dict(contract(), **{field: value}))
        self.assert_blocked(lambda t: t.pipeline.update(status='failed'),
                            dict(contract(), require_pipeline_success=True))

    def test_pagination(self):
        t = Transport()
        t.jobs += [dict(t.jobs[0], id=n, name=f'optional-{n}') for n in range(100, 205)]
        t.pipelines = [dict(id=n) for n in range(100, 205)] + [dict(id=9)]
        original_get = t.get
        def get(path):
            if '/pipelines/' in path and not path.split('?')[0].endswith('/jobs') and not path.endswith('/9'):
                return dict(t.pipeline, id=int(path.rsplit('/', 1)[1]), sha=TARGET)
            return original_get(path)
        t.get = get
        result = g.collect(contract(), t)
        self.assertEqual(len(result['jobs']), 106)
        self.assertTrue(any('page=2' in p and '/jobs?' in p for p in t.calls))
        self.assertTrue(any('page=2' in p and '/merge_requests/2/pipelines?' in p for p in t.calls))

    def test_newer_failed_not_cherry_picked(self):
        t = Transport()
        t.pipelines.append(dict(id=10))
        original_get = t.get
        t.get = lambda p: dict(t.pipeline, id=10, status='failed') if p.endswith('/pipelines/10') else original_get(p)
        with self.assertRaises(g.EvidenceError):
            g.collect(dict(contract(), require_pipeline_success=True), t)

    def test_races(self):
        for kind in ['mr', 'target', 'jobs', 'pipeline', 'new_pipeline']:
            t = Transport()
            original_get = t.get
            seen = {}
            def get(path):
                seen[path] = seen.get(path, 0) + 1
                value = original_get(path)
                if seen[path] > 1:
                    if kind == 'mr' and path.endswith('/merge_requests/2'):
                        value['sha'] = TARGET
                    if kind == 'target' and '/repository/branches/' in path:
                        value['commit']['id'] = SHA
                    if kind == 'jobs' and '/jobs?' in path:
                        value[0]['id'] += 1
                    if kind == 'pipeline' and path.endswith('/pipelines/9'):
                        value['status'] = 'running'
                    if kind == 'new_pipeline' and '/merge_requests/2/pipelines?' in path:
                        value.append(dict(id=10))
                return value
            t.get = get
            with self.subTest(kind=kind), self.assertRaises(g.EvidenceError):
                g.collect(contract(), t)

    def test_closed_contract_and_host_injection(self):
        for change in [dict(unknown=True), dict(project_id=True), dict(required_jobs=['unit', 'unit']),
                       dict(host='https://gitlab.test'), dict(host='gitlab.test --help'),
                       dict(host='user:secret@gitlab.test'), dict(host='-evil.test'),
                       dict(source_sha='x'*40), dict(effective_policy_digest='x'*64)]:
            self.assert_blocked(config=dict(contract(), **change))

    def test_duplicate_json_and_sanitized_transport(self):
        with self.assertRaises(g.EvidenceError):
            g.loads_strict('{"version":1,"version":1}')
        with patch.object(g.subprocess, 'run') as run:
            run.return_value = subprocess.CompletedProcess([], 0, '{"ok":true}', '')
            self.assertEqual(g.GlabTransport('gitlab.example.test').get('projects/10/pipelines/9'), {'ok': True})
            argv = run.call_args.args[0]
            self.assertEqual(argv, ['glab', 'api', '--method', 'GET', '--hostname', 'gitlab.example.test', 'projects/10/pipelines/9'])
            run.return_value = subprocess.CompletedProcess([], 1, '', 'secret token')
            with self.assertRaises(g.EvidenceError) as caught:
                g.GlabTransport('gitlab.example.test').get('projects/10/pipelines/9')
            self.assertNotIn('secret', str(caught.exception))
        for path in ['https://evil.test/api/v4/projects/10', '/projects/10', 'projects/10/../x', 'projects/10?token=secret']:
            with self.assertRaises(g.EvidenceError):
                g.GlabTransport('gitlab.example.test').get(path)

    def test_required_unconfirmed_rejects_before_read(self):
        for key in ('require_ready_at_start', 'require_source_review'):
            t = Transport()
            with self.assertRaises(g.EvidenceError):
                g.collect(dict(contract(), **{key: True}), t)
            self.assertEqual(t.calls, [])

    def test_malformed_pagination_and_identity(self):
        for invalid in [None, {}, [dict(id=True)], [dict(id=9), dict(id=9)]]:
            t = Transport()
            original_get = t.get
            t.get = lambda path: invalid if '/merge_requests/2/pipelines?' in path else original_get(path)
            with self.subTest(invalid=invalid), self.assertRaises(g.EvidenceError):
                g.collect(contract(), t)
        self.assert_blocked(lambda t: t.pipeline.update(id=8))
        self.assert_blocked(lambda t: t.jobs[0]['pipeline'].update(project_id=11))
        self.assert_blocked(lambda t: t.jobs[0]['pipeline'].update(sha=TARGET))

    def test_url_sanitization(self):
        for url in ['https://evil.test/p/9', 'https://token@gitlab.example.test/p/9',
                    'https://gitlab.example.test/p/9?private_token=secret',
                    'http://gitlab.example.test/p/9']:
            self.assert_blocked(lambda t: t.pipeline.update(web_url=url))

    def test_cli_changed_contract_and_existing_output(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'contract.json'
            output = Path(folder) / 'observation.json'
            source.write_text(json.dumps(contract()))
            real_collect = g.collect
            def changed(config, transport):
                result = real_collect(config, transport)
                source.write_text(source.read_text() + ' ')
                return result
            with patch.object(g, 'GlabTransport', return_value=Transport()), patch.object(g, 'collect', side_effect=changed):
                self.assertEqual(g.main(['collect', '--contract', str(source), '--output', str(output)]), 1)
            self.assertFalse(output.exists())
            output.write_text('keep')
            with patch.object(g, 'GlabTransport', return_value=Transport()):
                self.assertEqual(g.main(['collect', '--contract', str(source), '--output', str(output)]), 1)
            self.assertEqual(output.read_text(), 'keep')

    def test_cli_success_has_no_gate_authority(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'contract.json'
            output = Path(folder) / 'observation.json'
            source.write_text(json.dumps(contract()))
            with patch.object(g, 'GlabTransport', return_value=Transport()):
                self.assertEqual(g.main(['collect', '--contract', str(source), '--output', str(output)]), 0)
            result = json.loads(output.read_text())
            self.assertEqual(result['authority'], 'observation_only')
            self.assertIn('tracked_remote', result['unproved_bindings'])
            self.assertNotIn('version', result)
            self.assertNotIn('passed', result)

    def test_schema_runtime_representative_parity(self):
        schema = json.loads((MODULE.parents[1] / 'schemas/gitlab-ci-contract.schema.json').read_text())
        self.assertEqual(set(schema['required']), g.CONTRACT_KEYS)
        self.assertEqual(set(schema['properties']), g.CONTRACT_KEYS)
        self.assertFalse(schema['additionalProperties'])
        cases = {
            'host': [('gitlab.example.test', True), ('localhost', True), ('a..b', False),
                     ('a.-b', False), ('a.b-', False), ('https://a', False)],
            'target_branch': [('main', True), ('feature/test', True), ('x'+chr(1), False)],
            'repository': [('application', True), ('x'+chr(0), False)],
            'profile': [('final', True), ('x'+chr(31), False)],
            'source_sha': [(SHA, True), ('x'*40, False)],
        }
        for key, values in cases.items():
            for value, expected in values:
                with self.subTest(key=key, value=value):
                    pattern = schema['properties'][key]['pattern']
                    self.assertEqual(bool(re.fullmatch(pattern, value)), expected)
                    if expected:
                        g.validate_contract(dict(contract(), **{key: value}))
                    else:
                        with self.assertRaises(g.EvidenceError):
                            g.validate_contract(dict(contract(), **{key: value}))
        pattern = schema['properties']['required_jobs']['items']['pattern']
        self.assertTrue(re.fullmatch(pattern, 'unit'))
        self.assertFalse(re.fullmatch(pattern, 'unit'+chr(1)))

    def test_copy_installed_smoke(self):
        with tempfile.TemporaryDirectory() as folder:
            script = Path(folder) / 'gitlab_ci.py'
            script.write_bytes(MODULE.read_bytes())
            result = subprocess.run([sys.executable, str(script), '--help'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('collect', result.stdout)


if __name__ == '__main__':
    unittest.main()
