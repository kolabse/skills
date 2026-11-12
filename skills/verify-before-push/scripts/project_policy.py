#!/usr/bin/env python3
"""Read-only project-policy resolver. Never executes checks or changes project files.

Configured policies describe intent only; the canonical verifier blocks their
execution until policy-bound receipt support is implemented.
The standard-library schema walker intentionally implements only the vocabulary
used by the bundled closed schemas; adding vocabulary requires a validator change.
"""
from __future__ import annotations

import argparse
import copy
from datetime import date
import hashlib
import json
from pathlib import Path
import re

POLICY = '.agents/kolabse/project-policy.json'
CANDIDATES = (POLICY, '.agents/kolabse/project-policy.yaml', '.agents/kolabse/project-policy.yml')
OPERATIONS = ('push', 'merge', 'build', 'deploy', 'cleanup')
LEGACY = ('.agents/verify-before-push/config.json',
          '.agents/execute-verified-development-lifecycle/config.json',
          '.agents/develop-with-test-first-evidence/config.json', 'AGENTS.md', 'CLAUDE.md')
# Exact supported generated text; a marker around custom prose is not a rule parser.
VERIFY_BLOCK = '''<!-- verify-before-push:start -->
## Verification before push

Use `$verify-before-push` before pushing protected repositories. Run the
project-declared checks and require current evidence bound to the exact Git
commits and worktrees being pushed. Treat missing, failed, malformed, or
stale evidence as a stop condition for a protected push.
<!-- verify-before-push:end -->'''
MANAGED = ('verify-before-push', 'develop-with-test-first-evidence',
           'execute-verified-development-lifecycle', 'synchronize-git-repositories')


CHANGE_TYPES = ('added', 'modified', 'deleted', 'renamed', 'type_changed')


def portable_path(value, *, glob=False):
    """Validate repository-relative POSIX paths and the closed segment glob syntax."""
    if (not isinstance(value, str) or not value or value.startswith('/') or '\\' in value
            or ':' in value or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        return False
    parts = value.split('/')
    if any(part in ('', '.', '..') for part in parts):
        return False
    if glob and (any(c in value for c in '?[]{}!')
                 or any('**' in part and part != '**' for part in parts)):
        return False
    return True


def _catalog_error(pointer, message):
    return {'code': 'invalid_check_catalog', 'severity': 'error', 'path': POLICY,
            'pointer': pointer, 'message': message, 'affected_operations': list(OPERATIONS)}


def _catalog_errors(document):
    errors = []
    verification = document.get('verification', {})
    catalogs = [('/verification/checks', verification.get('checks'))] if isinstance(verification, dict) else []
    profiles = document.get('profiles', {})
    if isinstance(profiles, dict):
        for name, profile in profiles.items():
            if isinstance(profile, dict) and isinstance(profile.get('overrides'), dict):
                v = profile['overrides'].get('verification', {})
                if isinstance(v, dict) and 'checks' in v:
                    catalogs.append((_pointer('/profiles', name) + '/overrides/verification/checks', v['checks']))
    for pointer, checks in catalogs:
        if not isinstance(checks, list):
            continue
        seen = set()
        for i, check in enumerate(checks):
            if not isinstance(check, dict):
                continue
            ident = check.get('id')
            if isinstance(ident, str):
                if not ident.strip() or any(ord(c) < 32 or ord(c) == 127 for c in ident) or ident in seen:
                    errors.append(_catalog_error(pointer + '/' + str(i) + '/id', 'Check IDs must be nonblank, control-free and unique'))
                seen.add(ident)
            scope = check.get('scope', {})
            if isinstance(scope, dict):
                for key in ('include_paths', 'exclude_paths'):
                    if isinstance(scope.get(key), list):
                        for n, pattern in enumerate(scope[key]):
                            if not portable_path(pattern, glob=True):
                                errors.append(_catalog_error(pointer + '/' + str(i) + '/scope/' + key + '/' + str(n), 'Unsupported portable path pattern'))
    return errors


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode('utf-8')).hexdigest()


def _pointer(parent, key):
    return parent + '/' + str(key).replace('~', '~0').replace('/', '~1')


def _safe(root, relative):
    path = root / relative
    if not path.resolve().is_relative_to(root):
        raise ValueError('Source resolves outside the selected project root')
    return path


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON object key')
        result[key] = value
    return result


def _parse(raw):
    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite JSON number')))


def _validate(value, schema, pointer='', *, path=POLICY):
    """Validate the bundled JSON Schema subset without coercion or dependencies."""
    errors = []
    def fail(code='invalid_value', message='Value does not satisfy the v1 schema', at=pointer):
        errors.append({'code': code, 'severity': 'error', 'path': path,
                       'pointer': at, 'message': message, 'affected_operations': list(OPERATIONS)})
    kind = schema.get('type')
    valid = {'object': isinstance(value, dict), 'array': isinstance(value, list),
             'string': isinstance(value, str), 'boolean': type(value) is bool,
             'integer': type(value) is int}.get(kind, True)
    if not valid:
        fail('invalid_type', 'Expected ' + kind)
        return errors
    if 'const' in schema and value != schema['const']:
        fail('unsupported_version', 'Unsupported schema/profile version')
    if 'enum' in schema and value not in schema['enum']:
        fail('unsupported_value', 'Unsupported value; consult the bundled schema')
    if kind == 'object':
        for key in schema.get('required', []):
            if key not in value:
                fail('missing_field', 'Required field is missing', _pointer(pointer, key))
        for key, child in value.items():
            child_schema = schema.get('properties', {}).get(key, schema.get('additionalProperties', True))
            if child_schema is False:
                fail('unknown_field', 'Unknown field (value withheld)', _pointer(pointer, key))
            elif isinstance(child_schema, dict):
                errors.extend(_validate(child, child_schema, _pointer(pointer, key), path=path))
            if 'propertyNames' in schema and not re.fullmatch(schema['propertyNames']['pattern'], key):
                fail('invalid_name', 'Invalid profile name', pointer)
        if 'anyOf' in schema and not any(all(key in value for key in option['required']) for option in schema['anyOf']):
            fail('missing_review_boundary', 'Profile requires expires_on or review_condition')
    if kind == 'array':
        if len(value) < schema.get('minItems', 0):
            fail('empty_scope', 'Scope must not be empty')
        if schema.get('uniqueItems') and len({json.dumps(item, sort_keys=True) for item in value}) != len(value):
            fail('duplicate_scope', 'Scope entries must be unique')
        for index, child in enumerate(value):
            errors.extend(_validate(child, schema['items'], _pointer(pointer, index), path=path))
    for clause in schema.get('allOf', []):
        if 'not' in clause and not _validate(value, clause['not'], pointer, path=path):
            pointers = clause.get('x-conflict-pointers', [pointer])
            fail('contradictory_fields', clause.get('description', 'Contradictory fields'), pointers[0])
            errors[-1]['sources'] = [{'path': path, 'pointer': p} for p in pointers]
    if kind == 'string':
        if 'pattern' in schema and re.search(schema['pattern'], value) is None:
            fail('invalid_string', 'String must satisfy the declared schema pattern')
        if len(value.strip()) < schema.get('minLength', 0):
            fail('empty_value', 'String must not be blank')
        if schema.get('format') == 'date':
            try:
                parsed = date.fromisoformat(value)
                if parsed.isoformat() != value:
                    raise ValueError()
            except ValueError:
                fail('invalid_date', 'Expected calendar date YYYY-MM-DD')
    return errors


def _leaves(value, pointer=''):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _leaves(child, _pointer(pointer, key))
    else:
        yield pointer, value


def _merge(target, override):
    for key, value in override.items():
        if isinstance(value, dict):
            _merge(target[key], value)
        else:
            target[key] = copy.deepcopy(value)


def _cross_fields(effective):
    v = effective['verification']
    pairs = []
    if v['execution'] == 'local' and v['local_execution'] == 'forbidden':
        pairs.append(('/verification/execution', '/verification/local_execution', 'Local execution is forbidden'))
    if (v['execution'] == 'local') != (v['provider'] == 'none'):
        pairs.append(('/verification/execution', '/verification/provider', 'Local requires provider none; CI requires github or gitlab'))
    if v['execution'] == 'local' and v['subject'] != 'source_sha':
        pairs.append(('/verification/execution', '/verification/subject', 'Local verification supports source_sha only'))
    if v['local_execution'] == 'forbidden' and effective['documentation']['web']['execution'] == 'local':
        pairs.append(('/verification/local_execution', '/documentation/web/execution', 'Local documentation execution is forbidden'))
    return pairs


def _legacy(root, result, snapshots):
    """Read only bounded known inputs. Never infer execution from shell substrings."""
    for relative in LEGACY:
        try:
            path = _safe(root, relative)
            if not path.exists():
                continue
            raw = path.read_bytes()
            snapshots[relative] = hashlib.sha256(raw).hexdigest()
            entry = {'sha256': snapshots[relative]}
            result['legacy_inputs'][relative] = entry
            if relative.endswith('.json'):
                entry['document'] = _parse(raw)
                if not isinstance(entry['document'], dict):
                    del entry['document']
                    raise ValueError('Legacy configuration must be an object')
                for field in ('checks', 'gates'):
                    if field in entry['document'] and (not isinstance(entry['document'][field], list)
                            or not all(isinstance(item, dict) for item in entry['document'][field])):
                        del entry['document']
                        raise ValueError('Malformed legacy collection')
            else:
                text = raw.decode('utf-8')
                entry['text'] = text
                blocks = []
                remainder = text
                for name in MANAGED:
                    pattern = re.compile(r'<!-- ' + re.escape(name) + r':start -->.*?<!-- ' + re.escape(name) + r':end -->', re.S)
                    for match in pattern.finditer(text):
                        normalized = match.group().replace('\r\n', '\n')
                        recognized = normalized in (VERIFY_BLOCK, VERIFY_BLOCK.replace('`$verify-before-push`', '`/verify-before-push`'))
                        blocks.append({'name': name, 'text': match.group(),
                                       'line': text[:match.start()].count('\n') + 1, 'recognized': recognized})
                        if recognized:
                            remainder = remainder.replace(match.group(), '', 1)
                entry['managed_blocks'] = sorted(blocks, key=lambda block: block['line'])
                if remainder.strip():
                    result['diagnostics'].append({'code': 'instructions_need_review', 'severity': 'needs_review',
                        'path': relative, 'pointer': '', 'message': 'Custom instructions require bounded human review; text is not machine interpreted',
                        'affected_operations': [result['operation']]})
        except (OSError, ValueError, UnicodeError):
            result['diagnostics'].append({'code': 'legacy_input_unreadable', 'severity': 'needs_review',
                'path': relative, 'pointer': '', 'message': 'Legacy input is unsafe, malformed or unreadable',
                'affected_operations': [result['operation']]})


def _conflicts(result, assertions):
    policy = result['effective_policy']
    if policy is None:
        return
    v = policy['verification']
    def conflict(code, pointer, source, legacy_pointer, operations, message, line=None):
        origin = result['origins'][pointer]
        sources = [{'path': origin['source_path'], 'pointer': origin['source_pointer']},
                   {'path': source, 'pointer': legacy_pointer}]
        if line is not None:
            sources[1]['line'] = line
        result['diagnostics'].append({'code': code, 'severity': 'conflict', 'path': POLICY,
            'pointer': pointer, 'sources': sources, 'affected_operations': operations,
            'message': message, 'resolution': 'Reconcile the explicit declarations before the affected action; no legacy gate is weakened'})
    timing_pointer = '/verification/required_at' if policy['schema_version'] == 1 else '/verification/checks'
    def push_weakened(names=None):
        if policy['schema_version'] == 1:
            return v['required_at'] == 'before_merge'
        catalog = v['checks']
        if names is not None and not all(isinstance(name, str) and name.strip() for name in names):
            return True
        selected = [c for c in catalog if c['id'] in names] if names is not None else [c for c in catalog if c['blocks']]
        if not selected or (names is not None and {c['id'] for c in selected} != set(names)):
            return True
        return any('push' not in c['blocks'] or c['scope']['repositories'] != [result['repository']]
                   or c['scope']['include_paths'] != ['**'] or c['scope']['exclude_paths']
                   or set(c['scope']['change_types']) != set(CHANGE_TYPES) for c in selected)
    for path, entry in result['legacy_inputs'].items():
        doc = entry.get('document', {})
        if path.endswith('verify-before-push/config.json'):
            # Local commands plus a CI mapping describe dual capability, not selected execution.
            commands = [(i, c) for i, c in enumerate(doc.get('checks', []))
                        if c.get('enabled', True) is True and c.get('command')]
            required = [(i, c) for i, c in commands if c.get('required', True) is True]
            ci_capability = doc.get('github_ci') or (policy['schema_version'] == 2 and isinstance(doc.get('gitlab_ci'), dict) and doc['gitlab_ci'].get('version') == 2)
            if not ci_capability:
                if commands and v['local_execution'] == 'forbidden':
                    conflict('legacy_local_execution', '/verification/local_execution', path,
                             f'/checks/{commands[0][0]}/command', ['push'], 'Legacy push verification executes local commands')
                if required and push_weakened([c.get('name') for _, c in required]):
                    conflict('legacy_before_push', timing_pointer, path,
                             f'/checks/{required[0][0]}/required', ['push'], 'Legacy verifier still requires checks before push')
            if policy['schema_version'] == 2 and ci_capability and required and push_weakened([c.get('name') for _, c in required]):
                conflict('legacy_before_push', timing_pointer, path,
                         f'/checks/{required[0][0]}/required', ['push'], 'Legacy verifier still requires checks before push')
        if path.endswith('execute-verified-development-lifecycle/config.json'):
            for index, gate in enumerate(doc.get('gates', [])):
                if isinstance(gate, dict) and gate.get('id') == 'tdd-red' and gate.get('required') is True:
                    if policy['development']['evidence_mode'] == 'final_verification':
                        conflict('legacy_tdd_red', '/development/evidence_mode', path,
                                 f'/gates/{index}/required', ['push', 'merge'], 'Lifecycle explicitly requires an observed RED gate')
        if path.endswith('develop-with-test-first-evidence/config.json') and doc.get('red_execution') == 'local' and doc.get('require_red') is True and v['local_execution'] == 'forbidden':
            conflict('legacy_local_red', '/verification/local_execution', path, '/red_execution',
                     ['push', 'merge'], 'Explicit TDD configuration requires local RED execution')
        for block in entry.get('managed_blocks', []):
            if block['recognized'] and block['name'] == 'verify-before-push' and push_weakened():
                conflict('legacy_before_push', timing_pointer, path, '', ['push'],
                         'Recognized managed block invokes verification before push', block['line'])


    declarations = {
        'mandatory_before_push': ('legacy_before_push', timing_pointer, push_weakened()),
        'local_execution_required': ('legacy_local_execution', '/verification/local_execution', v['local_execution'] == 'forbidden'),
        'local_red_required': ('legacy_local_red', '/verification/local_execution', v['local_execution'] == 'forbidden'),
        'tdd_red_required': ('legacy_tdd_red', '/development/evidence_mode', policy['development']['evidence_mode'] == 'final_verification'),
        'bootstrap_run_pipeline_fallback': ('legacy_bootstrap_fallback', '/publication/pipeline/bootstrap',
             policy['publication']['pipeline']['bootstrap'] == 'suppress' and push_weakened()),
        'website_required_for_task_completion': ('legacy_website_required', '/documentation/web/blocks_primary_task',
             policy['documentation']['web']['blocks_primary_task'] is False)}
    for assertion in assertions:
        if assertion['repository'] != result['repository']:
            continue
        code, pointer, contradictory = declarations[assertion['declaration']]
        if contradictory:
            conflict(code, pointer, assertion['source_path'], assertion['source_pointer'],
                     assertion['operations'], 'Caller-supplied legacy assertion conflicts with policy', assertion.get('line'))


ASSERTION_KINDS = ('mandatory_before_push', 'local_execution_required', 'local_red_required',
                   'tdd_red_required', 'bootstrap_run_pipeline_fallback', 'website_required_for_task_completion')


def _validate_assertions(root, assertions):
    if not isinstance(assertions, (list, tuple)):
        raise ValueError('Assertions must be an array')
    required = {'repository', 'operations', 'declaration', 'source_path', 'source_pointer'}
    for item in assertions:
        if (not isinstance(item, dict) or not required <= item.keys() or item.keys() - required - {'line'}
                or not isinstance(item['repository'], str) or not item['repository'].strip()
                or not isinstance(item['operations'], list) or not item['operations']
                or any(op not in OPERATIONS for op in item['operations'])
                or len(set(item['operations'])) != len(item['operations'])
                or item['declaration'] not in ASSERTION_KINDS
                or not isinstance(item['source_path'], str)
                or not item['source_path'] or Path(item['source_path']).is_absolute()
                or ':' in item['source_path'] or '\\' in item['source_path']
                or '..' in Path(item['source_path']).parts
                or not isinstance(item['source_pointer'], str)
                or (item['source_pointer'] and not item['source_pointer'].startswith('/'))
                or ('line' in item and (type(item['line']) is not int or item['line'] < 1))):
            raise ValueError('Invalid bounded legacy assertion')
        _safe(root, item['source_path'])


def load_project_policy(root, *, repository, operation, profile=None, today=None, legacy_assertions=()):
    """Return absent/configured/invalid diagnostics without execution or mutation.

    repository is an opaque role, never a filesystem discovery instruction.
    today is an injectable datetime.date for deterministic profile expiry.
    Review conditions remain unconfirmed; there is no implicit profile selection.
    """
    root = Path(root).resolve()
    result = {'status': 'absent', 'effective_policy': None, 'active_profile': None,
              'compatibility_mode': 'legacy', 'execution_integration': 'unavailable',
              'constraints_status': 'undeclared', 'provider_confirmation': 'unconfirmed',
              'repository': repository, 'operation': operation, 'origins': {},
              'diagnostics': [], 'legacy_inputs': {}, 'dependent_action_blockers': {},
              'effective_digest': None, 'source_snapshot_digest': None, 'source_hashes': {}}
    snapshots = {}
    def error(code, message, pointer='', path=POLICY):
        result['status'] = 'invalid'
        result['compatibility_mode'] = 'blocked'
        result['diagnostics'].append({'code': code, 'severity': 'error', 'path': path,
            'pointer': pointer, 'message': message, 'affected_operations': list(OPERATIONS)})
    present = []
    if not root.is_dir():
        error('invalid_project_root', 'Project root must be an existing directory')
    try:
        for relative in CANDIDATES:
            candidate = _safe(root, relative)
            if candidate.exists() or candidate.is_symlink():
                present.append(relative)
        if len(present) > 1:
            error('ambiguous_policy', 'Multiple project-policy files; retain only canonical JSON')
        elif present and present[0] != POLICY:
            error('unsupported_format', 'Convert YAML to .agents/kolabse/project-policy.json; YAML is unsupported', path=present[0])
        elif present:
            raw = _safe(root, POLICY).read_bytes()
            snapshots[POLICY] = hashlib.sha256(raw).hexdigest()
            document = _parse(raw)
            version = document.get('schema_version') if isinstance(document, dict) else None
            schema_name = 'project-policy-v2.schema.json' if type(version) is int and version == 2 else 'project-policy.schema.json'
            schema = _parse((Path(__file__).resolve().parent.parent / 'schemas' / schema_name).read_bytes())
            errors = _validate(document, schema)
            if type(version) is int and version == 2:
                errors.extend(_catalog_errors(document))
                if isinstance(document.get('verification'), dict) and 'required_at' in document['verification']:
                    errors.append(_catalog_error('/schema_version', 'Version two requires the per-check catalog contract'))
            if errors:
                result['status'] = 'invalid'; result['compatibility_mode'] = 'blocked'
                result['diagnostics'].extend(errors)
            else:
                effective = {key: copy.deepcopy(value) for key, value in document.items() if key != 'profiles'}
                origins = {pointer: {'pointer': pointer, 'value': value, 'source_path': POLICY,
                                    'source_pointer': pointer, 'profile': None}
                           for pointer, value in _leaves(effective)}
                profiles = document.get('profiles', {})
                if profile is not None:
                    selected = profiles.get(profile)
                    if selected is None:
                        error('unknown_profile', 'Explicitly selected profile does not exist', '/profiles')
                    elif repository not in selected['scope']['repositories'] or operation not in selected['scope']['operations']:
                        error('inapplicable_profile', 'Profile does not cover this repository and operation', '/profiles')
                    elif 'expires_on' in selected and (today or date.today()) > date.fromisoformat(selected['expires_on']):
                        error('expired_profile', 'Selected profile has expired; no fallback is allowed', '/profiles')
                    else:
                        _merge(effective, selected['overrides'])
                        result['active_profile'] = profile
                        for pointer, value in _leaves(selected['overrides']):
                            origins[pointer] = {'pointer': pointer, 'value': value, 'source_path': POLICY,
                                'source_pointer': _pointer('/profiles', profile) + '/overrides' + pointer,
                                'profile': profile, 'base_source_pointer': pointer}
                        if 'review_condition' in selected:
                            result['diagnostics'].append({'code': 'profile_review_unconfirmed', 'severity': 'needs_review',
                                'path': POLICY, 'pointer': _pointer('/profiles', profile) + '/review_condition',
                                'message': selected['review_condition'], 'affected_operations': [operation]})
                if version == 2:
                    effective_errors = _validate(effective, schema) + _catalog_errors(effective)
                    if effective_errors:
                        result['status'] = 'invalid'; result['compatibility_mode'] = 'blocked'
                        result['diagnostics'].extend(effective_errors)
                for left, right, message in _cross_fields(effective):
                    error('contradictory_fields', message, left)
                    result['diagnostics'][-1]['sources'] = [{'path': POLICY, 'pointer': origins[p]['source_pointer']} for p in (left, right)]
                if result['status'] != 'invalid':
                    result.update(status='configured', compatibility_mode='diagnostic_only',
                                  constraints_status='declared', effective_policy=effective, origins=origins,
                                  effective_digest=_digest(effective))
    except (OSError, ValueError, UnicodeError):
        error('unsafe_path' if any(not (root / p).resolve().is_relative_to(root) for p in CANDIDATES) else 'invalid_json',
              'Policy source is unsafe, unreadable or not strict UTF-8 JSON; values withheld')
    if operation not in OPERATIONS or not isinstance(repository, str) or not repository.strip():
        error('invalid_scope', 'Provide a repository role and a supported operation')
    if not present and profile is not None and result['status'] != 'invalid':
        error('unknown_profile', 'A profile cannot be selected without a policy')
    try:
        _validate_assertions(root, legacy_assertions)
        if legacy_assertions:
            snapshots['caller_assertions'] = _digest(legacy_assertions)
    except (ValueError, TypeError):
        error('invalid_assertions', 'Caller assertions must use the bounded documented contract and safe relative source paths')
        legacy_assertions = ()
    _legacy(root, result, snapshots)
    _conflicts(result, legacy_assertions)
    for diagnostic in result['diagnostics']:
        diagnostic['blocking'] = diagnostic['severity'] in ('error', 'conflict')
        if diagnostic['blocking']:
            for action in diagnostic['affected_operations']:
                result['dependent_action_blockers'].setdefault(action, []).append(diagnostic['code'])
    if result['status'] == 'invalid':
        result.update(effective_policy=None, effective_digest=None, origins={}, active_profile=None,
                      constraints_status='undeclared')
    result['source_hashes'] = snapshots
    result['source_snapshot_digest'] = _digest(snapshots)
    return result


def migration_preview(root, result):
    """Conservative deterministic preview; no inference of missing required fields."""
    proposed = copy.deepcopy(result['effective_policy'])
    # Preserve inactive profiles too: copying only the effective values loses scoped intent.
    if result['status'] == 'configured':
        proposed = _parse(_safe(Path(root).resolve(), POLICY).read_bytes())
    edits = []
    preserved = {}
    for path, entry in result['legacy_inputs'].items():
        if 'text' not in entry:
            continue
        preserved[path] = entry['text']
        # Execution rules remain byte-for-byte unchanged until consumers support
        # policy enforcement; even a review-only replacement could weaken a gate.
    return {'proposed_document': proposed, 'managed_block_edits': edits,
            'preserved_content': preserved, 'unmapped_legacy_inputs': sorted(result['legacy_inputs']),
            'unresolved_choices': ([] if proposed is not None else [
                'Explicitly choose all required policy fields; legacy capabilities do not establish execution intent',
                'No provider jobs or successful verification evidence can be inferred']),
            'no_op': proposed is not None and not edits,
            'execution_integration': 'unavailable', 'apply_available': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('status', 'explain', 'validate', 'migrate'))
    parser.add_argument('--project-root', required=True)
    parser.add_argument('--repository', default='project')
    parser.add_argument('--operation', choices=OPERATIONS, default='push')
    parser.add_argument('--profile')
    parser.add_argument('--json', action='store_true', help='Emit JSON (also the default output format)')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    if args.command == 'migrate' and not args.dry_run:
        parser.error('migrate requires --dry-run; applying changes is unavailable')
    result = load_project_policy(args.project_root, repository=args.repository,
                                 operation=args.operation, profile=args.profile)
    if args.command == 'migrate':
        result['migration_preview'] = migration_preview(args.project_root, result)
    print(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False))
    return 2 if result['status'] == 'invalid' else 0


if __name__ == '__main__':
    raise SystemExit(main())
