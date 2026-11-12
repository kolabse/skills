"""Read-only acceptance of caller-supplied evidence; never execute or authorize it.

The selected installation is trusted filesystem input. Metadata checks establish
installation consistency and byte snapshots establish what was loaded, not code
authenticity, historical timing or actual check execution.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from types import ModuleType

POLICY_CANDIDATES = ('.agents/kolabse/project-policy.json',
    '.agents/kolabse/project-policy.yaml', '.agents/kolabse/project-policy.yml')
OPERATIONS = ('push', 'merge', 'build', 'deploy', 'cleanup')
COLLECTION = 'kolabse-skills'
SOURCE = 'https://github.com/kolabse/skills'
CAPABILITIES = ('project-policy-v1-v2', 'development-readiness-v1', 'test-first-binding-v1')
ENTRYPOINTS = {'project_policy': 'scripts/project_policy.py',
              'development_readiness': 'scripts/development_readiness.py'}
SCHEMAS = ('project-policy.schema.json', 'project-policy-v2.schema.json',
           'development-mode-decision.schema.json',
           'development-final-verification.schema.json',
           'development-final-verification-result.schema.json',
           'development-test-first-binding.schema.json',
           'development-test-first-result.schema.json')
RUNTIME_FILES = ('collection-metadata.json', 'references/runtime-api.json',
                 *ENTRYPOINTS.values(), *('schemas/' + name for name in SCHEMAS))


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _digest(value, key):
    raw = json.dumps({k: v for k, v in value.items() if k != key},
        sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')
    return 'sha256:' + _sha(raw)


def _pairs(items):
    value = {}
    for key, child in items:
        if key in value:
            raise ValueError('Duplicate JSON key')
        value[key] = child
    return value


def _json(raw):
    try:
        value = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite JSON number')))
        if not isinstance(value, dict):
            raise ValueError('Expected a JSON object')
        # Reject overflow numbers and escaped unpaired Unicode surrogates too.
        json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')
        return value
    except RecursionError as exc:
        raise ValueError('JSON nesting exceeds the supported parser boundary') from exc


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _metadata(value, skill):
    version = value.get('schema_version')
    expected = {'schema_version', 'collection', 'skill', 'source', 'version'}
    if version == 2:
        expected.add('canonical_repository')
    return (type(version) is int and version in (1, 2) and set(value) == expected
        and value['collection'] == COLLECTION and value['skill'] == skill
        and value['source'] == SOURCE
        and (version == 1 or value['canonical_repository'] == SOURCE)
        and isinstance(value['version'], str)
        and re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?', value['version']) is not None)


def _safe_file(root, relative):
    path = root / relative
    if not path.resolve(strict=True).is_relative_to(root) or not path.is_file():
        raise ValueError('Fixed runtime file is missing or escapes selected root')
    return path


def _schema_document(value):
    """Check closed bundled schema structure before executing runtime code."""
    return (value.get('$schema') == 'https://json-schema.org/draft/2020-12/schema'
        and value.get('type') == 'object' and isinstance(value.get('properties'), dict)
        and bool(value['properties']) and isinstance(value.get('required'), list)
        and all(isinstance(key, str) and key in value['properties'] for key in value['required'])
        and value.get('additionalProperties') is False and _schema_node(value))


def _schema_node(value):
    """Validate the closed supported bundled schema vocabulary recursively."""
    allowed = {'$id', '$schema', 'title', 'description', 'type', 'properties',
        'required', 'additionalProperties', 'items', 'minItems', 'uniqueItems',
        'minLength', 'minimum', 'pattern', 'format', 'enum', 'const',
        'allOf', 'anyOf', 'oneOf', 'not', 'propertyNames', 'x-conflict-pointers'}
    if not isinstance(value, dict) or not set(value).issubset(allowed):
        return False
    if 'type' in value and value['type'] not in (
            'object', 'array', 'string', 'integer', 'number', 'boolean', 'null'):
        return False
    for key in ('$id', '$schema', 'title', 'description', 'format'):
        if key in value and not isinstance(value[key], str):
            return False
    for key in ('required', 'x-conflict-pointers'):
        if key in value and (not isinstance(value[key], list)
                or any(not isinstance(item, str) for item in value[key])
                or len(set(value[key])) != len(value[key])):
            return False
    for key in ('minItems', 'minLength', 'minimum'):
        if key in value and (type(value[key]) is not int or value[key] < 0):
            return False
    if 'pattern' in value:
        if not isinstance(value['pattern'], str):
            return False
        try:
            re.compile(value['pattern'])
        except re.error:
            return False
    if 'enum' in value and (not isinstance(value['enum'], list) or not value['enum']):
        return False
    if 'uniqueItems' in value and type(value['uniqueItems']) is not bool:
        return False
    if 'properties' in value and (not isinstance(value['properties'], dict)
            or any(not _schema_node(child) for child in value['properties'].values())):
        return False
    for key in ('items', 'not', 'propertyNames'):
        if key in value and not _schema_node(value[key]):
            return False
    if 'additionalProperties' in value and (type(value['additionalProperties']) is not bool
            and not _schema_node(value['additionalProperties'])):
        return False
    for key in ('allOf', 'anyOf', 'oneOf'):
        if key in value and (not isinstance(value[key], list) or not value[key]
                or any(not _schema_node(child) for child in value[key])):
            return False
    return True


def _matches(value, schema):
    """Small dependency-free walker for the selected closed result schemas.

    Policy semantics stay in the provider. No external references are followed.
    """
    kind = schema.get('type')
    kinds = {'object': isinstance(value, dict), 'array': isinstance(value, list),
        'string': isinstance(value, str), 'integer': type(value) is int,
        'number': type(value) in (int, float), 'boolean': type(value) is bool,
        'null': value is None}
    if kind is not None and (kind not in kinds or not kinds[kind]):
        return False
    if 'const' in schema and (value != schema['const'] or
            isinstance(value, bool) != isinstance(schema['const'], bool)):
        return False
    if 'enum' in schema and value not in schema['enum']:
        return False
    if isinstance(value, dict):
        if any(key not in value for key in schema.get('required', [])):
            return False
        for key, child in value.items():
            child_schema = schema.get('properties', {}).get(key, schema.get('additionalProperties', True))
            if child_schema is False or isinstance(child_schema, dict) and not _matches(child, child_schema):
                return False
    if isinstance(value, list):
        if len(value) < schema.get('minItems', 0):
            return False
        if 'items' in schema and any(not _matches(child, schema['items']) for child in value):
            return False
    if isinstance(value, str):
        if len(value) < schema.get('minLength', 0):
            return False
        if 'pattern' in schema and re.search(schema['pattern'], value) is None:
            return False
    for key, check in (('anyOf', lambda n: n > 0), ('oneOf', lambda n: n == 1),
                       ('allOf', lambda n: n == len(schema['allOf']))):
        if key in schema and not check(sum(_matches(value, child) for child in schema[key])):
            return False
    return True


def _presence(project_root):
    """Only presence/safety detection; never implement policy interpretation."""
    root = Path(project_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Project root must be a directory')
    # Listing each existing bounded directory detects unreadable boundaries.
    tuple(root.iterdir())
    for relative in ('.agents', '.agents/kolabse'):
        boundary = root / relative
        try:
            boundary.lstat()
        except FileNotFoundError:
            continue
        resolved = boundary.resolve(strict=True)
        if not resolved.is_relative_to(root) or not resolved.is_dir():
            raise ValueError('Unsafe policy boundary')
        tuple(boundary.iterdir())
    present = []
    for relative in POLICY_CANDIDATES:
        path = root / relative
        try:
            path.lstat()
        except FileNotFoundError:
            continue
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(root) or not resolved.is_file():
            raise ValueError('Unsafe policy candidate')
        path.read_bytes()
        present.append(relative)
    return root, tuple(present)


def _runtime(selected):
    root = Path(selected).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Runtime root must be a directory')
    snapshots = {relative: _safe_file(root, relative).read_bytes() for relative in RUNTIME_FILES}
    consumer_path = Path(__file__).resolve().parent.parent / 'collection-metadata.json'
    consumer_raw = consumer_path.read_bytes()
    if (not _metadata(_json(consumer_raw), 'develop-with-test-first-evidence') or
            not _metadata(_json(snapshots['collection-metadata.json']), 'verify-before-push')):
        raise ValueError('Inconsistent installation metadata')
    marker = _json(snapshots['references/runtime-api.json'])
    expected = {'schema_version', 'provider', 'collection', 'api_version', 'capabilities', 'entrypoints'}
    if (set(marker) != expected or type(marker['schema_version']) is not int
            or marker['schema_version'] != 1 or type(marker['api_version']) is not int
            or marker['api_version'] != 1 or marker['provider'] != 'verify-before-push'
            or marker['collection'] != COLLECTION or marker['entrypoints'] != ENTRYPOINTS
            or not isinstance(marker['capabilities'], list)
            or any(not isinstance(item, str) for item in marker['capabilities'])
            or not set(CAPABILITIES).issubset(marker['capabilities'])
            or len(set(marker['capabilities'])) != len(marker['capabilities'])):
        raise ValueError('Unsupported runtime API, capabilities or entrypoints')
    schemas = {name: _json(snapshots['schemas/' + name]) for name in SCHEMAS}
    if not all(_schema_document(value) for value in schemas.values()):
        raise ValueError('Invalid required runtime schema')
    provenance = {'root': str(root), 'api_version': 1,
        'file_sha256': {relative: _sha(raw) for relative, raw in snapshots.items()},
        'consumer_metadata_sha256': _sha(consumer_raw), 'consumer_validator_sha256': None}
    return root, snapshots, schemas, provenance, consumer_path, consumer_raw


def _module(root, relative, raw, name):
    # Execute exactly the selected snapshot, avoiding stale bytecode caches.
    module = ModuleType(name)
    module.__file__ = str(root / relative)
    exec(compile(raw, module.__file__, 'exec'), module.__dict__)
    return module


def _consumer(legacy_validator):
    """Snapshot only fixed consumer files; never discover callback source files."""
    root = Path(__file__).resolve().parent.parent
    snapshots = {relative: _safe_file(root, relative).read_bytes() for relative in
        ('collection-metadata.json', 'scripts/evidence.py', 'scripts/policy_evidence.py')}
    if not _metadata(_json(snapshots['collection-metadata.json']), 'develop-with-test-first-evidence'):
        raise ValueError('Invalid consumer installation metadata')
    validator_path = root / 'scripts/evidence.py'
    code = getattr(legacy_validator, '__code__', None)
    fixed = (code is not None and code.co_name == 'validate'
        and Path(code.co_filename).resolve() == validator_path)
    provenance = {'root': str(root),
        'file_sha256': {relative: _sha(raw) for relative, raw in snapshots.items()},
        'validator_kind': 'fixed_consumer_validate' if fixed else 'trusted_library_callable',
        'validator_artifact': {'path': str(validator_path),
            'sha256': _sha(snapshots['scripts/evidence.py'])} if fixed else None}
    return root, snapshots, provenance


def accept_records(input_path, project_root, repository, operation, *, legacy_validator,
                   profile=None, decision_path=None, previous_decision_path=None,
                   subject_path=None, policy_runtime_root=None):
    """Return a sealed acceptance envelope without commands, network or writes.

    Library callers supply a trusted validator callable. The CLI injects only
    its fixed local evidence.validate function; it accepts no callable selector.
    """
    result = {'schema_version': 1, 'format': 'development_evidence_acceptance',
        'status': 'blocked', 'diagnostics': [], 'input_sha256': None,
        'context_sha256': {'decision': None, 'previous_decision': None, 'subject': None},
        'repository': repository, 'operation': operation, 'profile': profile,
        'subject': None, 'provider_result': None, 'runtime_provenance': None,
        'consumer_provenance': None,
        'authorization': 'not_granted', 'provider_confirmation': 'unconfirmed',
        'chronology': 'not_attested', 'observations': 'caller_supplied'}
    runtime = None
    consumer = None

    def error(code, message):
        result['status'] = 'blocked'
        result['subject'] = None
        result['diagnostics'].append({'code': code, 'message': message})

    def finish():
        # Postcheck all selected bytes, including metadata and validator, even
        # for blocked outcomes. Preserve the provider's own sealed report.
        if runtime is not None:
            root, snapshots, _, _, consumer_path, consumer_raw = runtime
            try:
                changed = any(_safe_file(root, relative).read_bytes() != raw
                              for relative, raw in snapshots.items())
                changed = changed or consumer_path.read_bytes() != consumer_raw
            except (OSError, ValueError, RuntimeError):
                changed = True
            if changed:
                error('runtime_changed', 'Selected runtime bytes changed during acceptance')
        if consumer is not None:
            consumer_root, snapshots, _ = consumer
            try:
                changed = any(_safe_file(consumer_root, relative).read_bytes() != raw
                              for relative, raw in snapshots.items())
            except (OSError, ValueError, RuntimeError):
                changed = True
            if changed:
                error('runtime_changed', 'Selected consumer bytes changed during acceptance')
        result['acceptance_digest'] = _digest(result, 'acceptance_digest')
        return result

    try:
        raw = Path(input_path).read_bytes()
        result['input_sha256'] = _sha(raw)
        evidence = _json(raw)
    except (OSError, ValueError, UnicodeError, TypeError):
        error('invalid_input', 'Evidence must be a readable strict JSON object')
        return finish()
    if not _text(repository) or operation not in OPERATIONS or (profile is not None and not _text(profile)):
        error('invalid_scope', 'Supply a repository role, supported operation and valid optional profile')
        return finish()
    try:
        root, present = _presence(project_root)
    except (OSError, ValueError, RuntimeError, TypeError):
        error('invalid_project_root', 'Project root or bounded policy boundary is unavailable or unsafe')
        return finish()
    try:
        consumer = _consumer(legacy_validator)
        result['consumer_provenance'] = consumer[2]
    except (OSError, ValueError, RuntimeError, UnicodeError, TypeError):
        error('invalid_runtime', 'Fixed consumer installation files are unavailable or inconsistent')
        return finish()
    selected = (Path(policy_runtime_root) if policy_runtime_root is not None else
        Path(__file__).resolve().parents[2] / 'verify-before-push')
    try:
        selected.lstat()
        runtime_present = True
    except FileNotFoundError:
        runtime_present = False
    except (OSError, ValueError, TypeError):
        runtime_present = True
    if policy_runtime_root is not None or runtime_present:
        try:
            runtime = _runtime(selected)
            result['runtime_provenance'] = runtime[3]
        except (OSError, ValueError, RuntimeError, UnicodeError, TypeError):
            error('invalid_runtime', 'Selected runtime installation is unavailable, unsafe or incompatible')
            return finish()
    elif present:
        error('missing_policy_runtime', 'Policy presence requires the fixed sibling or an explicit compatible runtime')
        return finish()

    report = None
    readiness = None
    if runtime is not None:
        try:
            runtime_root, snapshots, schemas, _, _, _ = runtime
            policy = _module(runtime_root, ENTRYPOINTS['project_policy'],
                snapshots[ENTRYPOINTS['project_policy']], '_acceptance_project_policy')
            readiness = _module(runtime_root, ENTRYPOINTS['development_readiness'],
                snapshots[ENTRYPOINTS['development_readiness']], '_acceptance_development_readiness')
            if (tuple(policy.CANDIDATES) != POLICY_CANDIDATES
                    or not callable(policy.load_project_policy)
                    or not callable(readiness.validate_final_verification)
                    or not callable(readiness.validate_test_first_binding)):
                raise ValueError('Runtime callable contract is unavailable')
            report = policy.load_project_policy(root, repository=repository, operation=operation, profile=profile)
            if not isinstance(report, dict) or report.get('status') not in ('absent', 'configured', 'invalid'):
                raise ValueError('Invalid policy loader result')
        except Exception:
            error('invalid_runtime', 'Selected runtime failed to provide a valid policy report')
            return finish()

    # Our conservative detector must agree with the provider before legacy use.
    absent = not present and (report is None or report['status'] == 'absent')
    if not present and any(item is not None for item in
            (profile, decision_path, previous_decision_path, subject_path)):
        error('absent_policy_context', 'Explicit policy context cannot be accepted without a policy')
        return finish()
    if absent:
        if not callable(legacy_validator):
            error('invalid_legacy_validator_result', 'A trusted canonical v1 validator callable is required')
            return finish()
        try:
            errors = legacy_validator(copy.deepcopy(evidence))
        except Exception:
            error('legacy_validator_failed', 'Canonical v1 evidence validation raised an exception')
            return finish()
        if not isinstance(errors, list) or any(not isinstance(item, str) for item in errors):
            error('invalid_legacy_validator_result', 'Canonical v1 evidence validation returned a malformed result')
        elif errors:
            error('invalid_legacy_evidence', 'Canonical v1 evidence validation rejected the record')
        else:
            result.update(status='legacy', subject=copy.deepcopy(evidence.get('subject')))
        return finish()
    if report is None or report['status'] != 'configured':
        error('invalid_project_policy', 'A current configured policy is required; no fallback is allowed')
        return finish()
    if decision_path is None or subject_path is None:
        error('missing_policy_context', 'Configured acceptance requires explicit decision and subject records')
        return finish()
    try:
        context = {}
        for name, path in (('decision', decision_path), ('previous_decision', previous_decision_path),
                           ('subject', subject_path)):
            context[name] = None
            if path is not None:
                raw = Path(path).read_bytes()
                result['context_sha256'][name] = _sha(raw)
                context[name] = _json(raw)
    except (OSError, ValueError, UnicodeError, TypeError):
        error('invalid_policy_context', 'Explicit context records must be readable strict JSON objects')
        return finish()
    try:
        mode = report['effective_policy']['development']['evidence_mode']
        if mode == 'test_first':
            result['runtime_provenance']['consumer_validator_sha256'] = _sha(consumer[1]['scripts/evidence.py'])
            provider = readiness.validate_test_first_binding(report, context['decision'], evidence,
                context['subject'], legacy_validator, previous_decision=context['previous_decision'])
            satisfied = 'test_first_satisfied'
            result_schema = schemas['development-test-first-result.schema.json']
        elif mode == 'final_verification':
            provider = readiness.validate_final_verification(report, context['decision'], evidence,
                context['subject'], previous_decision=context['previous_decision'])
            satisfied = 'final_verification_satisfied'
            result_schema = schemas['development-final-verification-result.schema.json']
        else:
            raise ValueError('Unsupported configured development mode')
        if (not isinstance(provider, dict) or not _matches(provider, result_schema)
                or provider['report_digest'] != _digest(provider, 'report_digest')
                or provider[satisfied] != (provider['status'] == 'verified')
                or bool(provider['diagnostics']) == provider[satisfied]):
            raise ValueError('Malformed or unsealed provider result')
        result['provider_result'] = copy.deepcopy(provider)
        if provider[satisfied]:
            result['subject'] = copy.deepcopy(provider['bindings']['subject'])
            result['status'] = 'accepted'
        else:
            error('provider_rejected', 'Shared policy-bound validation rejected the supplied evidence')
    except Exception:
        error('invalid_provider_result', 'Shared validation raised or returned a malformed result')
    return finish()
