"""Consumer acceptance must select bounded runtime context without executing checks."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(os.environ.get('POLICY_EVIDENCE_TEST_ROOT', Path(__file__).resolve().parents[1]))
CONSUMER = ROOT / 'skills/develop-with-test-first-evidence'
PROVIDER = ROOT / 'skills/verify-before-push'
SCRIPT = CONSUMER / 'scripts/evidence.py'
ADAPTER = CONSUMER / 'scripts/policy_evidence.py'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sealed(value, field):
    value[field] = 'sha256:' + hashlib.sha256(json.dumps(
        {k: v for k, v in value.items() if k != field}, sort_keys=True,
        separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    return value


def standard(mode='test_first', ci=False):
    return {'schema_version': 1,
        'verification': {'required_at': 'before_merge' if ci else 'before_push',
            'execution': 'ci' if ci else 'local', 'provider': 'gitlab' if ci else 'none',
            'subject': 'source_sha', 'local_execution': 'forbidden' if ci else 'allowed',
            'reuse_successful_result': True},
        'development': {'evidence_mode': mode},
        'publication': {'draft_until': 'implementation_and_source_review_complete',
            'pipeline': {'event': 'merge_request' if ci else 'push', 'target_branch': 'main',
                'require_ready': True, 'bootstrap': 'suppress', 'duplicate_active_run': 'forbidden'}},
        'documentation': {'source_updates': 'required', 'web': {'trigger': 'explicit_request',
            'blocks_primary_task': False, 'execution': 'ci', 'runner_tag': 'docs',
            'require_success_for_published_sha': True}}}


def legacy():
    run = {'command': ['python', '-m', 'unittest'], 'exit_code': 0, 'summary': 'Passed'}
    return sealed({'schema_version': 1, 'behavior': 'Intended behavior',
        'subject': {'kind': 'commit', 'identity': 'a' * 40},
        'red': dict(run, exit_code=1, failure_class='intended_behavior',
                    intended_behavior_failure_reason='Missing intended behavior assertion failed'),
        'green': {'focused': copy.deepcopy(run), 'broader': copy.deepcopy(run)}}, 'evidence_digest')


class PolicyEvidenceAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / 'project'
        self.project.mkdir()
        self.record = self.write('evidence.json', legacy())
        self.assertTrue(ADAPTER.is_file(), 'policy-aware evidence acceptance adapter is missing')
        self.adapter = load(ADAPTER, 'adapter_test')
        self.validator = load(SCRIPT, 'canonical_evidence_test')

    def write(self, relative, data):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding='utf-8')
        return path

    def accept(self, **changes):
        args = dict(input_path=self.record, project_root=self.project, repository='app',
                    operation='push', legacy_validator=self.validator.validate)
        args.update(changes)
        return self.adapter.accept_records(**args)

    def assert_sealed(self, result):
        self.assertEqual(result['acceptance_digest'], sealed(copy.deepcopy(result), 'acceptance_digest')['acceptance_digest'])
        self.assertEqual(result['authorization'], 'not_granted')
        self.assertEqual(result['provider_confirmation'], 'unconfirmed')
        self.assertEqual(result['chronology'], 'not_attested')
        self.assertEqual(result['observations'], 'caller_supplied')
        self.assertEqual(result['format'], 'development_evidence_acceptance')
        self.assertEqual(result['input_sha256'], hashlib.sha256(self.record.read_bytes()).hexdigest())

    def assert_blocked(self, result, code=None):
        self.assertEqual(result['status'], 'blocked', result)
        self.assert_sealed(result)
        if code:
            self.assertIn(code, [x['code'] for x in result['diagnostics']], result)

    def configured(self, mode='test_first', ci=False):
        self.write('project/.agents/kolabse/project-policy.json', standard(mode, ci))
        policy = load(PROVIDER / 'scripts/project_policy.py', 'provider_policy_test')
        report = policy.load_project_policy(self.project, repository='app', operation='push')
        self.assertEqual(report['status'], 'configured', report)
        scope = {'repository': 'app', 'operation': 'push', 'profile': None,
            'policy_digest': report['effective_digest'],
            'source_snapshot_digest': report['source_snapshot_digest']}
        choice = sealed(dict(scope, schema_version=1, format='development_mode_decision',
            mode=mode, selection_subject=legacy()['subject'], phase='pre_implementation',
            rationale='Chosen before implementation', predecessor_digest=None, change_reason=None), 'decision_digest')
        self.decision = self.write('decision.json', choice)
        self.subject = self.write('subject.json', legacy()['subject'])
        if mode == 'test_first':
            value = dict(scope, schema_version=1, format='development_test_first_binding',
                decision_digest=choice['decision_digest'], subject=legacy()['subject'], test_first_evidence=legacy())
            value = sealed(value, 'binding_digest')
        else:
            run = {'source': 'local', 'command': ['python', '-m', 'unittest'], 'exit_code': 0, 'summary': 'Passed'}
            if ci:
                run = {'source': 'ci', 'provider': 'gitlab', 'source_sha': 'a' * 40,
                    'pipeline_id': 100, 'job_id': 101, 'url': 'https://gitlab.example/jobs/101',
                    'status': 'passed', 'summary': 'Passed'}
            value = sealed(dict(scope, schema_version=1, format='development_final_verification',
                decision_digest=choice['decision_digest'], subject=legacy()['subject'],
                checks={'focused': copy.deepcopy(run), 'broader': copy.deepcopy(run)}), 'evidence_digest')
        self.record = self.write('evidence.json', value)
        return report, choice, value

    def runtime_copy(self):
        target = self.root / 'runtime'
        shutil.copytree(PROVIDER, target)
        return target

    def test_legacy_absent_policy_is_sealed_and_uses_canonical_validator(self):
        result = self.accept()
        self.assertEqual(result['status'], 'legacy', result)
        self.assertIsNone(result['provider_result'])
        self.assert_sealed(result)
        with patch.object(self.validator, 'validate', return_value=['canonical rejection']):
            self.assert_blocked(self.accept(legacy_validator=self.validator.validate), 'invalid_legacy_evidence')

    def test_standalone_legacy_does_not_need_provider(self):
        # A physically isolated consumer has no sibling provider or global lookup.
        consumer = self.root / 'standalone/develop-with-test-first-evidence'
        shutil.copytree(CONSUMER, consumer)
        adapter = load(consumer / 'scripts/policy_evidence.py', 'standalone_adapter')
        result = adapter.accept_records(self.record, self.project, 'app', 'push',
            legacy_validator=self.validator.validate)
        self.assertEqual(result['status'], 'legacy')
        self.assertIsNone(result['runtime_provenance'])
        self.write('project/.agents/kolabse/project-policy.yaml', {})
        self.assertEqual(adapter.accept_records(self.record, self.project, 'app', 'push',
            legacy_validator=self.validator.validate)['status'], 'blocked')

    def test_explicit_policy_context_never_disappears_into_legacy(self):
        for change in ({'profile': 'cloud'}, {'decision_path': self.record},
                       {'previous_decision_path': self.record}, {'subject_path': self.record}):
            with self.subTest(change=change):
                self.assert_blocked(self.accept(**change), 'absent_policy_context')
        self.assertEqual(self.accept(policy_runtime_root=PROVIDER)['status'], 'legacy')
        self.assert_blocked(self.accept(policy_runtime_root=self.root / 'missing-runtime'), 'invalid_runtime')

    def test_invalid_root_and_unsafe_or_dangling_boundaries_never_legacy(self):
        self.assert_blocked(self.accept(project_root=self.root / 'missing'), 'invalid_project_root')
        self.assert_blocked(self.accept(project_root=self.record), 'invalid_project_root')
        boundary = self.project / '.agents'
        try:
            boundary.symlink_to(self.root / 'missing-target', target_is_directory=True)
        except OSError:
            self.skipTest('Symlink creation unavailable')
        self.assert_blocked(self.accept())

    def test_candidate_fallback_matches_provider_and_never_parses_semantics(self):
        provider = load(PROVIDER / 'scripts/project_policy.py', 'fallback_provider')
        self.assertEqual(tuple(self.adapter.POLICY_CANDIDATES), tuple(provider.CANDIDATES))
        for candidate in provider.CANDIDATES:
            self.write('project/' + candidate, {'malformed': True})
            self.assert_blocked(self.accept())

    def test_validator_exception_and_malformed_result_block(self):
        for result in (None, True, 'accepted', [False]):
            self.assert_blocked(self.accept(legacy_validator=lambda _: result), 'invalid_legacy_validator_result')
        def broken(_):
            raise RuntimeError('Untrusted validator error')
        self.assert_blocked(self.accept(legacy_validator=broken), 'legacy_validator_failed')

    def test_strict_input_duplicate_keys_nonfinite_and_wrong_json_block(self):
        for raw in ('{"x":1,"x":2}', '{"x":NaN}', '[]', '\ufeff{"x":Infinity}'):
            self.record.write_text(raw, encoding='utf-8')
            self.assert_blocked(self.accept(), 'invalid_input')

    def test_policy_test_first_delegates_with_unchanged_nested_evidence(self):
        _, _, value = self.configured()
        before = copy.deepcopy(value)
        result = self.accept(decision_path=self.decision, subject_path=self.subject)
        self.assertEqual(result['status'], 'accepted', result)
        provider = result['provider_result']
        self.assertTrue(provider['test_first_satisfied'])
        self.assertEqual(provider['report_digest'], sealed(copy.deepcopy(provider), 'report_digest')['report_digest'])
        self.assertEqual(value, before)
        self.assert_sealed(result)
        provenance = result['runtime_provenance']
        self.assertEqual(provenance['api_version'], 1)
        self.assertEqual(Path(provenance['root']), PROVIDER.resolve())
        for relative in ('collection-metadata.json', 'references/runtime-api.json',
                         'scripts/project_policy.py', 'scripts/development_readiness.py',
                         'schemas/development-test-first-binding.schema.json'):
            self.assertEqual(provenance['file_sha256'][relative], hashlib.sha256((PROVIDER / relative).read_bytes()).hexdigest())
        self.assertEqual(provenance['consumer_validator_sha256'], hashlib.sha256(SCRIPT.read_bytes()).hexdigest())

    def test_native_final_ci_is_preserved_without_fake_exit_codes(self):
        _, _, value = self.configured('final_verification', ci=True)
        result = self.accept(decision_path=self.decision, subject_path=self.subject)
        self.assertEqual(result['status'], 'accepted', result)
        self.assertTrue(result['provider_result']['final_verification_satisfied'])
        self.assertNotIn('exit_code', json.dumps(value))
        self.assert_sealed(result)

    def test_configured_input_needs_explicit_decision_and_subject(self):
        self.configured()
        self.assert_blocked(self.accept(), 'missing_policy_context')
        self.assert_blocked(self.accept(decision_path=self.decision), 'missing_policy_context')

    def test_ci_only_test_first_and_invalid_policy_never_fallback(self):
        self.configured('test_first', ci=True)
        self.assert_blocked(self.accept(decision_path=self.decision, subject_path=self.subject))
        self.write('project/.agents/kolabse/project-policy.json', {'schema_version': True})
        self.record = self.write('evidence.json', legacy())
        self.assert_blocked(self.accept())

    def test_metadata_marker_schema_and_entrypoint_checked_before_import(self):
        self.configured()
        runtime = self.runtime_copy()
        loader = runtime / 'scripts/project_policy.py'
        sentinel = self.root / 'unsafe-import-executed'
        loader.write_text("from pathlib import Path\nPath(" + repr(str(sentinel)) +
            ").write_text('executed')\nraise AssertionError('unsafe import executed')", encoding='utf-8')
        marker = runtime / 'references/runtime-api.json'
        original = json.loads(marker.read_text(encoding='utf-8'))
        for key, value in (('api_version', True), ('capabilities', []),
                           ('entrypoints', {'project_policy': '../outside.py'}), ('collection', 'other')):
            altered = copy.deepcopy(original)
            altered[key] = value
            marker.write_text(json.dumps(altered), encoding='utf-8')
            self.assert_blocked(self.accept(policy_runtime_root=runtime), 'invalid_runtime')
            self.assertFalse(sentinel.exists(), 'Invalid runtime must be rejected before module import')
        marker.write_text(json.dumps(original), encoding='utf-8')
        (runtime / 'schemas/development-test-first-binding.schema.json').unlink()
        self.assert_blocked(self.accept(policy_runtime_root=runtime), 'invalid_runtime')
        self.assertFalse(sentinel.exists(), 'Missing required schemas must block before import')

    def test_metadata_v1_compatibility_and_v2_source_consistency(self):
        runtime = self.runtime_copy()
        path = runtime / 'collection-metadata.json'
        value = json.loads(path.read_text(encoding='utf-8'))
        value['schema_version'] = 1
        value.pop('canonical_repository', None)
        value['version'] = '0.1.0'
        path.write_text(json.dumps(value), encoding='utf-8')
        self.assertEqual(self.accept(policy_runtime_root=runtime)['status'], 'legacy')
        value.update(schema_version=2, canonical_repository='https://github.com/other/skills')
        path.write_text(json.dumps(value), encoding='utf-8')
        self.assert_blocked(self.accept(policy_runtime_root=runtime), 'invalid_runtime')

    def test_metadata_skill_collection_version_and_source_are_required(self):
        runtime = self.runtime_copy()
        path = runtime / 'collection-metadata.json'
        original = json.loads(path.read_text(encoding='utf-8'))
        for key, value in (('schema_version', True), ('schema_version', 3), ('skill', 'other'),
                           ('collection', 'other'), ('source', 'https://github.com/other/skills'),
                           ('version', '')):
            changed = dict(original, **{key: value})
            path.write_text(json.dumps(changed), encoding='utf-8')
            self.assert_blocked(self.accept(policy_runtime_root=runtime), 'invalid_runtime')

    def test_runtime_root_symlink_allowed_fixed_file_escape_blocked(self):
        runtime = self.runtime_copy()
        alias = self.root / 'alias'
        try:
            alias.symlink_to(runtime, target_is_directory=True)
        except OSError:
            self.skipTest('Symlink creation unavailable')
        self.assertEqual(self.accept(policy_runtime_root=alias)['status'], 'legacy')
        marker = runtime / 'references/runtime-api.json'
        external = self.root / 'external-marker.json'
        external.write_bytes(marker.read_bytes())
        marker.unlink()
        marker.symlink_to(external)
        self.assert_blocked(self.accept(policy_runtime_root=alias), 'invalid_runtime')

    def test_runtime_change_during_validation_cannot_receive_acceptance(self):
        self.configured()
        runtime = self.runtime_copy()
        script = runtime / 'scripts/project_policy.py'
        marker = runtime / 'references/runtime-api.json'
        script.write_text(script.read_text(encoding='utf-8') +
            "\nPath(" + repr(str(marker)) + ").write_text('{}', encoding='utf-8')\n", encoding='utf-8')
        self.assert_blocked(self.accept(policy_runtime_root=runtime,
            decision_path=self.decision, subject_path=self.subject), 'runtime_changed')

    def test_cli_accept_and_old_v1_commands(self):
        for command in ('validate', 'digest'):
            completed = subprocess.run([sys.executable, str(SCRIPT), command, '--input', str(self.record)],
                text=True, capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
        completed = subprocess.run([sys.executable, str(SCRIPT), 'accept', '--input', str(self.record),
            '--project-root', str(self.project), '--repository', 'app', '--operation', 'push'],
            text=True, capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result['status'], 'legacy')
        self.assert_sealed(result)

    def test_unpaired_unicode_surrogate_blocks_without_unsealed_exception(self):
        self.configured()
        self.subject.write_text('{"kind":"commit","identity":"\\ud800"}', encoding='ascii')
        result = self.accept(decision_path=self.decision, subject_path=self.subject)
        self.assert_blocked(result, 'invalid_policy_context')
        self.assertIsNone(result['subject'])

    def test_malformed_nested_schema_blocks_before_import(self):
        runtime = self.runtime_copy()
        sentinel = self.root / 'nested-schema-import-executed'
        loader = runtime / 'scripts/project_policy.py'
        loader.write_text("from pathlib import Path\nPath(" + repr(str(sentinel)) +
            ").write_text('executed')\nraise AssertionError('unsafe import executed')", encoding='utf-8')
        path = runtime / 'schemas/development-test-first-binding.schema.json'
        schema = json.loads(path.read_text(encoding='utf-8'))
        schema['properties']['schema_version']['type'] = 'unsupported_type'
        path.write_text(json.dumps(schema), encoding='utf-8')
        self.assert_blocked(self.accept(policy_runtime_root=runtime), 'invalid_runtime')
        self.assertFalse(sentinel.exists(), 'Malformed required schema must block before module execution')

    def test_isolated_metadata_mismatch_blocks_before_import(self):
        consumer = self.root / 'isolated/develop-with-test-first-evidence'
        runtime = self.root / 'isolated/verify-before-push'
        shutil.copytree(CONSUMER, consumer)
        shutil.copytree(PROVIDER, runtime)
        sentinel = self.root / 'metadata-import-executed'
        (runtime / 'scripts/project_policy.py').write_text(
            "from pathlib import Path\nPath(" + repr(str(sentinel)) +
            ").write_text('executed')\nraise AssertionError('unsafe import executed')", encoding='utf-8')
        path = runtime / 'collection-metadata.json'
        value = json.loads(path.read_text(encoding='utf-8'))
        value['collection'] = 'other-collection'
        path.write_text(json.dumps(value), encoding='utf-8')
        adapter = load(consumer / 'scripts/policy_evidence.py', 'isolated_metadata_adapter')
        self.assert_blocked(adapter.accept_records(self.record, self.project, 'app', 'push',
            legacy_validator=self.validator.validate), 'invalid_runtime')
        self.assertFalse(sentinel.exists())

    def test_standalone_consumer_validator_snapshot_and_postcheck(self):
        consumer = self.root / 'standalone-snapshots/develop-with-test-first-evidence'
        shutil.copytree(CONSUMER, consumer)
        adapter = load(consumer / 'scripts/policy_evidence.py', 'standalone_snapshots_adapter')
        validator = load(consumer / 'scripts/evidence.py', 'standalone_snapshots_validator')
        result = adapter.accept_records(self.record, self.project, 'app', 'push',
            legacy_validator=validator.validate)
        self.assertEqual(result['status'], 'legacy')
        provenance = result['consumer_provenance']
        self.assertEqual(provenance['file_sha256']['scripts/evidence.py'],
            hashlib.sha256((consumer / 'scripts/evidence.py').read_bytes()).hexdigest())
        self.assertEqual(provenance['validator_artifact']['path'],
            str((consumer / 'scripts/evidence.py').resolve()))
        validator_path = consumer / 'scripts/evidence.py'
        def mutate(data):
            validator_path.write_bytes(validator_path.read_bytes() + b'\n# changed during validation\n')
            return validator.validate(data)
        self.assert_blocked(adapter.accept_records(self.record, self.project, 'app', 'push',
            legacy_validator=mutate), 'runtime_changed')

    def test_excessive_json_nesting_is_sealed_blocked_input(self):
        depth = max(10000, sys.getrecursionlimit() * 10)
        self.record.write_text('{"x":' + '[' * depth + '0' + ']' * depth + '}', encoding='ascii')
        self.assert_blocked(self.accept(), 'invalid_input')

    def test_excessive_context_nesting_and_invalid_subject_are_not_echoed(self):
        self.configured()
        depth = max(10000, sys.getrecursionlimit() * 10)
        self.subject.write_text('{"x":' + '[' * depth + '0' + ']' * depth + '}', encoding='ascii')
        self.assert_blocked(self.accept(decision_path=self.decision, subject_path=self.subject),
            'invalid_policy_context')
        self.subject.write_text('{"private_token":"SENTINEL_ONLY"}', encoding='ascii')
        result = self.accept(decision_path=self.decision, subject_path=self.subject)
        self.assert_blocked(result)
        self.assertIsNone(result['subject'])
        self.assertNotIn('SENTINEL_ONLY', json.dumps(result))

    def test_runtime_input_schema_missing_subject_does_not_crash(self):
        self.configured()
        runtime = self.runtime_copy()
        path = runtime / 'schemas/development-final-verification.schema.json'
        schema = json.loads(path.read_text(encoding='utf-8'))
        schema['properties'].pop('subject')
        schema['required'].remove('subject')
        path.write_text(json.dumps(schema), encoding='utf-8')
        result = self.accept(policy_runtime_root=runtime,
            decision_path=self.decision, subject_path=self.subject)
        self.assertEqual(result['status'], 'accepted', result)
        self.assertEqual(result['subject'], result['provider_result']['bindings']['subject'])
        self.assert_sealed(result)

    def test_permissive_runtime_subject_schema_never_echoes_rejected_input(self):
        self.configured()
        runtime = self.runtime_copy()
        path = runtime / 'schemas/development-final-verification.schema.json'
        schema = json.loads(path.read_text(encoding='utf-8'))
        schema['properties']['subject'] = {}
        path.write_text(json.dumps(schema), encoding='utf-8')
        self.subject.write_text('{"private_token":"SENTINEL_ONLY"}', encoding='ascii')
        result = self.accept(policy_runtime_root=runtime,
            decision_path=self.decision, subject_path=self.subject)
        self.assert_blocked(result)
        self.assertIsNone(result['subject'])
        self.assertNotIn('SENTINEL_ONLY', json.dumps(result))


class AcceptanceCliGapTests(unittest.TestCase):
    def test_valid_legacy_record_is_accepted_without_project_policy(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            record = project / 'legacy-evidence.json'
            record.write_text(json.dumps(legacy()), encoding='utf-8')
            completed = subprocess.run([sys.executable, str(SCRIPT), 'accept', '--input', str(record),
                '--project-root', str(project), '--repository', 'app', '--operation', 'push'],
                text=True, capture_output=True)
            self.assertEqual(completed.returncode, 0,
                'Valid original v1 evidence must remain acceptable without policy: ' + completed.stderr)
            self.assertEqual(json.loads(completed.stdout)['status'], 'legacy')

    def test_accept_command_exposes_explicit_policy_context(self):
        completed = subprocess.run([sys.executable, str(SCRIPT), 'accept', '--help'],
            text=True, capture_output=True)
        self.assertEqual(completed.returncode, 0,
            'Evidence CLI has no policy-aware accept command: ' + completed.stderr)
        for option in ('--project-root', '--repository', '--operation', '--profile', '--decision',
                       '--previous-decision', '--subject', '--policy-runtime-root'):
            self.assertIn(option, completed.stdout)


if __name__ == '__main__':
    unittest.main()
