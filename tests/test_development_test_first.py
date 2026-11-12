"""Policy-bound local test-first consistency through the injected canonical validator."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/verify-before-push/scripts/development_readiness.py'
LEGACY = ROOT / 'skills/develop-with-test-first-evidence/scripts/evidence.py'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bound(value, field):
    value[field] = 'sha256:' + hashlib.sha256(json.dumps(
        {k: v for k, v in value.items() if k != field}, sort_keys=True,
        separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    return value


class DevelopmentTestFirstTests(unittest.TestCase):
    def setUp(self):
        self.helper = load(SCRIPT, 'test_first_readiness')
        self.legacy = load(LEGACY, 'test_first_canonical')
        effective = {'schema_version': 2, 'development': {'evidence_mode': 'test_first'},
            'verification': {'execution': 'local', 'provider': 'none',
                'local_execution': 'allowed', 'subject': 'source_sha'}}
        sources = {'policy.json': 'a' * 64}
        self.report = {'status': 'configured', 'effective_policy': effective,
            'active_profile': None, 'repository': 'app', 'operation': 'push',
            'effective_digest': bound(copy.deepcopy(effective), '_digest')['_digest'][7:],
            'source_hashes': sources,
            'source_snapshot_digest': bound(copy.deepcopy(sources), '_digest')['_digest'][7:],
            'diagnostics': [], 'dependent_action_blockers': {}}
        self.subject = {'kind': 'commit', 'identity': 'b' * 40}
        self.decision = bound({'schema_version': 1, 'format': 'development_mode_decision',
            **self.context(), 'mode': 'test_first',
            'selection_subject': {'kind': 'commit', 'identity': 'a' * 40},
            'phase': 'pre_implementation', 'rationale': 'Selected before implementation',
            'predecessor_digest': None, 'change_reason': None}, 'decision_digest')
        run = {'command': ['python', '-m', 'unittest'], 'exit_code': 0,
               'summary': 'Caller observed the supplied check'}
        self.evidence = bound({'schema_version': 1, 'behavior': 'Policy-bound local test-first evidence',
            'subject': copy.deepcopy(self.subject),
            'red': {**run, 'exit_code': 1, 'failure_class': 'intended_behavior',
                'intended_behavior_failure_reason': 'Required test-first binding API is missing'},
            'green': {'focused': copy.deepcopy(run), 'broader': copy.deepcopy(run)}}, 'evidence_digest')
        self.binding = self.make_binding()

    def context(self):
        return {'repository': 'app', 'operation': 'push', 'profile': None,
            'policy_digest': self.report['effective_digest'],
            'source_snapshot_digest': self.report['source_snapshot_digest']}

    def make_binding(self, **changes):
        value = {'schema_version': 1, 'format': 'development_test_first_binding',
            **self.context(), 'decision_digest': self.decision['decision_digest'],
            'subject': copy.deepcopy(self.subject), 'test_first_evidence': copy.deepcopy(self.evidence)}
        value.update(changes)
        return bound(value, 'binding_digest')

    def verify(self, **changes):
        self.assertTrue(callable(getattr(self.helper, 'validate_test_first_binding', None)),
                        'policy-bound canonical test-first validation API is missing')
        args = dict(policy_report=self.report, decision=self.decision, binding=self.binding,
                    subject=self.subject, legacy_validator=self.legacy.validate)
        args.update(changes)
        return self.helper.validate_test_first_binding(**args)

    def assert_blocked(self, result, code=None):
        self.assertEqual(result['status'], 'blocked', result)
        self.assertFalse(result['test_first_satisfied'])
        self.assertIsNone(result['bindings'])
        self.assertEqual(result['authorization'], 'not_granted')
        self.assertEqual(result['report_digest'], self.helper.digest(result, 'report_digest'))
        if code:
            self.assertIn(code, [item['code'] for item in result['diagnostics']], result)

    def update_policy(self, **changes):
        self.report['effective_policy']['verification'].update(changes)
        self.report['effective_digest'] = bound(copy.deepcopy(self.report['effective_policy']), '_digest')['_digest'][7:]
        self.decision.update(self.context())
        bound(self.decision, 'decision_digest')
        self.binding = self.make_binding()

    def test_valid_local_binding_delegates_once_and_seals_exact_context(self):
        observed = []
        def validator(value):
            observed.append(copy.deepcopy(value))
            return self.legacy.validate(value)
        result = self.verify(legacy_validator=validator)
        self.assertEqual(result['status'], 'verified', result)
        self.assertTrue(result['test_first_satisfied'])
        self.assertEqual(observed, [self.evidence])
        for key, value in self.context().items():
            self.assertEqual(result['bindings'][key], value)
        self.assertEqual(result['bindings']['subject'], self.subject)
        self.assertEqual(result['bindings']['binding_digest'], self.binding['binding_digest'])
        self.assertEqual(result['bindings']['evidence_digest'], self.evidence['evidence_digest'])
        for key, value in [('observations', 'caller_supplied'), ('chronology', 'not_attested'),
                           ('provider_confirmation', 'unconfirmed'), ('authorization', 'not_granted')]:
            self.assertEqual(result[key], value)
        self.assertEqual(result['report_digest'], self.helper.digest(result, 'report_digest'))

    def test_nested_canonical_errors_are_required_and_not_reinterpreted(self):
        invalid = copy.deepcopy(self.evidence)
        invalid['red']['exit_code'] = 0
        bound(invalid, 'evidence_digest')
        self.assert_blocked(self.verify(binding=self.make_binding(test_first_evidence=invalid)), 'invalid_test_first_evidence')
        self.assert_blocked(self.verify(legacy_validator=lambda _: ['canonical rejection']), 'invalid_test_first_evidence')

    def test_missing_raising_and_malformed_validator_results_fail_closed(self):
        def raises(_):
            raise TypeError('Invalid caller observation')
        for validator in (None, raises, lambda _: None, lambda _: False, lambda _: 'error',
                          lambda _: {}, lambda _: [None], lambda _: [1], lambda _: ()): 
            with self.subTest(validator=validator):
                self.assert_blocked(self.verify(legacy_validator=validator), 'invalid_legacy_validator')

    def test_binding_exact_fields_version_and_digest_are_required(self):
        for key, value in [('schema_version', True), ('schema_version', 2), ('format', 'other'),
                           ('unexpected', True), ('profile', []), ('binding_digest', 'sha256:' + '0' * 64)]:
            record = copy.deepcopy(self.binding)
            record[key] = value
            if key != 'binding_digest':
                bound(record, 'binding_digest')
            with self.subTest(key=key):
                self.assert_blocked(self.verify(binding=record), 'invalid_binding')
        record = copy.deepcopy(self.binding)
        del record['test_first_evidence']
        self.assert_blocked(self.verify(binding=bound(record, 'binding_digest')), 'invalid_binding')
        for record in (None, [], {}):
            self.assert_blocked(self.verify(binding=record), 'invalid_binding')

    def test_stale_context_or_decision_never_accepts(self):
        for key, value in [('repository', 'other'), ('operation', 'merge'), ('profile', 'migration'),
                           ('policy_digest', 'f' * 64), ('source_snapshot_digest', 'f' * 64),
                           ('decision_digest', 'sha256:' + 'f' * 64)]:
            with self.subTest(key=key):
                self.assert_blocked(self.verify(binding=self.make_binding(**{key: value})))

    def test_wrapper_nested_and_expected_subject_must_agree(self):
        other = {'kind': 'commit', 'identity': 'c' * 40}
        self.assert_blocked(self.verify(subject=other), 'evidence_subject_mismatch')
        self.assert_blocked(self.verify(binding=self.make_binding(subject=other)), 'evidence_subject_mismatch')
        nested = copy.deepcopy(self.evidence)
        nested['subject'] = other
        bound(nested, 'evidence_digest')
        self.assert_blocked(self.verify(binding=self.make_binding(test_first_evidence=nested)), 'evidence_subject_mismatch')
        self.assert_blocked(self.verify(subject={'kind': 'worktree', 'identity': 'invalid'}), 'invalid_subject')

    def test_local_worktree_evidence_remains_supported(self):
        self.subject = {'kind': 'worktree', 'identity': 'sha256:' + 'b' * 64}
        self.evidence['subject'] = copy.deepcopy(self.subject)
        bound(self.evidence, 'evidence_digest')
        self.binding = self.make_binding()
        self.assertEqual(self.verify()['status'], 'verified')

    def test_ci_forbidden_local_and_merge_result_are_explicitly_unsupported(self):
        for changes in ({'execution': 'ci', 'provider': 'github', 'local_execution': 'forbidden'},
                        {'local_execution': 'forbidden'}, {'provider': 'gitlab'}, {'execution': 'ci'}):
            with self.subTest(changes=changes):
                saved = copy.deepcopy([self.report, self.decision, self.binding])
                self.update_policy(**changes)
                self.assert_blocked(self.verify(), 'unsupported_test_first_execution')
                self.report, self.decision, self.binding = saved
        self.update_policy(subject='merge_result_sha')
        self.assert_blocked(self.verify(), 'unsupported_verification_subject')

    def test_final_only_mode_cannot_use_test_first_binding(self):
        self.report['effective_policy']['development']['evidence_mode'] = 'final_verification'
        self.update_policy()
        self.decision['mode'] = 'final_verification'
        bound(self.decision, 'decision_digest')
        self.binding = self.make_binding()
        self.assert_blocked(self.verify(), 'mode_conflict')

    def test_current_policy_and_preimplementation_selection_are_required(self):
        for report in (None, {}, {'status': 'absent'}):
            self.assert_blocked(self.verify(policy_report=report), 'invalid_policy_report')
        self.decision['phase'] = 'late_selection'
        bound(self.decision, 'decision_digest')
        self.binding = self.make_binding()
        self.assert_blocked(self.verify(), 'late_test_first_selection')

    def test_predecessor_is_checked_by_shared_selection(self):
        previous = copy.deepcopy(self.decision)
        self.decision.update(selection_subject={'kind': 'commit', 'identity': 'c' * 40},
            predecessor_digest=previous['decision_digest'], change_reason='Explicit new selection')
        bound(self.decision, 'decision_digest')
        self.binding = self.make_binding()
        self.assert_blocked(self.verify(), 'missing_predecessor')
        self.assertEqual(self.verify(previous_decision=previous)['status'], 'verified')

    def test_read_only_no_runtime_search_provider_calls_or_input_mutation(self):
        before = copy.deepcopy([self.report, self.decision, self.binding, self.subject])
        def mutating_validator(value):
            valid = self.legacy.validate(value)
            value['behavior'] = 'Caller callable mutation must not alter supplied record'
            return valid
        with (patch('subprocess.run', side_effect=AssertionError('must not execute')),
              patch('pathlib.Path.read_bytes', side_effect=AssertionError('must not discover runtimes')),
              patch('pathlib.Path.write_text', side_effect=AssertionError('must not write'))):
            self.assertEqual(self.verify(legacy_validator=mutating_validator)['status'], 'verified')
        self.assertEqual([self.report, self.decision, self.binding, self.subject], before)

    def test_result_and_binding_schemas_describe_closed_records(self):
        schema_root = ROOT / 'skills/verify-before-push/schemas'
        binding_schema = json.loads((schema_root / 'development-test-first-binding.schema.json').read_text(encoding='utf-8'))
        result_schema = json.loads((schema_root / 'development-test-first-result.schema.json').read_text(encoding='utf-8'))
        self.assertFalse(binding_schema['additionalProperties'])
        self.assertEqual(set(binding_schema['required']), set(self.binding))
        self.assertEqual(set(binding_schema['properties']), set(self.binding))
        self.assertEqual(binding_schema['properties']['format']['const'], 'development_test_first_binding')
        self.assertEqual(binding_schema['properties']['test_first_evidence']['type'], 'object')
        self.assertFalse(result_schema['additionalProperties'])
        for result in (self.verify(), self.verify(binding=None)):
            self.assertEqual(set(result_schema['required']), set(result))
            self.assertEqual(set(result_schema['properties']), set(result))
        properties = result_schema['properties']
        self.assertEqual(properties['authorization']['const'], 'not_granted')
        self.assertEqual(properties['chronology']['const'], 'not_attested')

    def test_runtime_marker_declares_fixed_provider_api(self):
        marker = json.loads((ROOT / 'skills/verify-before-push/references/runtime-api.json').read_text(encoding='utf-8'))
        self.assertEqual(marker, {'schema_version': 1, 'provider': 'verify-before-push',
            'collection': 'kolabse-skills', 'api_version': 1,
            'capabilities': ['project-policy-v1-v2', 'development-readiness-v1', 'test-first-binding-v1'],
            'entrypoints': {'project_policy': 'scripts/project_policy.py',
                            'development_readiness': 'scripts/development_readiness.py'}})


if __name__ == '__main__':
    unittest.main()
