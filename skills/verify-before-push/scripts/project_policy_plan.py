"""Pure operation planning boundary, with no filesystem, subprocess or provider I/O.

Only absent-policy legacy routing is executable today. A valid declaration is
not an executable policy-bound receipt contract, nor action authorization.
"""

ACTIONS = ('execute_local_check', 'collect_ci', 'trigger_ci', 'accept_evidence',
           'push', 'bootstrap', 'merge', 'web_build', 'web_publish', 'cleanup')
OPERATIONS = ('push', 'merge', 'build', 'deploy', 'cleanup')


def plan_operation(policy, *, repository, operation, action, profile=None):
    """Return a new plan from a loader report and an explicit requested context.

    Context mismatches never acquire legacy permission. Provider capabilities
    and evidence do not yet enable configured execution; consumers must block
    until a versioned policy-bound receipt evaluator is implemented.
    """
    context_valid = (isinstance(repository, str) and bool(repository.strip())
                     and operation in OPERATIONS and action in ACTIONS
                     and policy.get('repository') == repository
                     and policy.get('operation') == operation
                     and policy.get('active_profile') == profile)
    legacy = context_valid and policy.get('status') == 'absent' and profile is None
    reasons = []
    if not context_valid:
        reasons.append('invalid_plan_context')
    if policy.get('status') not in ('absent', 'configured', 'invalid'):
        reasons.append('unknown_policy_status')
    if policy.get('status') == 'invalid':
        reasons.append('invalid_project_policy')
    reasons.extend(policy.get('dependent_action_blockers', {}).get(operation, []))
    if policy.get('status') == 'configured':
        reasons.append('policy_bound_receipt_execution_unavailable')
    if reasons:
        legacy = False
    return {'version': 1, 'decision': 'legacy' if legacy else 'blocked',
            'repository': repository, 'operation': operation, 'action': action,
            'profile': profile, 'effective_digest': policy.get('effective_digest'),
            'source_snapshot_digest': policy.get('source_snapshot_digest'),
            'provider_confirmation': 'unconfirmed', 'blockers': reasons,
            'limitations': [] if legacy else ['Policy-bound execution and receipt acceptance are unavailable'],
            'authorization': 'not_granted'}

# These evaluators are declarations and observations only. They perform no I/O,
# accept no provider truth, and cannot authorize any operation in plan_operation.
import copy
import hashlib
import json
import re

CHANGE_TYPES = ('added', 'modified', 'deleted', 'renamed', 'type_changed')
CHECK_STATUSES = ('passed', 'failed', 'pending', 'running', 'canceled', 'skipped',
                  'manual', 'missing', 'ambiguous', 'unknown', 'not_observed')
_DECISION_FIELDS = {'version', 'repository', 'operation', 'profile', 'source_sha',
                    'policy_digest', 'source_snapshot_digest', 'inventory_digest',
                    'check_decisions', 'mandatory_ids', 'background_ids', 'deferred_ids',
                    'blockers', 'authorization', 'decision_digest'}
_ROW_FIELDS = {'id', 'applicability', 'required', 'background', 'blocks', 'matched_paths', 'reason'}


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode('utf-8')).hexdigest()


def _name(value):
    return (isinstance(value, str) and bool(value.strip())
            and not any(ord(c) < 32 or ord(c) == 127 for c in value))


def _path(value, *, pattern=False):
    if (not _name(value) or value.startswith('/') or '\\' in value or ':' in value
            or any(p in ('', '.', '..') for p in value.split('/'))):
        return False
    return not pattern or (not any(c in value for c in '?[]{}!')
                           and all('**' not in p or p == '**' for p in value.split('/')))


def _segment_matches(value, pattern):
    """Match literal characters and * with polynomial time and bounded memory."""
    if '*' not in pattern:
        return value == pattern
    previous = [True] + [False] * len(value)
    for char in pattern:
        current = [False] * (len(value) + 1)
        if char == '*':
            current[0] = previous[0]
            for i in range(1, len(current)):
                current[i] = previous[i] or current[i - 1]
        else:
            for i in range(1, len(current)):
                current[i] = previous[i - 1] and value[i - 1] == char
        previous = current
    return previous[-1]


def _matches(path, pattern):
    """Full path match with * within segments and ** spanning whole segments.

    Iterative dynamic programming avoids recursion and exponential wildcard
    backtracking, both between path segments and within a single segment.
    """
    path_parts = path.split('/')
    previous = [True] + [False] * len(path_parts)
    for part in pattern.split('/'):
        current = [False] * (len(path_parts) + 1)
        if part == '**':
            current[0] = previous[0]
            for i in range(1, len(current)):
                current[i] = previous[i] or current[i - 1]
        else:
            for i in range(1, len(current)):
                current[i] = previous[i - 1] and _segment_matches(path_parts[i - 1], part)
        previous = current
    return previous[-1]


def _valid_inventory(value, repository):
    keys = {'version', 'repository', 'source_sha', 'target_sha', 'start_sha', 'base_sha',
            'comparison', 'complete', 'changes'}
    if (not isinstance(value, dict) or set(value) != keys or type(value['version']) is not int
            or value['version'] != 1 or value['repository'] != repository
            or value['comparison'] != 'merge-base' or type(value['complete']) is not bool
            or not isinstance(value['changes'], list)):
        return 'invalid_change_inventory'
    shas = [value[k] for k in ('source_sha', 'target_sha', 'start_sha', 'base_sha')]
    if (not all(isinstance(s, str) and re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', s) for s in shas)
            or len({len(s) for s in shas}) != 1):
        return 'invalid_change_inventory'
    seen = set()
    for change in value['changes']:
        if (not isinstance(change, dict) or set(change) != {'kind', 'old_path', 'new_path'}
                or change['kind'] not in CHANGE_TYPES):
            return 'invalid_change_inventory'
        old, new, kind = change['old_path'], change['new_path'], change['kind']
        if any(p is not None and not _path(p) for p in (old, new)):
            return 'invalid_change_inventory'
        if (kind == 'added' and not (old is None and new is not None)
                or kind == 'deleted' and not (new is None and old is not None)
                or kind in ('modified', 'type_changed') and not (old is not None and old == new)
                or kind == 'renamed' and not (old is not None and new is not None and old != new)):
            return 'invalid_change_inventory'
        identity = (kind, old, new)
        if identity in seen:
            return 'invalid_change_inventory'
        seen.add(identity)
    return None if value['complete'] else 'incomplete_change_inventory'


def _valid_catalog(checks):
    if not isinstance(checks, list):
        return False
    seen = set()
    for c in checks:
        if (not isinstance(c, dict) or set(c) != {'id', 'blocks', 'scope'}
                or not _name(c['id']) or c['id'] in seen or not isinstance(c['blocks'], list)
                or any(op not in OPERATIONS for op in c['blocks'])
                or len(set(c['blocks'])) != len(c['blocks'])):
            return False
        seen.add(c['id'])
        scope = c['scope']
        if not isinstance(scope, dict) or set(scope) != {'repositories', 'include_paths', 'exclude_paths', 'change_types'}:
            return False
        for key in scope:
            items = scope[key]
            if (not isinstance(items, list) or (key != 'exclude_paths' and not items)
                    or not all(isinstance(x, str) for x in items) or len(set(items)) != len(items)):
                return False
            if key == 'repositories' and not all(_name(x) for x in items):
                return False
            if key in ('include_paths', 'exclude_paths') and not all(_path(x, pattern=True) for x in items):
                return False
            if key == 'change_types' and any(x not in CHANGE_TYPES for x in items):
                return False
    return True


def evaluate_check_applicability(report, *, repository, operation, profile=None, change_inventory):
    """Evaluate explicit scopes against a complete supplied change inventory.

    A sealed decision binds inputs for later observation matching. This digest
    protects consistency only; it neither authenticates the caller nor proves
    that the inventory was derived from Git or observations from a CI provider.
    """
    value = {'version': 1, 'repository': repository, 'operation': operation, 'profile': profile,
             'source_sha': None, 'policy_digest': None, 'source_snapshot_digest': None,
             'inventory_digest': None, 'check_decisions': [], 'mandatory_ids': [],
             'background_ids': [], 'deferred_ids': [], 'blockers': [], 'authorization': 'not_granted'}
    blockers = value['blockers']
    if not isinstance(report, dict):
        blockers.append('invalid_policy_report')
        report = {}
    effective = report.get('effective_policy')
    checks = effective.get('verification', {}).get('checks') if isinstance(effective, dict) and isinstance(effective.get('verification'), dict) else None
    valid_policy = (report.get('status') == 'configured' and isinstance(effective, dict)
                    and type(effective.get('schema_version')) is int and effective['schema_version'] == 2
                    and _valid_catalog(checks))
    if not valid_policy:
        blockers.append('invalid_v2_project_policy')
    if (not _name(repository) or operation not in OPERATIONS or report.get('repository') != repository
            or report.get('operation') != operation or report.get('active_profile') != profile):
        blockers.append('invalid_applicability_context')
    if isinstance(effective, dict):
        value['policy_digest'] = _digest(effective)
        if value['policy_digest'] != report.get('effective_digest'):
            blockers.append('policy_digest_mismatch')
    value['source_snapshot_digest'] = report.get('source_snapshot_digest')
    if not isinstance(value['source_snapshot_digest'], str) or not re.fullmatch('[0-9a-f]{64}', value['source_snapshot_digest']):
        blockers.append('invalid_source_snapshot_digest')
    blockers.extend(report.get('dependent_action_blockers', {}).get(operation, []))
    inventory_error = _valid_inventory(change_inventory, repository)
    if inventory_error:
        blockers.append(inventory_error)
    try:
        value['inventory_digest'] = _digest(change_inventory)
    except (TypeError, ValueError):
        blockers.append('invalid_change_inventory')
    if isinstance(change_inventory, dict):
        value['source_sha'] = change_inventory.get('source_sha')
    if valid_policy:
        for c in checks:
            scope = c['scope']
            paths = set()
            if not inventory_error:
                for change in change_inventory['changes']:
                    if change['kind'] not in scope['change_types']:
                        continue
                    for path in (change['old_path'], change['new_path']):
                        if (path is not None and any(_matches(path, p) for p in scope['include_paths'])
                                and not any(_matches(path, p) for p in scope['exclude_paths'])):
                            paths.add(path)
            applicable = ('unknown' if inventory_error else 'applicable' if repository in scope['repositories'] and paths else 'not_applicable')
            required = applicable != 'not_applicable' and operation in c['blocks']
            background = applicable == 'applicable' and not c['blocks']
            row = {'id': c['id'], 'applicability': applicable, 'required': required,
                   'background': background, 'blocks': copy.deepcopy(c['blocks']),
                   'matched_paths': sorted(paths) if repository in scope['repositories'] else [],
                   'reason': 'inventory_unknown' if inventory_error else 'scope_matched' if applicable == 'applicable' else 'scope_not_matched'}
            value['check_decisions'].append(row)
            if required:
                value['mandatory_ids'].append(c['id'])
            elif background:
                value['background_ids'].append(c['id'])
            elif applicable == 'applicable' and c['blocks']:
                value['deferred_ids'].append(c['id'])
    value['blockers'] = list(dict.fromkeys(blockers))
    value['decision_digest'] = _digest(value)
    return value


def _valid_decision(value):
    if not isinstance(value, dict) or set(value) != _DECISION_FIELDS:
        return False
    unsigned = {k: v for k, v in value.items() if k != 'decision_digest'}
    if (value['decision_digest'] != _digest(unsigned) or type(value['version']) is not int or value['version'] != 1
            or not _name(value['repository']) or value['operation'] not in OPERATIONS
            or value['authorization'] != 'not_granted' or not isinstance(value['check_decisions'], list)
            or not isinstance(value['blockers'], list) or not all(_name(b) for b in value['blockers'])):
        return False
    if not value['blockers']:
        if (not isinstance(value['source_sha'], str)
                or re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', value['source_sha']) is None
                or any(not isinstance(value[k], str) or re.fullmatch('[0-9a-f]{64}', value[k]) is None
                       for k in ('policy_digest', 'source_snapshot_digest', 'inventory_digest'))):
            return False
    roles = {'mandatory_ids': [], 'background_ids': [], 'deferred_ids': []}
    seen = set()
    for c in value['check_decisions']:
        if (not isinstance(c, dict) or set(c) != _ROW_FIELDS or not _name(c['id']) or c['id'] in seen
                or c['applicability'] not in ('applicable', 'not_applicable', 'unknown')
                or type(c['required']) is not bool or type(c['background']) is not bool
                or not isinstance(c['blocks'], list) or any(op not in OPERATIONS for op in c['blocks'])
                or len(set(c['blocks'])) != len(c['blocks']) or not isinstance(c['matched_paths'], list)
                or not all(_path(p) for p in c['matched_paths']) or not _name(c['reason'])):
            return False
        seen.add(c['id'])
        required = c['applicability'] != 'not_applicable' and value['operation'] in c['blocks']
        background = c['applicability'] == 'applicable' and not c['blocks']
        if c['required'] != required or c['background'] != background:
            return False
        if required:
            roles['mandatory_ids'].append(c['id'])
        elif background:
            roles['background_ids'].append(c['id'])
        elif c['applicability'] == 'applicable' and c['blocks']:
            roles['deferred_ids'].append(c['id'])
        if c['applicability'] == 'unknown' and not value['blockers']:
            return False
    return all(value[key] == ids for key, ids in roles.items())


def evaluate_check_results(applicability, *, observations):
    """Join bounded observations to a sealed decision without granting authority."""
    result = {'decision_digest': applicability.get('decision_digest') if isinstance(applicability, dict) else None,
              'checks': [], 'blocking_state': 'blocked', 'checks_satisfied': False,
              'background_counts': {s: 0 for s in CHECK_STATUSES}, 'blockers': [],
              'authorization': 'not_granted', 'provider_confirmation': 'unconfirmed'}
    try:
        valid = _valid_decision(applicability)
    except (TypeError, ValueError, KeyError):
        valid = False
    if not valid:
        result['blockers'].append('invalid_applicability_decision')
        return result
    result['blockers'].extend(applicability['blockers'])
    if not isinstance(observations, dict):
        result['blockers'].append('invalid_check_observations')
        observations = {}
    ids = {c['id'] for c in applicability['check_decisions']}
    if set(observations) - ids:
        result['blockers'].append('unknown_check_observation')
    for c in applicability['check_decisions']:
        row = copy.deepcopy(c)
        observation = observations.get(c['id'])
        status, jobs = 'not_observed', []
        if observation is not None:
            if (not isinstance(observation, dict) or set(observation) != {'decision_digest', 'source_sha', 'status', 'jobs'}
                    or observation.get('decision_digest') != applicability['decision_digest']
                    or observation.get('source_sha') != applicability['source_sha']
                    or observation.get('status') not in CHECK_STATUSES or not isinstance(observation.get('jobs'), list)
                    or not all(isinstance(j, dict) for j in observation.get('jobs', []))):
                result['blockers'].append('invalid_check_observation:' + c['id'])
                status = 'unknown'
            else:
                status, jobs = observation['status'], copy.deepcopy(observation['jobs'])
                # A check cannot claim success when its constituent jobs disagree
                # or when it has no observed job at all.
                job_statuses = [j.get('status', 'unknown') for j in jobs]
                if 'failed' in job_statuses:
                    status = 'failed'
                elif status == 'passed' and (not jobs or any(s != 'passed' for s in job_statuses)):
                    status = 'missing' if not jobs else 'unknown'
        row.update(status=status, jobs=jobs,
                   classification='mandatory' if c['required'] else 'background' if c['background']
                   else 'deferred' if c['applicability'] == 'applicable' and c['blocks']
                   else 'unknown' if c['applicability'] == 'unknown' else 'not_applicable')
        result['checks'].append(row)
        # Background outcome remains visible even when scope did not require it.
        if not c['blocks']:
            result['background_counts'][status] += 1
        if c['required'] and status != 'passed':
            result['blockers'].append('mandatory_check_not_passed:' + c['id'])
    result['blockers'] = list(dict.fromkeys(result['blockers']))
    if not result['blockers']:
        if applicability['mandatory_ids']:
            result.update(blocking_state='satisfied', checks_satisfied=True)
        else:
            result.update(blocking_state='not_required', checks_satisfied=None)
    return result
