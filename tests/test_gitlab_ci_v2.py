import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'skills/verify-before-push/scripts/gitlab_ci.py'
spec = importlib.util.spec_from_file_location('collector_v2_baseline', ROOT / 'tests/test_gitlab_ci.py')
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)
g = baseline.g
SHA, TARGET = baseline.SHA, baseline.TARGET
BASE, START = 'c' * 40, 'd' * 40


def contract(**changes):
    result = dict(baseline.contract(), version=2, observed_jobs=['unit', 'background'],
                  target_head=TARGET, diff_base_sha=BASE, diff_start_sha=START,
                  applicability_digest='4' * 64)
    result.update(changes)
    return result


class Transport(baseline.Transport):
    def __init__(self):
        super().__init__()
        self.mr['diff_refs'].update(base_sha=BASE, start_sha=START)
        self.pipeline['status'] = 'failed'
        self.jobs.append(dict(id=21, name='background', status='failed',
                              pipeline=dict(id=9, project_id=10, sha=SHA),
                              web_url='https://gitlab.example.test/j/21'))


class CollectorV2Tests(unittest.TestCase):
    def test_failed_background_preserves_mandatory_success(self):
        result = g.collect(contract(), Transport())
        self.assertEqual(result['observation_version'], 2)
        self.assertEqual(result['pipeline']['status'], 'failed')
        self.assertEqual(result['jobs'][1]['status'], 'failed')
        self.assertEqual(result['authority'], 'observation_only')
        self.assertEqual(result['pipeline_observation'], 'observed')
        self.assertNotIn('passed', result)

    def test_mr_context_is_normalized_and_provenance_bound(self):
        t = Transport()
        t.mr.update(updated_at='later', detailed_merge_status='ci_still_running',
                    pipeline=dict(id=100, status='running'))
        t.mr['diff_refs']['unrelated'] = 'ignored'
        result = g.read_mr_context(t, **{key: contract()[key] for key in
            ('host', 'project_id', 'mr_iid', 'source_sha', 'target_branch', 'require_non_draft')})
        self.assertEqual(set(result), {'mr', 'target_head'})
        self.assertEqual(set(result['mr']), g.MR_KEYS)
        self.assertEqual(set(result['mr']['diff_refs']), {'base_sha', 'start_sha', 'head_sha'})
        for field in ('base_sha', 'start_sha', 'head_sha'):
            bad = Transport()
            bad.mr['diff_refs'][field] = 'invalid'
            with self.subTest(field=field), self.assertRaises(g.EvidenceError):
                g.collect(contract(), bad)
        for change in (dict(target_head=SHA), dict(diff_base_sha=SHA), dict(diff_start_sha=SHA)):
            with self.subTest(change=change), self.assertRaises(g.EvidenceError):
                g.collect(contract(**change), Transport())

    def test_required_statuses_missing_duplicate_and_identity_fail_closed(self):
        for status in ('failed', 'pending', 'running', 'manual', 'skipped', 'canceled', 'unknown'):
            t = Transport()
            t.jobs[0]['status'] = status
            with self.subTest(status=status), self.assertRaises(g.EvidenceError):
                g.collect(contract(), t)
        mutations = [lambda t: t.jobs.pop(0),
                     lambda t: t.jobs.append(dict(t.jobs[0], id=22)),
                     lambda t: t.jobs[1]['pipeline'].update(project_id=True),
                     lambda t: t.jobs[1].update(id=True),
                     lambda t: t.jobs[1].update(retried=True),
                     lambda t: t.pipeline.update(project_id=True),
                     lambda t: t.mr.update(source_project_id=11),
                     lambda t: t.pipeline.update(ref='refs/merge-requests/2/merge')]
        for mutate in mutations:
            t = Transport()
            mutate(t)
            with self.assertRaises(g.EvidenceError):
                g.collect(contract(), t)

    def test_pipeline_status_is_observation_only(self):
        for status in ('failed', 'canceled', 'running', 'pending', 'manual', 'skipped'):
            t = Transport()
            t.pipeline['status'] = status
            result = g.collect(contract(), t)
            self.assertEqual(result['pipeline']['status'], status)

    def test_optional_background_details_and_unknown_status_retained(self):
        t = Transport()
        t.jobs[1].update(status='provider_future_state', duration=0.5, started_at='2026-01-01T00:00:00Z',
                         finished_at=None)
        result = g.collect(contract(), t)
        self.assertEqual(result['jobs'][1]['status'], 'provider_future_state')
        self.assertEqual(result['jobs'][1]['duration'], 0.5)
        self.assertIsNone(result['jobs'][1]['finished_at'])
        for duration in (True, -1, float('nan'), float('inf'), '1'):
            t.jobs[1]['duration'] = duration
            with self.subTest(duration=duration), self.assertRaises(g.EvidenceError):
                g.collect(contract(), t)

    def changing_transport(self, mutate):
        t = Transport()
        original = t.get
        mr_reads = 0
        def get(path):
            nonlocal mr_reads
            if path.endswith('/merge_requests/2'):
                mr_reads += 1
                if mr_reads == 2:
                    mutate(t)
            return original(path)
        t.get = get
        return t

    def test_background_progress_retry_and_global_status_do_not_change_binding(self):
        def mutate(t):
            t.pipeline['status'] = 'running'
            t.jobs[1].update(id=99, status='running', duration=3)
            t.mr.update(updated_at='later', pipeline=dict(id=9, status='running'))
        result = g.collect(contract(), self.changing_transport(mutate))
        self.assertEqual(result['pipeline']['status'], 'running')
        self.assertEqual(result['jobs'][1]['id'], 99)
        self.assertEqual(result['jobs'][1]['status'], 'running')

    def test_required_retry_new_latest_pipeline_and_mr_movement_invalidate(self):
        mutations = [lambda t: t.jobs[0].update(id=99),
                     lambda t: t.pipelines.append(dict(id=10)),
                     lambda t: t.mr.update(source_branch='other'),
                     lambda t: t.mr['diff_refs'].update(base_sha=TARGET)]
        for mutate in mutations:
            with self.assertRaises(g.EvidenceError):
                g.collect(contract(), self.changing_transport(mutate))

    def test_empty_required_no_pipeline_has_explicit_absence(self):
        for observed, expected in (([], 'not_needed'), (['background'], 'absent')):
            t = Transport()
            t.pipelines = []
            result = g.collect(contract(required_jobs=[], observed_jobs=observed), t)
            self.assertIsNone(result['pipeline'])
            self.assertEqual(result['jobs'], [])
            self.assertEqual(result['pipeline_observation'], expected)
            self.assertEqual(len(g.binding_key(result)), 64)
        t = Transport()
        t.pipelines = []
        with self.assertRaises(g.EvidenceError):
            g.collect(contract(), t)

    def test_empty_required_pipeline_appearing_or_disappearing_is_not_required(self):
        t = self.changing_transport(lambda t: t.pipelines.append(dict(id=9)))
        t.pipelines = []
        result = g.collect(contract(required_jobs=[], observed_jobs=['background']), t)
        self.assertEqual(result['pipeline_observation'], 'observed')
        self.assertEqual(result['pipeline']['status'], 'failed')
        t = self.changing_transport(lambda t: t.pipelines.clear())
        result = g.collect(contract(required_jobs=[], observed_jobs=['background']), t)
        self.assertEqual(result['pipeline_observation'], 'absent')

    def test_strict_contract_versions_flags_and_closed_fields(self):
        changes = [dict(version=True), dict(version=3), dict(extra=True),
                   dict(require_pipeline_success=True), dict(require_non_draft=1),
                   dict(required_jobs=['unit', 'unit']), dict(observed_jobs=['background']),
                   dict(observed_jobs=['unit', 'unit']), dict(target_head=True),
                   dict(applicability_digest='x' * 64), dict(repository=' '),
                   dict(host='https://gitlab.example.test'), dict(host='gitlab.test --help'),
                   dict(require_ready_at_start=True), dict(require_source_review=True)]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(g.EvidenceError):
                g.validate_contract(contract(**change))
        with self.assertRaises(g.EvidenceError):
            g.validate_contract(dict(baseline.contract(), required_jobs=[]))

    def test_unsafe_urls_fail_even_for_background(self):
        for url in ('https://evil.test/job/21', 'https://token@gitlab.example.test/j/21',
                    'https://gitlab.example.test/j/21?token=secret', 'http://gitlab.example.test/j/21'):
            t = Transport()
            t.jobs[1]['web_url'] = url
            with self.assertRaises(g.EvidenceError):
                g.collect(contract(), t)

    def test_provider_whitespace_identity_rejected(self):
        for field in ('name', 'status'):
            t = Transport()
            t.jobs[1][field] = ' '
            with self.subTest(field=field), self.assertRaises(g.EvidenceError):
                g.collect(contract(), t)
        t = Transport()
        t.mr['source_branch'] = ' '
        with self.assertRaises(g.EvidenceError):
            g.collect(contract(), t)

    def test_binding_rejects_malformed_and_boolean_identity_even_resealed(self):
        result = g.collect(contract(), Transport())
        mutations = [lambda r: r.update(observation_version=True),
                     lambda r: r['mr'].update(iid=True),
                     lambda r: r['pipeline'].update(id=True),
                     lambda r: r['jobs'][0].update(id=True),
                     lambda r: r.update(relevant_pipeline_ids=[True]),
                     lambda r: r.update(pipeline_observation='absent'),
                     lambda r: r.update(authority='authorized'),
                     lambda r: r.update(extra=True)]
        for mutate in mutations:
            changed = copy.deepcopy(result)
            mutate(changed)
            changed['integrity_digest'] = g.observation_digest(changed)
            with self.assertRaises(g.EvidenceError):
                g.binding_key(changed)

    def test_binding_ignores_only_background_proof(self):
        result = g.collect(contract(), Transport())
        key = g.binding_key(result)
        changed = copy.deepcopy(result)
        changed['jobs'][1].update(id=999, status='success', duration=100)
        changed['jobs'][0]['duration'] = 999
        changed['pipeline']['status'] = 'success'
        changed['integrity_digest'] = g.observation_digest(changed)
        self.assertEqual(key, g.binding_key(changed))
        changed['jobs'][0]['id'] = 19
        changed['integrity_digest'] = g.observation_digest(changed)
        self.assertNotEqual(key, g.binding_key(changed))

    def test_pagination_reads_all_current_jobs_and_pipelines(self):
        t = Transport()
        t.jobs += [dict(t.jobs[1], id=n, name=f'outside-{n}') for n in range(100, 205)]
        t.pipelines = [dict(id=n) for n in range(100, 205)] + [dict(id=9)]
        original = t.get
        def get(path):
            if '/pipelines/' in path and not path.split('?')[0].endswith('/jobs') and not path.endswith('/9'):
                return dict(t.pipeline, id=int(path.rsplit('/', 1)[1]), sha=TARGET)
            return original(path)
        t.get = get
        result = g.collect(contract(), t)
        self.assertEqual(len(result['jobs']), 107)
        self.assertTrue(any('page=2' in path and '/jobs?' in path for path in t.calls))
        self.assertTrue(any('page=2' in path and '/merge_requests/2/pipelines?' in path for path in t.calls))

    def test_schema_keys_and_explicit_version(self):
        schema = json.loads((MODULE.parents[1] / 'schemas/gitlab-ci-contract-v2.schema.json').read_text())
        self.assertEqual(set(schema['required']), g.CONTRACT_V2_KEYS)
        self.assertEqual(set(schema['properties']), g.CONTRACT_V2_KEYS)
        self.assertEqual(schema['properties']['version']['const'], 2)
        self.assertEqual(schema['properties']['require_pipeline_success']['const'], False)
        self.assertFalse(schema['additionalProperties'])


if __name__ == '__main__':
    unittest.main()
