"""Behavioral contract for the read-only project policy diagnostic foundation."""
import copy
import datetime
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/verify-before-push/scripts/project_policy.py'
SCHEMA = SCRIPT.parent.parent / 'schemas/project-policy.schema.json'
POLICY_PATH = '.agents/kolabse/project-policy.json'


def standard():
    return {
        'schema_version': 1,
        'verification': {'required_at': 'before_push', 'execution': 'local',
                         'provider': 'none', 'subject': 'source_sha',
                         'local_execution': 'allowed', 'reuse_successful_result': True},
        'development': {'evidence_mode': 'test_first'},
        'publication': {'draft_until': 'implementation_and_source_review_complete',
                        'pipeline': {'event': 'push', 'target_branch': 'main',
                                     'require_ready': True, 'bootstrap': 'suppress',
                                     'duplicate_active_run': 'forbidden'}},
        'documentation': {'source_updates': 'required', 'web': {
            'trigger': 'explicit_request', 'blocks_primary_task': False,
            'execution': 'ci', 'runner_tag': 'docs', 'require_success_for_published_sha': True}}}


def cloud():
    value = standard()
    value['verification'].update(required_at='before_merge', execution='ci',
                                 provider='gitlab', local_execution='forbidden')
    value['development']['evidence_mode'] = 'final_verification'
    value['publication']['pipeline']['event'] = 'merge_request'
    return value


class ProjectPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assertTrue(SCRIPT.is_file(), 'read-only policy diagnostic entry point is not implemented')
        spec = importlib.util.spec_from_file_location('policy_under_test', SCRIPT)
        self.policy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.policy)

    def write(self, value, path=POLICY_PATH):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((value if isinstance(value, str) else json.dumps(value)).encode('utf-8'))
        return target

    def load(self, **kwargs):
        return self.policy.load_project_policy(self.root, repository='app', operation='push', **kwargs)

    def test_absent_sentinel_and_non_enforcement(self):
        value = self.load()
        self.assertEqual(value['status'], 'absent')
        self.assertIsNone(value['effective_policy'])
        self.assertEqual(value['compatibility_mode'], 'legacy')
        self.assertEqual(value['execution_integration'], 'unavailable')

    def test_standard_and_cloud_declarations_are_not_provider_evidence(self):
        for document in (standard(), cloud()):
            self.write(document)
            value = self.load()
            self.assertEqual(value['status'], 'configured', value)
            self.assertEqual(value['effective_policy'], document)
            self.assertEqual(value['constraints_status'], 'declared')
            self.assertEqual(value['provider_confirmation'], 'unconfirmed')
            self.assertEqual(value['origins']['/verification/execution']['value'], document['verification']['execution'])

    def test_effective_and_source_digest_have_distinct_meanings(self):
        target = self.write(standard())
        first = self.load()
        target.write_text(json.dumps(standard(), sort_keys=True, indent=4), encoding='utf-8')
        second = self.load()
        self.assertEqual(first['effective_digest'], second['effective_digest'])
        self.assertNotEqual(first['source_snapshot_digest'], second['source_snapshot_digest'])
        changed = standard()
        changed['verification']['reuse_successful_result'] = False
        self.write(changed)
        self.assertNotEqual(first['effective_digest'], self.load()['effective_digest'])

    def test_strict_closed_contract_and_no_fallback(self):
        for pointer, value in [('/schema_version', True), ('/schema_version', 2),
                               ('/verification/provider', 'unknown'),
                               ('/verification/execution', []),
                               ('/verification/reuse_successful_result', 1),
                               ('/documentation/web/runner_tag', ''),
                               ('/publication/pipeline/require_ready', 'yes')]:
            document = standard()
            parent = document
            keys = pointer.strip('/').split('/')
            for key in keys[:-1]:
                parent = parent[key]
            parent[keys[-1]] = value
            self.write(document)
            result = self.load()
            self.assertEqual(result['status'], 'invalid', (pointer, result))
            self.assertIsNone(result['effective_policy'])
            self.assertTrue(any(d['pointer'] == pointer for d in result['diagnostics']))
        for raw in ['[]', '{"schema_version":1,"schema_version":1}', '{bad json}']:
            self.write(raw)
            self.assertEqual(self.load()['status'], 'invalid')
        document = standard()
        document['token'] = 'secret-do-not-echo'
        self.write(document)
        result = self.load()
        self.assertEqual(result['status'], 'invalid')
        self.assertNotIn('secret-do-not-echo', json.dumps(result))

    def test_unsupported_and_ambiguous_files(self):
        self.write('schema_version: 1', '.agents/kolabse/project-policy.yaml')
        self.assertEqual(self.load()['diagnostics'][0]['code'], 'unsupported_format')
        self.write(standard())
        self.assertEqual(self.load()['diagnostics'][0]['code'], 'ambiguous_policy')

    def test_unsafe_symlink_cannot_escape_project(self):
        outside = self.root.parent / (self.root.name + '-outside.json')
        outside.write_text(json.dumps(standard()), encoding='utf-8')
        self.addCleanup(lambda: outside.unlink(missing_ok=True))
        target = self.root / POLICY_PATH
        target.parent.mkdir(parents=True)
        try:
            target.symlink_to(outside)
        except OSError:
            self.skipTest('symlink privilege unavailable')
        self.assertEqual(self.load()['diagnostics'][0]['code'], 'unsafe_path')

    def test_cross_field_conflicts(self):
        cases = []
        value = standard(); value['verification']['local_execution'] = 'forbidden'; cases.append(value)
        value = standard(); value['verification']['provider'] = 'gitlab'; cases.append(value)
        value = cloud(); value['verification']['provider'] = 'none'; cases.append(value)
        for value in cases:
            self.write(value)
            self.assertEqual(self.load()['status'], 'invalid')

    def profile(self, **changes):
        profile = {'version': 1, 'reason': 'controlled migration',
                   'scope': {'repositories': ['app'], 'operations': ['push']},
                   'overrides': {'development': {'evidence_mode': 'final_verification'}},
                   'expires_on': '2030-01-01'}
        profile.update(changes)
        value = standard(); value['profiles'] = {'migration': profile}
        self.write(value)

    def test_profiles_explicit_scoped_expiring_and_origin_bound(self):
        self.profile()
        self.assertEqual(self.load()['effective_policy']['development']['evidence_mode'], 'test_first')
        result = self.load(profile='migration', today=datetime.date(2026, 1, 1))
        self.assertEqual(result['effective_policy']['development']['evidence_mode'], 'final_verification')
        self.assertEqual(result['active_profile'], 'migration')
        self.assertEqual(result['origins']['/development/evidence_mode']['source_pointer'],
                         '/profiles/migration/overrides/development/evidence_mode')
        for kwargs in ({'profile': 'unknown'}, {'profile': 'migration', 'today': datetime.date(2031, 1, 1)}):
            self.assertEqual(self.load(**kwargs)['status'], 'invalid')
        isolated = self.policy.load_project_policy(self.root, repository='other', operation='push', profile='migration')
        self.assertEqual(isolated['status'], 'invalid')
        self.profile(expires_on='2030-01-01', review_condition='migration complete')
        self.assertIn('profile_review_unconfirmed', [d['code'] for d in self.load(profile='migration')['diagnostics']])

    def test_legacy_conflicts_are_scoped_and_dual_capability_is_not_conflict(self):
        self.write(cloud())
        self.write({'version': 1, 'checks': [{'name': 'unit', 'required': True, 'command': ['python', 'tests.py']}],
                    'github_ci': {'checks': {'unit': {'workflow': 'check.yml', 'jobs': ['unit']}}}},
                   '.agents/verify-before-push/config.json')
        result = self.load()
        self.assertEqual(result['status'], 'configured')
        self.assertNotIn('legacy_local_execution', [d['code'] for d in result['diagnostics']])
        self.write({'version': 1, 'gates': [{'id': 'tdd-red', 'required': True}]},
                   '.agents/execute-verified-development-lifecycle/config.json')
        result = self.load()
        conflict = next(d for d in result['diagnostics'] if d['code'] == 'legacy_tdd_red')
        self.assertEqual(len(conflict['sources']), 2)
        self.assertIn('merge', conflict['affected_operations'])
        self.assertNotIn('cleanup', result['dependent_action_blockers'])

    def test_managed_blocks_and_custom_rules_remain_visible(self):
        self.write(cloud())
        text = '<!-- verify-before-push:start -->\n## Verification before push\n\nUse `$verify-before-push` before pushing protected repositories. Run the\nproject-declared checks and require current evidence bound to the exact Git\ncommits and worktrees being pushed. Treat missing, failed, malformed, or\nstale evidence as a stop condition for a protected push.\n<!-- verify-before-push:end -->\nCustom build requirement.\n'
        self.write(text, 'AGENTS.md')
        result = self.load()
        self.assertIn('legacy_before_push', [d['code'] for d in result['diagnostics']])
        self.assertIn('instructions_need_review', [d['code'] for d in result['diagnostics']])
        self.assertEqual(result['legacy_inputs']['AGENTS.md']['managed_blocks'][0]['text'], text.split('Custom')[0].rstrip('\n'))

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_commands_and_migration_have_no_execution_network_or_write_effects(self):
        self.write(standard())
        self.write('Arbitrary custom text\r\n', 'CLAUDE.md')
        before = self.snapshot()
        with patch('subprocess.run', side_effect=AssertionError('execution')), \
             patch('socket.socket', side_effect=AssertionError('network')), \
             patch('pathlib.Path.write_text', side_effect=AssertionError('write')), \
             patch('pathlib.Path.write_bytes', side_effect=AssertionError('write')):
            for command in ('status', 'explain', 'validate', 'migrate'):
                argv = [command, '--project-root', str(self.root), '--repository', 'app', '--json']
                if command == 'migrate': argv.append('--dry-run')
                out = io.StringIO()
                with patch('sys.stdout', out):
                    self.assertEqual(self.policy.main(argv), 0)
                value = json.loads(out.getvalue())
                self.assertEqual(value['execution_integration'], 'unavailable')
            first = self.policy.migration_preview(self.root, self.load())
            self.assertEqual(first, self.policy.migration_preview(self.root, self.load()))
            self.assertTrue(first['no_op'])
            self.assertEqual(first['proposed_document'], standard())
        self.assertEqual(before, self.snapshot())
        self.assertEqual(first['preserved_content']['CLAUDE.md'], 'Arbitrary custom text\r\n')

    def test_migration_missing_policy_does_not_invent_contract_or_evidence(self):
        result = self.policy.migration_preview(self.root, self.load())
        self.assertIsNone(result['proposed_document'])
        self.assertTrue(result['unresolved_choices'])
        self.assertNotIn('evidence', result)
        with patch('sys.stdout', io.StringIO()), patch('sys.stderr', io.StringIO()):
            with self.assertRaises(SystemExit):
                self.policy.main(['migrate', '--project-root', str(self.root)])

    def test_customized_managed_marker_is_not_machine_interpreted(self):
        self.write(cloud())
        self.write('<!-- verify-before-push:start -->\nOptional checks after merge.\n<!-- verify-before-push:end -->', 'AGENTS.md')
        value = self.load()
        self.assertNotIn('legacy_before_push', [d['code'] for d in value['diagnostics']])
        self.assertIn('instructions_need_review', [d['code'] for d in value['diagnostics']])
        preview = self.policy.migration_preview(self.root, value)
        self.assertEqual(preview['managed_block_edits'], [])

    def test_caller_assertions_bound_conflicts_to_repository_operation_and_sources(self):
        self.write(cloud())
        assertions = [{'repository': 'app', 'operations': ['push'],
                       'declaration': 'bootstrap_run_pipeline_fallback',
                       'source_path': 'AGENTS.md', 'source_pointer': '', 'line': 7},
                      {'repository': 'app', 'operations': ['deploy'],
                       'declaration': 'website_required_for_task_completion',
                       'source_path': 'CLAUDE.md', 'source_pointer': '', 'line': 9}]
        result = self.load(legacy_assertions=assertions)
        conflicts = {d['code']: d for d in result['diagnostics']}
        self.assertEqual(conflicts['legacy_bootstrap_fallback']['sources'][1]['line'], 7)
        self.assertEqual(conflicts['legacy_website_required']['affected_operations'], ['deploy'])
        isolated = self.policy.load_project_policy(self.root, repository='other', operation='push', legacy_assertions=assertions)
        self.assertEqual(isolated['dependent_action_blockers'], {})
        changed = copy.deepcopy(assertions); changed[0]['line'] = 8
        self.assertNotEqual(result['source_snapshot_digest'], self.load(legacy_assertions=changed)['source_snapshot_digest'])
        self.assertEqual(result['effective_digest'], self.load(legacy_assertions=changed)['effective_digest'])
        invalid = copy.deepcopy(assertions); invalid[0]['source_path'] = '../private.md'
        self.assertEqual(self.load(legacy_assertions=invalid)['status'], 'invalid')

    def test_malformed_legacy_lists_are_review_diagnostics_without_crashing(self):
        self.write(cloud())
        for path, value in [('.agents/verify-before-push/config.json', {'checks': None}),
                            ('.agents/execute-verified-development-lifecycle/config.json', {'gates': 3})]:
            self.write(value, path)
        result = self.load()
        self.assertEqual(result['status'], 'configured')
        self.assertIn('legacy_input_unreadable', [d['code'] for d in result['diagnostics']])

    def test_cli_invalid_policy_returns_nonzero_without_mutating_snapshot(self):
        self.write({'schema_version': 123})
        before = self.snapshot()
        for command in ('status', 'validate', 'explain', 'migrate'):
            argv = [command, '--project-root', str(self.root), '--json']
            if command == 'migrate': argv.append('--dry-run')
            with patch('sys.stdout', io.StringIO()) as out:
                self.assertEqual(self.policy.main(argv), 2)
            self.assertEqual(json.loads(out.getvalue())['status'], 'invalid')
        self.assertEqual(before, self.snapshot())

    def test_invalid_scope_never_exposes_an_effective_policy(self):
        self.write(standard())
        value = self.policy.load_project_policy(self.root, repository='app', operation='unknown')
        self.assertEqual(value['status'], 'invalid')
        self.assertIsNone(value['effective_policy'])
        self.assertIsNone(value['effective_digest'])

    def test_legacy_non_object_input_is_diagnostic(self):
        self.write(cloud())
        self.write([], '.agents/verify-before-push/config.json')
        value = self.load()
        self.assertIn('legacy_input_unreadable', [d['code'] for d in value['diagnostics']])

    def test_closed_schema_walker_enforces_cross_fields_and_whitespace(self):
        schema = json.loads(SCHEMA.read_text(encoding='utf-8'))
        cases = []
        value = standard(); value['verification']['local_execution'] = 'forbidden'; cases.append(value)
        value = standard(); value['verification']['provider'] = 'gitlab'; cases.append(value)
        value = cloud(); value['verification']['provider'] = 'none'; cases.append(value)
        value = standard(); value['publication']['pipeline']['target_branch'] = '   '; cases.append(value)
        for value in cases:
            self.assertTrue(self.policy._validate(value, schema), value)
        self.assertFalse(self.policy._validate(standard(), schema))
        self.assertFalse(self.policy._validate(cloud(), schema))

    def test_migration_never_proposes_execution_rule_changes(self):
        block = self.policy.VERIFY_BLOCK
        self.write(block + '\r\ncustom prose\r\n', 'AGENTS.md')
        for value in (None, standard(), cloud(), {'schema_version': 99}):
            target = self.root / POLICY_PATH
            if value is None:
                target.unlink(missing_ok=True)
            else:
                self.write(value)
            result = self.policy.migration_preview(self.root, self.load())
            self.assertEqual(result['managed_block_edits'], [])
            self.assertEqual(result['preserved_content']['AGENTS.md'], block + '\r\ncustom prose\r\n')

    def test_invalid_project_root_does_not_look_like_absent_policy(self):
        for target in (self.root / 'missing', self.write('ordinary file', 'file.txt')):
            result = self.policy.load_project_policy(target, repository='app', operation='push')
            self.assertEqual(result['status'], 'invalid')
            self.assertEqual(result['diagnostics'][0]['code'], 'invalid_project_root')

    def test_optional_enabled_local_checks_conflict_but_disabled_checks_do_not(self):
        self.write(cloud())
        path = '.agents/verify-before-push/config.json'
        check = {'name': 'optional', 'required': False, 'enabled': True, 'command': ['python', 'optional.py']}
        self.write({'checks': [check]}, path)
        value = self.load()
        self.assertIn('legacy_local_execution', [d['code'] for d in value['diagnostics']])
        self.assertNotIn('legacy_before_push', [d['code'] for d in value['diagnostics']])
        check.update(enabled=False, skip_reason='explicitly deferred')
        self.write({'checks': [check]}, path)
        value = self.load()
        self.assertNotIn('legacy_local_execution', [d['code'] for d in value['diagnostics']])

    def test_migration_preserves_utf8_bom_and_line_endings(self):
        self.write(standard())
        content = '\ufeffCustom instructions\r\nDo the declared work.\n'
        target = self.write(content, 'AGENTS.md')
        result = self.policy.migration_preview(self.root, self.load())
        self.assertEqual(result['preserved_content']['AGENTS.md'].encode('utf-8'), target.read_bytes())

    def test_local_documentation_build_conflicts_with_global_local_prohibition(self):
        value = cloud(); value['documentation']['web']['execution'] = 'local'
        self.write(value)
        result = self.load()
        self.assertEqual(result['status'], 'invalid')
        conflict = next(d for d in result['diagnostics'] if d['code'] == 'contradictory_fields')
        self.assertEqual({source['pointer'] for source in conflict['sources']},
                         {'/verification/local_execution', '/documentation/web/execution'})

    def test_custom_prose_is_advisory_without_changing_absent_legacy_semantics(self):
        self.write('Custom instructions whose execution scope is unconfirmed.\n', 'AGENTS.md')
        for document in (None, standard()):
            if document is not None:
                self.write(document)
            result = self.load()
            self.assertEqual(result['status'], 'absent' if document is None else 'configured')
            self.assertEqual(result['dependent_action_blockers'], {})
            review = next(d for d in result['diagnostics'] if d['code'] == 'instructions_need_review')
            self.assertFalse(review['blocking'])
            self.assertEqual(review['affected_operations'], ['push'])

    def test_installed_skill_cli_and_schema_are_self_contained(self):
        installed = self.root / 'installed'
        shutil.copytree(SCRIPT.parent.parent, installed)
        self.write(standard())
        for command in ('status', 'validate', 'explain'):
            run = subprocess.run([sys.executable, str(installed / 'scripts/project_policy.py'), command,
                                  '--project-root', str(self.root), '--json'], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)['status'], 'configured')
        schema = json.loads(SCHEMA.read_text(encoding='utf-8'))
        self.assertFalse(schema['additionalProperties'])
        self.assertEqual(schema['properties']['schema_version']['const'], 1)


if __name__ == '__main__':
    unittest.main()
