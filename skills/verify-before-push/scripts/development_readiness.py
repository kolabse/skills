#!/usr/bin/env python3
"""Read-only consistency diagnostics; never grant provider or action authorization.

Records are caller-supplied assertions. Digests bind content, not chronology,
actual command execution, reviewer independence, or Git provenance. Source
readiness precedes final verification; neither changes existing lifecycle gates.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

SHA = re.compile(r'^sha256:[0-9a-f]{64}$')
HEX = re.compile(r'^[0-9a-f]{64}$')
COMMIT = re.compile(r'^[0-9a-f]{40}(?:[0-9a-f]{24})?$')
OPERATIONS = ('push', 'merge', 'build', 'deploy', 'cleanup')
MODES = ('test_first', 'final_verification')
CONTEXT = {'repository', 'operation', 'profile', 'policy_digest', 'source_snapshot_digest'}
DECISION = CONTEXT | {'schema_version', 'format', 'mode', 'selection_subject', 'phase',
                      'rationale', 'predecessor_digest', 'change_reason', 'decision_digest'}
EVIDENCE = CONTEXT | {'schema_version', 'format', 'decision_digest', 'subject', 'checks', 'evidence_digest'}
REVIEW = CONTEXT | {'schema_version', 'format', 'decision_digest', 'subject', 'outcome',
                    'reviewer', 'summary', 'review_digest'}
LOCAL = {'source', 'command', 'exit_code', 'summary'}
CI = {'source', 'provider', 'source_sha', 'pipeline_id', 'job_id', 'url', 'status', 'summary'}


def digest(record, digest_key):
    """Canonical SHA-256 excluding the named digest field; no provenance claim."""
    payload = {key: value for key, value in record.items() if key != digest_key}
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'),
                     ensure_ascii=False, allow_nan=False).encode('utf-8')
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _match(pattern, value):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _fields(value, expected):
    return isinstance(value, dict) and set(value) == expected


def _subject(value):
    if not _fields(value, {'kind', 'identity'}):
        return False
    return ((value['kind'] == 'commit' and _match(COMMIT, value['identity'])) or
            (value['kind'] == 'worktree' and _match(SHA, value['identity'])))


def _diagnostic(errors, code, message):
    errors.append({'code': code, 'message': message})


def _base(status, errors):
    return {'schema_version': 1, 'status': status, 'diagnostics': errors,
            'readiness_kind': 'diagnostic_consistency_only',
            'provider_confirmation': 'unconfirmed', 'authorization': 'not_granted',
            'observations': 'caller_supplied', 'chronology': 'not_attested',
            'subject_provenance': 'caller_supplied_not_reconstructed'}


def _record(value, expected, name, digest_key, errors):
    valid = _fields(value, expected)
    if valid:
        valid = (type(value['schema_version']) is int and value['schema_version'] == 1
                 and value['format'] == name
                 and _text(value['repository']) and value['operation'] in OPERATIONS
                 and (value['profile'] is None or _text(value['profile']))
                 and _match(HEX, value['policy_digest'])
                 and _match(HEX, value['source_snapshot_digest'])
                 and _match(SHA, value[digest_key]))
    if valid:
        try:
            valid = digest(value, digest_key) == value[digest_key]
        except (TypeError, ValueError, UnicodeError):
            valid = False
    if not valid:
        _diagnostic(errors, 'invalid_' + {'decision_digest': 'decision', 'evidence_digest': 'evidence',
                    'review_digest': 'review'}[digest_key], 'Record structure, version or canonical binding is invalid')
    return valid


def _policy(report, errors):
    """Consume v1/v2 loader report fields, never reinterpret its declarations."""
    valid = isinstance(report, dict) and report.get('status') == 'configured'
    if valid:
        effective = report.get('effective_policy')
        hashes = report.get('source_hashes')
        valid = (isinstance(effective, dict) and type(effective.get('schema_version')) is int
                 and effective['schema_version'] in (1, 2)
                 and isinstance(effective.get('development'), dict)
                 and effective['development'].get('evidence_mode') in MODES
                 and _text(report.get('repository')) and report.get('operation') in OPERATIONS
                 and (report.get('active_profile') is None or _text(report['active_profile']))
                 and _match(HEX, report.get('effective_digest'))
                 and _match(HEX, report.get('source_snapshot_digest'))
                 and isinstance(hashes, dict) and bool(hashes)
                 and all(_text(key) and _match(HEX, value) for key, value in hashes.items())
                 and isinstance(report.get('diagnostics'), list)
                 and isinstance(report.get('dependent_action_blockers'), dict))
        if valid:
            try:
                valid = (digest(effective, '__not_a_policy_field__')[7:] == report['effective_digest']
                         and digest(hashes, '__not_a_snapshot_field__')[7:] == report['source_snapshot_digest'])
            except (TypeError, ValueError, UnicodeError):
                valid = False
    if not valid:
        _diagnostic(errors, 'invalid_policy_report', 'A current configured, internally bound policy report is required')
        return False
    if report['dependent_action_blockers'].get(report['operation']):
        _diagnostic(errors, 'policy_blocked', 'The policy loader reports blockers for this operation')
    for item in report['diagnostics']:
        if not isinstance(item, dict) or not _text(item.get('code')) or not _text(item.get('severity')):
            _diagnostic(errors, 'invalid_policy_report', 'Policy diagnostics are malformed')
            continue
        operations = item.get('affected_operations')
        if not isinstance(operations, list) or any(op not in OPERATIONS for op in operations):
            _diagnostic(errors, 'invalid_policy_report', 'Policy diagnostic operation scope is malformed')
        elif report['operation'] in operations and (item.get('blocking') is True or
                item['severity'] in ('error', 'conflict') or item['code'] == 'profile_review_unconfirmed'):
            _diagnostic(errors, 'policy_blocked', 'Unresolved policy diagnostics require reconciliation or review')
    return True


def _scope(report, record, errors):
    wanted = {'repository': report['repository'], 'operation': report['operation'],
              'profile': report.get('active_profile'), 'policy_digest': report['effective_digest'],
              'source_snapshot_digest': report['source_snapshot_digest']}
    if any(record[key] != value for key, value in wanted.items()):
        _diagnostic(errors, 'stale_context', 'Record does not match the selected repository, operation, profile or policy snapshot')


def _decision(value, errors):
    if not _record(value, DECISION, 'development_mode_decision', 'decision_digest', errors):
        return False
    if (value['mode'] not in MODES or not _subject(value['selection_subject'])
            or value['phase'] not in ('pre_implementation', 'late_selection')
            or not _text(value['rationale'])
            or not (value['predecessor_digest'] is None or _match(SHA, value['predecessor_digest']))
            or not (value['change_reason'] is None or _text(value['change_reason']))):
        _diagnostic(errors, 'invalid_decision', 'Decision values, selection subject or change explanation are invalid')
        return False
    return True


def select_mode(policy_report, decision, implementation_started, previous_decision=None):
    """Check an explicit content-bound choice; never attest its historical timing."""
    errors = []
    policy_valid = _policy(policy_report, errors)
    choice_valid = _decision(decision, errors)
    if type(implementation_started) is not bool:
        _diagnostic(errors, 'invalid_implementation_state', 'implementation_started must be an explicit boolean')
    if policy_valid and choice_valid:
        _scope(policy_report, decision, errors)
        if decision['mode'] != policy_report['effective_policy']['development']['evidence_mode']:
            _diagnostic(errors, 'mode_conflict', 'Explicit choice conflicts with the effective policy mode')
        if type(implementation_started) is bool:
            phase = 'late_selection' if implementation_started else 'pre_implementation'
            if decision['phase'] != phase:
                _diagnostic(errors, 'selection_phase_mismatch', 'Declared selection phase disagrees with caller-supplied implementation state')
            if implementation_started and decision['mode'] == 'test_first':
                _diagnostic(errors, 'late_test_first_selection', 'Late selection cannot establish a preimplementation test-first choice')
        if previous_decision is None:
            if decision['predecessor_digest'] is not None or decision['change_reason'] is not None:
                _diagnostic(errors, 'missing_predecessor', 'Supply the actual predecessor record for a changed decision')
        elif _decision(previous_decision, errors):
            if previous_decision['decision_digest'] == decision['decision_digest']:
                _diagnostic(errors, 'predecessor_mismatch', 'A decision cannot be supplied as its own predecessor')
            if (previous_decision['repository'] != decision['repository'] or
                    previous_decision['operation'] != decision['operation']):
                _diagnostic(errors, 'predecessor_scope_mismatch', 'Predecessor belongs to another repository or operation')
            if previous_decision['decision_digest'] != decision['decision_digest']:
                if decision['predecessor_digest'] != previous_decision['decision_digest']:
                    _diagnostic(errors, 'predecessor_mismatch', 'Changed choice must link the supplied predecessor digest')
                if not _text(decision['change_reason']):
                    _diagnostic(errors, 'decision_change_unexplained', 'Changed choice requires an explicit reason')
    result = _base('blocked' if errors else 'selected', errors)
    result['mode'] = decision['mode'] if choice_valid else None
    return result


def _selected(report, decision, previous):
    # Reusing a selection record checks its declared phase, not the current phase
    # of implementation. It cannot reconstruct when selection actually occurred.
    started = isinstance(decision, dict) and decision.get('phase') == 'late_selection'
    return select_mode(report, decision, started, previous)


def _receipt(result, report, decision, subject, extra, digest_key):
    """Bind successful diagnostics to inputs; invalid inputs are never echoed."""
    result['bindings'] = None
    if not result['diagnostics']:
        result['bindings'] = {
            'repository': report['repository'], 'operation': report['operation'],
            'profile': report.get('active_profile'), 'policy_digest': report['effective_digest'],
            'source_snapshot_digest': report['source_snapshot_digest'],
            'subject': copy.deepcopy(subject), 'decision_digest': decision['decision_digest'], **extra}
    result[digest_key] = digest(result, digest_key)
    return result


def evaluate_source_readiness(policy_report, decision, review, subject,
                              implementation_complete, previous_decision=None):
    """Check completion plus exact-subject review, independently of final CI."""
    result = _selected(policy_report, decision, previous_decision)
    errors = result['diagnostics']
    if implementation_complete is not True:
        _diagnostic(errors, 'implementation_incomplete', 'Explicit implementation_complete=true is required')
    if not _subject(subject):
        _diagnostic(errors, 'invalid_subject', 'Supply an exact commit or worktree subject')
    valid = _record(review, REVIEW, 'development_source_review', 'review_digest', errors)
    if valid:
        if (not _subject(review['subject']) or review['outcome'] != 'approved'
                or not _text(review['reviewer']) or not _text(review['summary'])
                or not _match(SHA, review['decision_digest'])):
            _diagnostic(errors, 'invalid_review', 'Explicit approved source review and reviewer assertion are required')
        if review['subject'] != subject:
            _diagnostic(errors, 'review_subject_mismatch', 'Review must bind the supplied exact final subject')
        if isinstance(decision, dict) and review['decision_digest'] != decision.get('decision_digest'):
            _diagnostic(errors, 'review_decision_mismatch', 'Review must bind the selected decision')
        if _policy_usable(policy_report):
            _scope(policy_report, review, errors)
    result.update(status='blocked' if errors else 'source_ready', source_ready=not errors)
    return _receipt(result, policy_report, decision, subject,
                    {'review_digest': review.get('review_digest') if isinstance(review, dict) else None,
                     'implementation_complete': implementation_complete}, 'readiness_digest')


def _policy_usable(report):
    return isinstance(report, dict) and all(key in report for key in
        ('repository', 'operation', 'effective_digest', 'source_snapshot_digest'))


def _https(value):
    if not isinstance(value, str) or any(character.isspace() for character in value):
        return False
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        if (parsed.scheme != 'https' or not host or parsed.username is not None
                or parsed.password is not None or parsed.fragment
                or any(ord(character) < 32 or ord(character) == 127 for character in value)):
            return False
        parsed.port  # Validate malformed or out-of-range ports without making requests.
        return True  # Private and single-label self-hosted CI hosts are valid observations.
    except ValueError:
        return False


def _check(value, verification, subject, errors):
    if not isinstance(value, dict):
        _diagnostic(errors, 'invalid_check', 'Each focused/broader check must be an observation object')
        return
    source = value.get('source')
    if source != verification.get('execution'):
        _diagnostic(errors, 'check_execution_mismatch', 'Check execution source must match the selected policy execution')
    if source == 'local':
        valid = (_fields(value, LOCAL) and verification.get('provider') == 'none'
                 and verification.get('local_execution') == 'allowed'
                 and isinstance(value.get('command'), list) and bool(value['command'])
                 and all(_text(part) for part in value['command'])
                 and type(value.get('exit_code')) is int and value['exit_code'] == 0
                 and _text(value.get('summary')))
    elif source == 'ci':
        valid = (_fields(value, CI) and value.get('provider') in ('github', 'gitlab')
                 and value['provider'] == verification.get('provider')
                 and isinstance(subject, dict) and subject.get('kind') == 'commit'
                 and _match(COMMIT, value.get('source_sha')) and value['source_sha'] == subject.get('identity')
                 and type(value.get('pipeline_id')) is int and value['pipeline_id'] > 0
                 and type(value.get('job_id')) is int and value['job_id'] > 0
                 and _https(value.get('url')) and value.get('status') == 'passed'
                 and _text(value.get('summary')))
    else:
        valid = False
    if not valid:
        _diagnostic(errors, 'invalid_check', 'Check must be a successful, policy-compatible local or CI observation')


def validate_final_verification(policy_report, decision, evidence, subject, previous_decision=None):
    """Validate the final-only observation format; does not satisfy legacy gates."""
    result = _selected(policy_report, decision, previous_decision)
    errors = result['diagnostics']
    if result['mode'] == 'test_first':
        _diagnostic(errors, 'test_first_evidence_unavailable', 'Legacy v1 test-first ingestion is deferred; use its canonical validator and retain existing gates')
    if not _subject(subject):
        _diagnostic(errors, 'invalid_subject', 'Supply an exact commit or worktree subject')
    if _record(evidence, EVIDENCE, 'development_final_verification', 'evidence_digest', errors):
        if _policy_usable(policy_report):
            _scope(policy_report, evidence, errors)
        if not _subject(evidence['subject']) or evidence['subject'] != subject:
            _diagnostic(errors, 'evidence_subject_mismatch', 'Evidence must bind the exact final subject')
        if (not isinstance(decision, dict) or not _match(SHA, evidence['decision_digest'])
                or evidence['decision_digest'] != decision.get('decision_digest')):
            _diagnostic(errors, 'evidence_decision_mismatch', 'Evidence must bind the selected decision')
        effective = policy_report.get('effective_policy') if isinstance(policy_report, dict) else None
        verification = effective.get('verification') if isinstance(effective, dict) else None
        if not isinstance(verification, dict) or verification.get('subject') != 'source_sha':
            _diagnostic(errors, 'unsupported_verification_subject', 'Only source_sha observations are supported; merge-result evidence is deferred')
        elif not _fields(evidence['checks'], {'focused', 'broader'}):
            _diagnostic(errors, 'invalid_check', 'Both focused and broader final check observations are required')
        else:
            for value in evidence['checks'].values():
                _check(value, verification, subject, errors)
    result.update(status='blocked' if errors else 'verified', final_verification_satisfied=not errors,
                  check_scope='focused_and_broader_contract_only')
    return _receipt(result, policy_report, decision, subject,
                    {'evidence_digest': evidence.get('evidence_digest') if isinstance(evidence, dict) else None},
                    'report_digest')


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'), object_pairs_hook=_pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite number')))


def _load_policy(root, **scope):
    # Fixed sibling only. No arbitrary search, cross-skill import or execution.
    path = Path(__file__).resolve().with_name('project_policy.py')
    spec = importlib.util.spec_from_file_location('_readiness_project_policy', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.load_project_policy(root, **scope)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('select-mode', 'source-readiness', 'final-verification'))
    parser.add_argument('--project-root', required=True)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--operation', choices=OPERATIONS, required=True)
    parser.add_argument('--profile')
    for name in ('decision', 'previous-decision', 'subject', 'review', 'evidence'):
        parser.add_argument('--' + name, required=name == 'decision')
    parser.add_argument('--implementation-started', choices=('true', 'false'))
    parser.add_argument('--implementation-complete', choices=('true', 'false'))
    args = parser.parse_args(argv)
    required = {'select-mode': ('implementation_started',),
                'source-readiness': ('subject', 'review', 'implementation_complete'),
                'final-verification': ('subject', 'evidence')}[args.command]
    if any(getattr(args, key) is None for key in required):
        parser.error('Missing command-specific record or explicit implementation state')
    try:
        report = _load_policy(args.project_root, repository=args.repository,
                              operation=args.operation, profile=args.profile)
        decision = _read(args.decision)
        previous = _read(args.previous_decision) if args.previous_decision else None
        if args.command == 'select-mode':
            result = select_mode(report, decision, args.implementation_started == 'true', previous)
        elif args.command == 'source-readiness':
            result = evaluate_source_readiness(report, decision, _read(args.review), _read(args.subject),
                                                args.implementation_complete == 'true', previous)
        else:
            result = validate_final_verification(report, decision, _read(args.evidence), _read(args.subject), previous)
    except (OSError, ValueError, UnicodeError, ImportError):
        result = _base('blocked', [{'code': 'unreadable_input',
                                  'message': 'Selected JSON input or fixed sibling policy loader is unavailable or invalid'}])
        result['mode'] = None
        if args.command == 'source-readiness':
            result.update(source_ready=False, bindings=None)
            result['readiness_digest'] = digest(result, 'readiness_digest')
        elif args.command == 'final-verification':
            result.update(final_verification_satisfied=False, bindings=None,
                          check_scope='focused_and_broader_contract_only')
            result['report_digest'] = digest(result, 'report_digest')
    print(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False))
    return 2 if result['status'] == 'blocked' else 0


if __name__ == '__main__':
    raise SystemExit(main())
