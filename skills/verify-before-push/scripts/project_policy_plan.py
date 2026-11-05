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
