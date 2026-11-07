"""Contract for diagnostic development choices and source consistency, not action gates."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/verify-before-push/scripts/development_readiness.py'


def canonical(record, field):
    payload = {k: v for k, v in record.items() if k != field}
    return 'sha256:' + hashlib.sha256(json.dumps(payload, sort_keys=True,
        separators=(',', ':'), ensure_ascii=False).encode('utf-8')).hexdigest()


def subject(char='a'):
    return {'kind': 'commit', 'identity': char * 40}


def policy(mode='final_verification'):
    effective = {'schema_version': 1, 'development': {'evidence_mode': mode},
        'verification': {'execution': 'local', 'provider': 'none', 'local_execution': 'allowed', 'subject': 'source_sha'}}
    sources = {'policy.json': 'a' * 64}
    bare = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True,
        separators=(',', ':'), ensure_ascii=False).encode('utf-8')).hexdigest()
    return {'status': 'configured', 'effective_policy': effective,
            'active_profile': None, 'repository': 'app', 'operation': 'push',
            'effective_digest': bare(effective), 'source_hashes': sources,
            'source_snapshot_digest': bare(sources), 'diagnostics': [],
            'dependent_action_blockers': {}}


class DevelopmentReadinessTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), 'development mode/source readiness entry point is missing')
        spec = importlib.util.spec_from_file_location('development_readiness_test', SCRIPT)
        self.helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.helper)
        self.report = policy()
        self.choice = self.decision()
        self.final_subject = subject('b')
        self.evidence = self.final_evidence()
        self.review = self.review_record()

    def bound(self, value, field):
        value[field] = canonical(value, field)
        return value

    def decision(self, **changes):
        value = {'schema_version': 1, 'format': 'development_mode_decision',
            'repository': 'app', 'operation': 'push', 'profile': None,
            'policy_digest': self.report['effective_digest'],
            'source_snapshot_digest': self.report['source_snapshot_digest'],
            'mode': self.report['effective_policy']['development']['evidence_mode'],
            'selection_subject': subject(), 'phase': 'pre_implementation',
            'rationale': 'Choose declared project mode before implementation',
            'predecessor_digest': None, 'change_reason': None}
        value.update(changes)
        return self.bound(value, 'decision_digest')

    def final_evidence(self, **changes):
        run = {'source': 'local', 'command': ['python', '-m', 'unittest'], 'exit_code': 0,
               'summary': 'Observed successful check against the supplied final subject'}
        value = {'schema_version': 1, 'format': 'development_final_verification',
            'repository': 'app', 'operation': 'push', 'profile': None,
            'policy_digest': self.report['effective_digest'],
            'source_snapshot_digest': self.report['source_snapshot_digest'],
            'decision_digest': self.choice['decision_digest'],
            'subject': self.final_subject,
            'checks': {'focused': copy.deepcopy(run), 'broader': copy.deepcopy(run)}}
        value.update(changes)
        return self.bound(value, 'evidence_digest')

    def review_record(self, **changes):
        value = {'schema_version': 1, 'format': 'development_source_review',
            'repository': 'app', 'operation': 'push', 'profile': None,
            'policy_digest': self.report['effective_digest'],
            'source_snapshot_digest': self.report['source_snapshot_digest'],
            'decision_digest': self.choice['decision_digest'],
            'subject': self.final_subject, 'outcome': 'approved',
            'reviewer': 'source reviewer', 'summary': 'Reviewed the supplied final subject'}
        value.update(changes)
        return self.bound(value, 'review_digest')

    def select(self, decision=None, started=False, previous=None):
        return self.helper.select_mode(self.report, self.choice if decision is None else decision,
                                       started, previous)

    def evaluate(self, **changes):
        args = dict(policy_report=self.report, decision=self.choice, review=self.review,
                    subject=self.final_subject, implementation_complete=True)
        args.update(changes)
        return self.helper.evaluate_source_readiness(**args)

    def verify(self, **changes):
        args = dict(policy_report=self.report, decision=self.choice, evidence=self.evidence, subject=self.final_subject)
        args.update(changes)
        return self.helper.validate_final_verification(**args)

    def assert_blocked(self, result, code=None):
        self.assertEqual(result['status'], 'blocked', result)
        self.assertFalse(result.get('source_ready', False))
        self.assertEqual(result['authorization'], 'not_granted')
        self.assertEqual(result['provider_confirmation'], 'unconfirmed')
        if code:
            self.assertIn(code, [item['code'] for item in result['diagnostics']], result)

    def test_valid_decision_is_diagnostic_and_does_not_prove_chronology(self):
        result = self.select()
        self.assertEqual(result['status'], 'selected', result)
        self.assertEqual(result['mode'], 'final_verification')
        self.assertEqual(result['authorization'], 'not_granted')
        self.assertEqual(result['chronology'], 'not_attested')
        self.assertEqual(result['observations'], 'caller_supplied')
        self.assertEqual(self.helper.digest(self.choice, 'decision_digest'), self.choice['decision_digest'])

    def test_missing_choice_cannot_default_from_policy(self):
        self.assert_blocked(self.helper.select_mode(self.report, None, False), 'invalid_decision')

    def test_mode_conflict_and_scope_changes_fail_closed(self):
        for changes in ({'mode': 'test_first'}, {'repository': 'other'}, {'operation': 'merge'},
                        {'profile': 'migration'}, {'policy_digest': 'f' * 64},
                        {'source_snapshot_digest': 'f' * 64}):
            with self.subTest(changes=changes):
                self.assert_blocked(self.select(self.decision(**changes)))

    def test_exact_decision_format_types_subject_and_binding(self):
        for key, value in [('schema_version', True), ('schema_version', 2), ('mode', []),
                           ('phase', 'automatic'), ('rationale', ''), ('unexpected', True),
                           ('selection_subject', {'kind': 'commit', 'identity': 'x' * 40}),
                           ('decision_digest', 'sha256:' + '0' * 64)]:
            value_record = copy.deepcopy(self.choice)
            value_record[key] = value
            if key != 'decision_digest':
                self.bound(value_record, 'decision_digest')
            with self.subTest(key=key, value=value):
                self.assert_blocked(self.select(value_record))
        malformed = copy.deepcopy(self.choice)
        del malformed['rationale']
        self.assert_blocked(self.select(self.bound(malformed, 'decision_digest')))

    def test_implementation_state_is_explicit_boolean_and_phase_must_match(self):
        for started in (None, 0, 'false'):
            self.assert_blocked(self.helper.select_mode(self.report, self.choice, started))
        self.assert_blocked(self.select(started=True), 'selection_phase_mismatch')
        late = self.decision(phase='late_selection')
        self.assertEqual(self.select(late, started=True)['status'], 'selected')
        self.assert_blocked(self.select(late), 'selection_phase_mismatch')

    def test_changes_need_predecessor_and_explicit_reason(self):
        previous = self.choice
        changed = self.decision(selection_subject=subject('c'))
        self.assert_blocked(self.select(changed, previous=previous), 'decision_change_unexplained')
        changed = self.decision(selection_subject=subject('c'),
            predecessor_digest=previous['decision_digest'], change_reason='New selection source')
        self.assertEqual(self.select(changed, previous=previous)['status'], 'selected')
        self.assert_blocked(self.select(changed), 'missing_predecessor')
        corrupted = copy.deepcopy(previous); corrupted['rationale'] = 'changed without rebinding'
        self.assert_blocked(self.select(changed, previous=corrupted))
        wrong = self.decision(predecessor_digest='sha256:' + '0' * 64, change_reason='Changed')
        self.assert_blocked(self.select(wrong, previous=previous), 'predecessor_mismatch')

    def test_mode_transition_from_old_policy_can_be_explicitly_recorded_late(self):
        previous = self.decision(mode='test_first', policy_digest='f' * 64)
        changed = self.decision(phase='late_selection', predecessor_digest=previous['decision_digest'],
            change_reason='Explicit project policy changed; previous observations retained')
        self.assertEqual(self.select(changed, started=True, previous=previous)['status'], 'selected')

    def test_supported_history_never_accepts_current_record_as_its_predecessor(self):
        changed = self.decision(predecessor_digest='sha256:' + 'f' * 64, change_reason='Changed choice')
        self.assert_blocked(self.select(changed, previous=changed), 'predecessor_mismatch')

    def test_supported_advisory_custom_prose_does_not_invent_policy_blocker(self):
        self.report['diagnostics'].append({'code': 'instructions_need_review',
            'severity': 'needs_review', 'blocking': False, 'affected_operations': ['push']})
        self.assertEqual(self.select()['status'], 'selected')

    def test_supported_private_ci_urls_are_observations_not_network_requests(self):
        self.report['effective_policy']['verification'].update(execution='ci', provider='gitlab', local_execution='forbidden')
        self.report['effective_digest'] = canonical(self.report['effective_policy'], '__none__')[7:]
        self.choice = self.decision()
        for url in ('https://gitlab/jobs/34', 'https://10.0.0.2/jobs/34', 'https://[::1]/jobs/34'):
            ci = {'source': 'ci', 'provider': 'gitlab', 'source_sha': self.final_subject['identity'],
                  'pipeline_id': 12, 'job_id': 34, 'url': url,
                  'status': 'passed', 'summary': 'Caller supplied private CI observation'}
            self.evidence = self.final_evidence(checks={'focused': ci, 'broader': copy.deepcopy(ci)})
            self.assertEqual(self.verify()['status'], 'verified')

    def test_late_test_first_cannot_create_preimplementation_chronology(self):
        self.report = policy('test_first')
        late = self.decision(phase='late_selection')
        self.assert_blocked(self.select(late, started=True), 'late_test_first_selection')

    def test_absent_invalid_conflicted_and_review_condition_policy_block(self):
        for status in ('absent', 'invalid'):
            report = copy.deepcopy(self.report); report['status'] = status
            self.assert_blocked(self.helper.select_mode(report, self.choice, False))
        for diagnostic in ({'code': 'legacy_tdd_red', 'severity': 'conflict', 'affected_operations': ['push']},
                           {'code': 'profile_review_unconfirmed', 'severity': 'needs_review',
                            'affected_operations': ['push']}):
            report = copy.deepcopy(self.report); report['diagnostics'].append(diagnostic)
            self.assert_blocked(self.helper.select_mode(report, self.choice, False))
        report = copy.deepcopy(self.report); report['dependent_action_blockers'] = {'push': ['legacy_gate']}
        self.assert_blocked(self.helper.select_mode(report, self.choice, False))

    def test_report_digest_tampering_and_malformed_report_block(self):
        report = copy.deepcopy(self.report)
        report['effective_policy']['development']['evidence_mode'] = 'test_first'
        self.assert_blocked(self.helper.select_mode(report, self.choice, False))
        report = copy.deepcopy(self.report); report['source_hashes']['policy.json'] = 'b' * 64
        self.assert_blocked(self.helper.select_mode(report, self.choice, False))
        for report in (None, [], {}, {'status': 'configured'}):
            self.assert_blocked(self.helper.select_mode(report, self.choice, False))

    def test_both_policy_report_versions_are_consumed_without_mutation(self):
        for version in (1, 2):
            report = copy.deepcopy(self.report)
            report['effective_policy']['schema_version'] = version
            report['effective_digest'] = canonical(report['effective_policy'], '__none__')[7:]
            self.report = report; self.choice = self.decision()
            original = copy.deepcopy(report)
            self.assertEqual(self.select()['status'], 'selected')
            self.assertEqual(report, original)

    def test_success_requires_distinct_final_evidence_and_bound_review(self):
        result = self.evaluate()
        self.assertEqual(result['status'], 'source_ready', result)
        self.assertTrue(result['source_ready'])
        self.assertEqual(result['provider_confirmation'], 'unconfirmed')
        self.assertEqual(result['authorization'], 'not_granted')
        self.assertEqual(result['readiness_kind'], 'diagnostic_consistency_only')
        self.assertEqual(result['subject_provenance'], 'caller_supplied_not_reconstructed')
        self.assertEqual(result['observations'], 'caller_supplied')
        self.assertEqual(result['chronology'], 'not_attested')

    def test_missing_review_does_not_follow_from_implementation_and_tests(self):
        self.assert_blocked(self.evaluate(review=None), 'invalid_review')
        for field, value in [('outcome', 'changes_requested'), ('reviewer', ''),
                             ('subject', subject('c')), ('decision_digest', 'sha256:' + 'f' * 64)]:
            review = copy.deepcopy(self.review); review[field] = value
            self.assert_blocked(self.evaluate(review=self.bound(review, 'review_digest')))

    def test_final_evidence_rejects_false_success_wrong_bindings_and_red(self):
        for changes in ({'subject': subject('c')}, {'decision_digest': 'sha256:' + 'f' * 64},
                        {'policy_digest': 'f' * 64}, {'profile': 'wrong'},
                        {'schema_version': True}, {'schema_version': 2},
                        {'format': 'test_first'}, {'red': {}}):
            with self.subTest(changes=changes):
                self.assert_blocked(self.verify(evidence=self.final_evidence(**changes)))
        for key, value in [('exit_code', 1), ('exit_code', False), ('command', 'python test.py'),
                           ('command', []), ('summary', ''), ('unexpected', 'value')]:
            evidence = copy.deepcopy(self.evidence); evidence['checks']['focused'][key] = value
            self.assert_blocked(self.verify(evidence=self.bound(evidence, 'evidence_digest')))
        for field in ('focused', 'broader'):
            evidence = copy.deepcopy(self.evidence); del evidence['checks'][field]
            self.assert_blocked(self.verify(evidence=self.bound(evidence, 'evidence_digest')))

    def test_evidence_review_digest_and_exact_fields_are_required(self):
        for argument, record, field in [('evidence', self.evidence, 'evidence_digest'),
                                        ('review', self.review, 'review_digest')]:
            changed = copy.deepcopy(record); changed[field] = 'sha256:' + '0' * 64
            self.assert_blocked((self.verify if argument == 'evidence' else self.evaluate)(**{argument: changed}))
            changed = copy.deepcopy(record); changed['unknown'] = True
            self.assert_blocked((self.verify if argument == 'evidence' else self.evaluate)(**{argument: self.bound(changed, field)}))
        self.assert_blocked(self.evaluate(subject={'kind': 'worktree', 'identity': 'bad'}))

    def test_test_first_ingestion_is_explicitly_unavailable_and_no_filesystem_search(self):
        self.report = policy('test_first'); self.choice = self.decision()
        self.evidence = {'schema_version': 1, 'subject': self.final_subject, 'red': {}, 'green': {}}
        self.review = self.review_record()
        with patch('pathlib.Path.read_bytes', side_effect=AssertionError('unexpected runtime discovery')):
            self.assert_blocked(self.verify(), 'test_first_evidence_unavailable')
        self.assertEqual(self.evaluate()['status'], 'source_ready')

    def test_api_is_read_only_and_never_invokes_subprocess_or_providers(self):
        original = copy.deepcopy([self.report, self.choice, self.evidence, self.review, self.final_subject])
        with (patch('subprocess.run', side_effect=AssertionError('must not execute checks')),
                patch('pathlib.Path.write_text', side_effect=AssertionError('must not write'))):
            self.evaluate()
        self.assertEqual([self.report, self.choice, self.evidence, self.review, self.final_subject], original)

    def test_cli_loads_fresh_policy_and_outputs_consistency_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records = {'decision': self.choice, 'review': self.review, 'subject': self.final_subject}
            paths = {}
            for name, value in records.items():
                paths[name] = root / (name + '.json')
                paths[name].write_text(json.dumps(value), encoding='utf-8')
            argv = ['source-readiness', '--project-root', str(root), '--repository', 'app',
                    '--operation', 'push', '--implementation-complete', 'true']
            for name, path in paths.items():
                argv.extend(['--' + name, str(path)])
            with (patch.object(self.helper, '_load_policy', return_value=self.report) as loader,
                    patch('sys.stdout', new_callable=io.StringIO) as output):
                code = self.helper.main(argv)
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output.getvalue())['status'], 'source_ready')
            loader.assert_called_once_with(str(root), repository='app', operation='push', profile=None)

    def test_cli_duplicate_keys_and_missing_json_fail_closed_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            record = Path(directory) / 'choice.json'
            record.write_text('{"schema_version":1,"schema_version":1}', encoding='utf-8')
            for path in (record, record.parent / 'missing.json'):
                argv = ['select-mode', '--project-root', directory, '--repository', 'app',
                        '--operation', 'push', '--implementation-started', 'false', '--decision', str(path)]
                with (patch.object(self.helper, '_load_policy', return_value=self.report),
                        patch('sys.stdout', new_callable=io.StringIO) as output):
                    self.assertEqual(self.helper.main(argv), 2)
                self.assertEqual(json.loads(output.getvalue())['status'], 'blocked')

    def test_source_readiness_precedes_final_ci_and_requires_explicit_completion(self):
        self.assertEqual(self.evaluate()['status'], 'source_ready')
        self.assert_blocked(self.verify(evidence=None), 'invalid_evidence')
        for complete in (False, 1, None, 'true'):
            self.assert_blocked(self.evaluate(implementation_complete=complete), 'implementation_incomplete')

    def test_output_receipts_bind_subject_scope_and_input_digests(self):
        result = self.evaluate()
        self.assertIn('bindings', result)
        self.assertEqual(result['bindings']['subject'], self.final_subject)
        self.assertEqual(result['bindings']['repository'], 'app')
        self.assertEqual(result['bindings']['operation'], 'push')
        self.assertEqual(result['bindings']['policy_digest'], self.report['effective_digest'])
        self.assertEqual(result['bindings']['decision_digest'], self.choice['decision_digest'])
        self.assertEqual(result['bindings']['review_digest'], self.review['review_digest'])
        self.assertEqual(result['readiness_digest'], canonical(result, 'readiness_digest'))
        blocked = self.evaluate(subject=subject('c'))
        self.assertIsNone(blocked['bindings'])
        self.assertEqual(blocked['readiness_digest'], canonical(blocked, 'readiness_digest'))
        verified = self.verify()
        self.assertEqual(verified['bindings']['subject'], self.final_subject)
        self.assertEqual(verified['bindings']['evidence_digest'], self.evidence['evidence_digest'])
        self.assertEqual(verified['report_digest'], canonical(verified, 'report_digest'))

    def test_final_verification_local_and_ci_observations_match_execution_policy(self):
        self.assertEqual(self.verify()['status'], 'verified')
        self.report['effective_policy']['verification'].update(execution='ci', provider='gitlab', local_execution='forbidden')
        self.report['effective_digest'] = canonical(self.report['effective_policy'], '__none__')[7:]
        self.choice = self.decision()
        self.evidence = self.final_evidence()
        self.assert_blocked(self.verify(), 'check_execution_mismatch')
        ci = {'source': 'ci', 'provider': 'gitlab', 'source_sha': self.final_subject['identity'],
              'pipeline_id': 12, 'job_id': 34, 'url': 'https://gitlab.example/app/jobs/34',
              'status': 'passed', 'summary': 'Caller observed successful pipeline job'}
        self.evidence = self.final_evidence(checks={'focused': ci, 'broader': copy.deepcopy(ci)})
        self.assertEqual(self.verify()['status'], 'verified')
        for key, value in [('provider', 'github'), ('source_sha', 'c' * 40), ('job_id', True),
                           ('pipeline_id', 0), ('status', 'running'), ('url', 'http://example.com'),
                           ('url', 'https://user:password@example.com'), ('exit_code', 0)]:
            evidence = copy.deepcopy(self.evidence); evidence['checks']['focused'][key] = value
            self.assert_blocked(self.verify(evidence=self.bound(evidence, 'evidence_digest')))
        self.report['effective_policy']['verification']['subject'] = 'merge_result_sha'
        self.report['effective_digest'] = canonical(self.report['effective_policy'], '__none__')[7:]
        self.choice = self.decision(); self.evidence = self.final_evidence()
        self.assert_blocked(self.verify(), 'unsupported_verification_subject')

    def test_schema_files_are_closed_and_separate_from_existing_evidence(self):
        for name in ('development-mode-decision', 'development-final-verification',
                     'development-source-review', 'development-source-readiness'):
            schema = json.loads((SCRIPT.parent.parent / 'schemas' / (name + '.schema.json')).read_text('utf-8'))
            self.assertFalse(schema['additionalProperties'])
            self.assertEqual(schema['properties']['schema_version']['const'], 1)


if __name__ == '__main__':
    unittest.main()
