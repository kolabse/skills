"""Version-two check applicability and result contracts."""
import copy
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/verify-before-push/scripts'

def module(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value

POLICY = module('project_policy')
PLAN = module('project_policy_plan')

def check(name='unit', blocks=None, paths=None, repositories=None, kinds=None, excludes=None):
    return {'id': name, 'blocks': ['merge'] if blocks is None else blocks,
            'scope': {'repositories': repositories or ['app'],
                      'include_paths': ['src/**'] if paths is None else paths,
                      'exclude_paths': [] if excludes is None else excludes,
                      'change_types': kinds or ['added', 'modified', 'deleted', 'renamed', 'type_changed']}}

def policy(checks=None):
    return {'schema_version': 2,
        'verification': {'execution': 'ci', 'provider': 'gitlab', 'subject': 'source_sha',
                         'local_execution': 'forbidden', 'reuse_successful_result': True,
                         'checks': [check()] if checks is None else checks},
        'development': {'evidence_mode': 'final_verification'},
        'publication': {'draft_until': 'implementation_and_source_review_complete',
                        'pipeline': {'event': 'merge_request', 'target_branch': 'main',
                                     'require_ready': True, 'bootstrap': 'suppress',
                                     'duplicate_active_run': 'forbidden'}},
        'documentation': {'source_updates': 'required', 'web': {
            'trigger': 'explicit_request', 'blocks_primary_task': False,
            'execution': 'ci', 'runner_tag': 'docs', 'require_success_for_published_sha': True}}}

def inventory(changes=None, **kwargs):
    value = {'version': 1, 'repository': 'app', 'source_sha': 'a' * 40, 'target_sha': 'b' * 40,
             'start_sha': 'b' * 40, 'base_sha': 'c' * 40, 'comparison': 'merge-base',
             'complete': True, 'changes': [{'kind': 'modified', 'old_path': 'src/a.py', 'new_path': 'src/a.py'}] if changes is None else changes}
    value.update(kwargs)
    return value

class PolicyV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def load(self, document=None, **kwargs):
        target = self.root / POLICY.POLICY
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(policy() if document is None else document), encoding='utf-8')
        return POLICY.load_project_policy(self.root, repository='app', operation='merge', **kwargs)

    def test_valid_v2_catalog_loads_without_authorizing_execution(self):
        report = self.load()
        self.assertEqual(report['status'], 'configured', report['diagnostics'])
        self.assertEqual(report['effective_policy'], policy())
        self.assertEqual(report['origins']['/verification/checks']['value'], [check()])
        self.assertEqual(PLAN.plan_operation(report, repository='app', operation='merge', action='merge')['decision'], 'blocked')

    def decide(self, checks=None, changes=None, **kwargs):
        return PLAN.evaluate_check_applicability(self.load(policy(checks)), repository='app', operation='merge',
                                                 change_inventory=inventory(changes, **kwargs))

    def observe(self, decision, **statuses):
        return {ident: {'decision_digest': decision['decision_digest'], 'source_sha': decision['source_sha'],
                        'status': status, 'jobs': [{'name': ident, 'status': status}]} for ident, status in statuses.items()}

    def test_paths_define_independent_roles_for_docs_infra_and_application(self):
        checks = [check(), check('docs', [], ['docs/**']), check('infra', ['deploy'], ['infra/**'])]
        changes = [{'kind': 'modified', 'old_path': p, 'new_path': p}
                   for p in ('docs/intro.md', 'infra/main.tf', 'src/app.py')]
        decision = self.decide(checks, changes)
        self.assertEqual(decision['mandatory_ids'], ['unit'])
        self.assertEqual(decision['background_ids'], ['docs'])
        self.assertEqual(decision['deferred_ids'], ['infra'])
        self.assertEqual(decision['authorization'], 'not_granted')
        docs_only = self.decide(checks, changes[:1])
        self.assertEqual(docs_only['mandatory_ids'], [])
        results = PLAN.evaluate_check_results(docs_only, observations=self.observe(docs_only, docs='failed'))
        self.assertEqual(results['blocking_state'], 'not_required')
        self.assertIsNone(results['checks_satisfied'])
        self.assertEqual(results['background_counts']['failed'], 1)
        self.assertEqual(results['provider_confirmation'], 'unconfirmed')

    def test_rename_deletion_type_change_and_exclusion_use_each_endpoint(self):
        cases = [({'kind': 'renamed', 'old_path': 'src/a.py', 'new_path': 'docs/a.md'}, ['src/a.py']),
                 ({'kind': 'renamed', 'old_path': 'docs/a.md', 'new_path': 'src/a.py'}, ['src/a.py']),
                 ({'kind': 'deleted', 'old_path': 'src/a.py', 'new_path': None}, ['src/a.py']),
                 ({'kind': 'type_changed', 'old_path': 'src/a.py', 'new_path': 'src/a.py'}, ['src/a.py'])]
        for change, matched in cases:
            with self.subTest(change=change):
                decision = self.decide(changes=[change])
                self.assertEqual(decision['mandatory_ids'], ['unit'])
                self.assertEqual(decision['check_decisions'][0]['matched_paths'], matched)
        excluded = self.decide([check(excludes=['src/generated/**'])],
                              [{'kind': 'modified', 'old_path': 'src/generated/a.py', 'new_path': 'src/generated/a.py'}])
        self.assertEqual(excluded['mandatory_ids'], [])
        other = self.decide([check(repositories=['docs'])])
        self.assertEqual(other['mandatory_ids'], [])

    def test_glob_star_stays_within_segment_double_star_accepts_zero_segments(self):
        for pattern, path, expected in [('src/*.py', 'src/a/b.py', False),
                                        ('src/**/*.py', 'src/a.py', True),
                                        ('src/**/*.py', 'src/a/b.py', True),
                                        ('**', 'README.md', True)]:
            value = self.decide([check(paths=[pattern])], [{'kind': 'added', 'old_path': None, 'new_path': path}])
            self.assertEqual(bool(value['mandatory_ids']), expected, (pattern, path))

    def test_complete_empty_inventory_is_not_required_and_never_pipeline_success(self):
        decision = self.decide(changes=[])
        self.assertEqual(decision['mandatory_ids'], [])
        self.assertFalse(decision['blockers'])
        results = PLAN.evaluate_check_results(decision, observations={})
        self.assertEqual(results['blocking_state'], 'not_required')
        self.assertIsNone(results['checks_satisfied'])
        self.assertEqual(results['checks'][0]['status'], 'not_observed')

    def test_incomplete_or_malformed_inventory_blocks_dependents(self):
        cases = [inventory([], complete=False), inventory(comparison='unknown'), inventory(version=True),
                 inventory(source_sha='a'*64), inventory(repository='other'),
                 inventory([{'kind': 'unknown', 'old_path': 'src/a', 'new_path': 'src/a'}]),
                 inventory([{'kind': 'deleted', 'old_path': '../src/a', 'new_path': None}]),
                 inventory([{'kind': 'modified', 'old_path': 'src/a', 'new_path': 'src/b'}]),
                 inventory([{'kind': 'added', 'old_path': 'src/a', 'new_path': 'src/a'}]),
                 inventory([{'kind': 'renamed', 'old_path': None, 'new_path': 'src/a'}])]
        cases.append({**inventory(), 'unexpected': True})
        for item in cases:
            with self.subTest(item=item):
                decision = PLAN.evaluate_check_applicability(self.load(), repository='app', operation='merge', change_inventory=item)
                self.assertTrue(decision['blockers'])
                self.assertEqual(decision['check_decisions'][0]['applicability'], 'unknown')
                results = PLAN.evaluate_check_results(decision, observations={})
                self.assertEqual(results['blocking_state'], 'blocked')
                self.assertFalse(results['checks_satisfied'])
        good64 = inventory(**{k: v * 64 for k,v in [('source_sha','a'),('target_sha','b'),('start_sha','b'),('base_sha','c')]})
        value = PLAN.evaluate_check_applicability(self.load(), repository='app', operation='merge', change_inventory=good64)
        self.assertFalse(value['blockers'])

    def test_catalog_rejects_unknown_duplicate_control_and_unsupported_patterns(self):
        for pattern in ['/abs/**', '../src/**', 'src/../**', 'C:/src/**', r'src\**',
                        'src/a**', 'src/**a', 'src/***', 'src/?', 'src/[ab]', 'src/{a,b}', 'src//a', './src']:
            with self.subTest(pattern=pattern):
                self.assertEqual(self.load(policy([check(paths=[pattern])]))['status'], 'invalid')
        for checks in [[check(), check()], [check('   ')], [check('unit\n')], [dict(check(), typo=True)],
                       [check(kinds=['copied'])]]:
            self.assertEqual(self.load(policy(checks))['status'], 'invalid')
        for version in (True, 2.0, 3, '2'):
            value = policy(); value['schema_version'] = version
            self.assertEqual(self.load(value)['status'], 'invalid')
        value = policy(); value['verification']['required_at'] = 'before_merge'
        self.assertEqual(self.load(value)['status'], 'invalid')

    def test_profile_replaces_whole_catalog_and_expiry_has_no_fallback(self):
        value = policy([check(), check('docs', [], ['docs/**'])])
        value['profiles'] = {'docs_only': {'version': 1, 'reason': 'docs scope',
             'scope': {'repositories': ['app'], 'operations': ['merge']},
             'overrides': {'verification': {'checks': [check('docs', [], ['docs/**'])]}},
             'expires_on': '2030-01-01'}}
        report = self.load(value, profile='docs_only', today=datetime.date(2026, 1, 1))
        self.assertEqual(report['status'], 'configured', report['diagnostics'])
        self.assertEqual([c['id'] for c in report['effective_policy']['verification']['checks']], ['docs'])
        self.assertEqual(report['origins']['/verification/checks']['source_pointer'],
                         '/profiles/docs_only/overrides/verification/checks')
        self.assertEqual(report['origins']['/verification/checks']['profile'], 'docs_only')
        self.assertEqual(self.load(value, profile='docs_only', today=datetime.date(2031, 1, 1))['status'], 'invalid')
        value['profiles']['docs_only']['overrides']['verification']['checks'] = [check(), check()]
        self.assertEqual(self.load(value, profile='docs_only')['status'], 'invalid')

    def test_background_failure_and_progress_never_change_mandatory_satisfaction(self):
        decision = self.decide([check(), check('background', [], ['**'])])
        for status in PLAN.CHECK_STATUSES:
            results = PLAN.evaluate_check_results(decision, observations=self.observe(decision, unit='passed', background=status))
            self.assertEqual(results['blocking_state'], 'satisfied', status)
            self.assertEqual(results['checks'][1]['status'], status)
            self.assertEqual(results['background_counts'][status], 1)
            self.assertEqual(results['checks'][1]['classification'], 'background')
        results = PLAN.evaluate_check_results(decision, observations=self.observe(decision, unit='failed', background='passed'))
        self.assertEqual(results['blocking_state'], 'blocked')
        self.assertEqual(results['checks'][0]['classification'], 'mandatory')

    def test_observed_out_of_scope_background_failure_is_retained(self):
        decision = self.decide([check(), check('docs', [], ['docs/**'])])
        results = PLAN.evaluate_check_results(decision, observations=self.observe(decision, unit='passed', docs='failed'))
        self.assertEqual(results['blocking_state'], 'satisfied')
        self.assertEqual(results['checks'][1]['applicability'], 'not_applicable')
        self.assertEqual(results['checks'][1]['status'], 'failed')
        self.assertEqual(results['background_counts']['failed'], 1)

    def test_each_nonpass_or_missing_mandatory_observation_blocks(self):
        decision = self.decide()
        for status in PLAN.CHECK_STATUSES:
            results = PLAN.evaluate_check_results(decision, observations=self.observe(decision, unit=status))
            self.assertEqual(results['blocking_state'], 'satisfied' if status == 'passed' else 'blocked', status)
        self.assertEqual(PLAN.evaluate_check_results(decision, observations={})['blocking_state'], 'blocked')
        observations = self.observe(decision, unit='passed'); observations['unit']['jobs'] = []
        results = PLAN.evaluate_check_results(decision, observations=observations)
        self.assertEqual(results['checks'][0]['status'], 'missing')
        self.assertFalse(results['checks_satisfied'])
        observations = self.observe(decision, unit='passed'); observations['unit']['jobs'][0]['status'] = 'failed'
        self.assertEqual(PLAN.evaluate_check_results(decision, observations=observations)['checks'][0]['status'], 'failed')

    def test_observation_binding_and_sealed_role_consistency_fail_closed(self):
        decision = self.decide()
        for key, value in [('decision_digest', '0'*64), ('source_sha', 'f'*40), ('status', 'success')]:
            observations = self.observe(decision, unit='passed'); observations['unit'][key] = value
            self.assertEqual(PLAN.evaluate_check_results(decision, observations=observations)['blocking_state'], 'blocked')
        changed = copy.deepcopy(decision); changed['check_decisions'][0]['required'] = False
        self.assertEqual(PLAN.evaluate_check_results(changed, observations={})['blockers'], ['invalid_applicability_decision'])
        unsigned = {k:v for k,v in changed.items() if k != 'decision_digest'}
        changed['decision_digest'] = PLAN._digest(unsigned)
        self.assertEqual(PLAN.evaluate_check_results(changed, observations={})['blockers'], ['invalid_applicability_decision'])
        changed = copy.deepcopy(decision); changed['mandatory_ids'] = []
        changed['decision_digest'] = PLAN._digest({k:v for k,v in changed.items() if k != 'decision_digest'})
        self.assertEqual(PLAN.evaluate_check_results(changed, observations={})['blockers'], ['invalid_applicability_decision'])

    def test_policy_binding_and_wrong_context_cannot_produce_satisfied_checks(self):
        report = self.load(); report['effective_policy']['verification']['checks'][0]['blocks'] = []
        decision = PLAN.evaluate_check_applicability(report, repository='app', operation='merge', change_inventory=inventory())
        self.assertIn('policy_digest_mismatch', decision['blockers'])
        report = self.load()
        for kwargs in [{'repository':'other', 'operation':'merge'}, {'repository':'app','operation':'push'},
                       {'repository':'app','operation':'merge','profile':'missing'}]:
            decision = PLAN.evaluate_check_applicability(report, change_inventory=inventory(), **kwargs)
            self.assertTrue(decision['blockers'])

    def test_legacy_local_tdd_and_before_push_obligations_are_preserved(self):
        config = self.root / '.agents/verify-before-push/config.json'
        config.parent.mkdir(parents=True, exist_ok=True)
        legacy = {'checks': [{'name': 'unit', 'required': True, 'command': ['python','tests.py']} ]}
        config.write_text(json.dumps(legacy), encoding='utf-8')
        report = self.load()
        self.assertIn('legacy_local_execution', report['dependent_action_blockers']['push'])
        self.assertIn('legacy_before_push', report['dependent_action_blockers']['push'])
        legacy['gitlab_ci'] = {'version': 2}; config.write_text(json.dumps(legacy), encoding='utf-8')
        report = self.load()
        self.assertNotIn('legacy_local_execution', report['dependent_action_blockers']['push'])
        self.assertIn('legacy_before_push', report['dependent_action_blockers']['push'])
        # A scoped catalog cannot replace an unconditional legacy push gate.
        report = self.load(policy([check(blocks=['push'])]))
        self.assertIn('legacy_before_push', report['dependent_action_blockers']['push'])
        report = self.load(policy([check(blocks=['push'], paths=['**'])]))
        self.assertNotIn('push', report['dependent_action_blockers'])
        report = self.load(policy([]))
        self.assertIn('legacy_before_push', report['dependent_action_blockers']['push'])
        tdd = self.root / '.agents/execute-verified-development-lifecycle/config.json'
        tdd.parent.mkdir(parents=True); tdd.write_text(json.dumps({'gates':[{'id':'tdd-red','required':True}]}), encoding='utf-8')
        report = self.load()
        self.assertIn('legacy_tdd_red', report['dependent_action_blockers']['merge'])

    def test_resealed_decisions_still_require_valid_source_and_digest_fields(self):
        original = self.decide()
        for key, value in [('source_sha', 'not-a-sha'), ('policy_digest', None),
                           ('source_snapshot_digest', True), ('inventory_digest', '0')]:
            decision = copy.deepcopy(original)
            decision[key] = value
            decision['decision_digest'] = PLAN._digest({k:v for k,v in decision.items() if k != 'decision_digest'})
            result = PLAN.evaluate_check_results(decision, observations=self.observe(decision, unit='passed'))
            self.assertEqual(result['blocking_state'], 'blocked', key)
            self.assertIn('invalid_applicability_decision', result['blockers'])

    def test_malformed_legacy_names_cannot_crash_v2_conflict_resolution(self):
        target = self.root / '.agents/verify-before-push/config.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({'checks':[{'name':['bad'], 'required':True, 'command':['python']}, {'name':'unit', 'required':True, 'command':['python']}]}), encoding='utf-8')
        report = self.load()
        self.assertIn('legacy_before_push', report['dependent_action_blockers']['push'])

    def test_glob_matching_handles_deep_and_repetitive_wildcards_without_backtracking(self):
        # Valid deep paths must not exhaust Python's call stack.
        self.assertFalse(PLAN._matches('/'.join(['a'] * 1500), '**/nope'))
        # Repeated ** components are valid; their failed match is polynomial.
        started = time.monotonic()
        self.assertFalse(PLAN._matches('/'.join(['a'] * 200), '/'.join(['**'] * 20 + ['nope'])))
        self.assertLess(time.monotonic() - started, 2.0)

    def test_single_segment_repeated_star_matching_is_polynomial(self):
        code = ("import importlib.util; "
                "spec=importlib.util.spec_from_file_location('p', " + repr(str(SCRIPTS / 'project_policy_plan.py')) + "); "
                "p=importlib.util.module_from_spec(spec); spec.loader.exec_module(p); "
                "assert p._matches('a'*35, '*a'*20+'b') is False")
        run = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=2)
        self.assertEqual(run.returncode, 0, run.stderr)

if __name__ == '__main__':
    unittest.main()
