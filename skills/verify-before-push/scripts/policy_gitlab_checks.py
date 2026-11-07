#!/usr/bin/env python3
"""Policy-v2 applicability-bound CI observations, never action authorization."""
from pathlib import Path
from types import SimpleNamespace
import importlib.util
import re


def sibling(name):
    spec = importlib.util.spec_from_file_location('_checks_' + name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


p = sibling('policy_gitlab_ci')
g = p.g
plan = sibling('project_policy_plan')
require = p.require
EvidenceError = p.EvidenceError
DEFAULT_EVIDENCE = '.agents/verify-before-push/gitlab-check-evidence.json'
LIMITATIONS = ['source_review_unconfirmed', 'ready_at_start_unconfirmed',
               'applicable_required_checks_only', 'no_push_or_merge_authorization',
               'no_pipeline_mutation_or_local_execution']
RECEIPT_KEYS = p.RECEIPT_KEYS | {'evaluation'}


def safe_path(path):
    return (isinstance(path, str) and bool(path) and not path.startswith('/') and
            not any(ord(c) < 32 or ord(c) == 127 for c in path) and
            ':' not in path and '\\' not in path and
            all(part not in ('', '.', '..') for part in path.split('/')))


def parse_changes(raw):
    """Parse the complete Git name-status -z stream without line/path quoting."""
    require(type(raw) is bytes and (not raw or raw.endswith(b'\0')), 'incomplete Git diff stream')
    try:
        tokens = raw.decode('utf-8', errors='strict').split('\0')[:-1]
    except UnicodeDecodeError:
        raise EvidenceError('Git diff paths must be UTF-8') from None
    rows, index, seen = [], 0, set()
    kinds = {'A': 'added', 'M': 'modified', 'D': 'deleted', 'T': 'type_changed'}
    while index < len(tokens):
        status = tokens[index]
        index += 1
        rename = re.fullmatch(r'R(?:100|0?[0-9]{1,2})', status) is not None
        require(status in kinds or rename, 'unsupported or unproven Git change status')
        count = 2 if rename else 1
        require(index + count <= len(tokens), 'incomplete Git change paths')
        paths = tokens[index:index + count]
        index += count
        require(all(safe_path(path) for path in paths), 'unsafe or unproven Git change path')
        old = None if status == 'A' else paths[0]
        new = None if status == 'D' else paths[-1]
        row = dict(kind='renamed' if rename else kinds[status], old_path=old, new_path=new)
        key = (row['kind'], old, new)
        require(key not in seen, 'duplicate Git change')
        seen.add(key)
        rows.append(row)
    return rows


def inventory(v, root, repository, ident, metadata, source_sha, target_branch):
    def object_git(*args, **kwargs):
        # Applicability belongs to the advertised SHAs, not a local virtual history.
        return v.git(root, '--no-replace-objects', *args, **kwargs)

    require(object_git('rev-parse', '--is-shallow-repository').strip() == b'false',
            'complete Git history is required')
    target = metadata['target_head']
    refs = metadata['mr']['diff_refs']
    ref = 'refs/heads/' + target_branch
    require(v.run_process(['git', 'check-ref-format', ref], root).returncode == 0,
            'invalid configured target ref')
    tracking = 'refs/remotes/' + ident['remote'] + '/' + target_branch
    current = object_git('rev-parse', '--verify', tracking, check=False).decode().strip()
    if current != target:
        # Fetch only the declared target ref; never trust a provider path list.
        v.git(root, 'fetch', '--no-tags', ident['remote'], ref + ':' + tracking)
        current = object_git('rev-parse', '--verify', tracking).decode().strip()
    require(current == target, 'Git target ref differs from current provider target')
    for sha in (source_sha, target, refs['base_sha'], refs['start_sha']):
        require(g.sha(sha) and object_git('cat-file', '-t', sha, check=False).strip() == b'commit',
                'missing or invalid source/target/base/start commit')
    bases = object_git('merge-base', '--all', source_sha, target).decode().strip().splitlines()
    require(bases == [refs['base_sha']], 'MR base does not equal the unique current Git merge base')
    changes = parse_changes(object_git('diff', '--name-status', '-z', '--no-ext-diff', '--no-textconv',
                                  '--ignore-submodules=none', '--find-renames', refs['base_sha'], source_sha, '--'))
    return dict(version=1, repository=repository, source_sha=source_sha, target_sha=target,
                start_sha=refs['start_sha'], base_sha=refs['base_sha'], comparison='merge-base',
                complete=True, changes=changes)


def context(v, root, repository, operation, profile, transport, expected_digest, helpers=p):
    require(operation in helpers.policy_loader.OPERATIONS, 'unsupported CI-check operation')
    for relative in ('.agents', '.agents/verify-before-push', '.agents/kolabse', str(v.CONFIG_RELATIVE), helpers.policy_loader.POLICY):
        v.reject_workspace_links(root, root / relative)
    raw = (root / v.CONFIG_RELATIVE).read_bytes()
    parsed = g.loads_strict(raw.decode('utf-8-sig'))
    require(g.hashlib.sha256(raw).hexdigest() == expected_digest, 'configuration changed after provider host selection')
    config, _ = v.load_config(root)
    require(g.digest(config) == g.digest(parsed), 'configuration changed during loading')
    block = helpers.validate_gitlab_ci_policy(config)
    require(block is not None and block.get('version') == 2, 'explicit version 2 GitLab configuration required')
    require(getattr(transport, 'host', block['host']) == block['host'], 'transport host differs from selected configuration')
    entries = config['repositories']
    require(len(entries) == 1 and entries[0]['name'] == repository and
            (root / entries[0]['path']).resolve() == root and
            entries[0].get('require_clean', True) is True and entries[0].get('require_upstream_current', True) is True,
            'only one clean/current repository at project root is supported')
    for check in config['checks']:
        v.validate_check(check, root, [root])
    report = helpers.policy_loader.load_project_policy(root, repository=repository, operation=operation, profile=profile)
    require(report['status'] == 'configured' and not report['dependent_action_blockers'].get(operation),
            'policy is absent, invalid, expired or blocked for operation')
    policy = report['effective_policy']
    require(policy['schema_version'] == 2, 'version 2 GitLab configuration requires version 2 policy')
    verification = policy['verification']
    require(verification['execution'] == 'ci' and verification['provider'] == 'gitlab' and
            verification['subject'] == 'source_sha' and verification['reuse_successful_result'] is True,
            'unsupported policy provider/execution/subject/reuse')
    catalog = verification['checks']
    enabled = {c['name']: c for c in config['checks'] if c.get('enabled', True)}
    require(set(enabled) == {c['id'] for c in catalog} == set(block['checks']), 'policy/configuration check catalogs differ')
    for check in catalog:
        require(enabled[check['id']].get('required', True) == bool(check['blocks']),
                'configuration required flag differs from explicit policy blocking role')
    publication = policy['publication']['pipeline']
    require(publication['event'] == 'merge_request', 'policy must declare merge_request pipeline events')
    ident = helpers.identity(v, root, block, transport)
    v.refresh_required_upstreams(config, root)
    states = v.capture_states(config, root)
    state = states[0]
    require(state['clean'] and state['head'] == state['upstream_sha'] and state['ahead'] == state['behind'] == 0,
            'source HEAD must equal fresh remote upstream')
    metadata = g.read_mr_context(transport, host=block['host'], project_id=block['project_id'], mr_iid=block['mr_iid'],
                                 source_sha=state['head'], target_branch=publication['target_branch'], require_non_draft=publication['require_ready'])
    require(metadata['mr']['source_branch'] == ident['source_branch'], 'MR source branch differs from tracked source ref')
    changes = inventory(v, root, repository, ident, metadata, state['head'], publication['target_branch'])
    applicability = plan.evaluate_check_applicability(report, repository=repository, operation=operation,
                                                      profile=profile, change_inventory=changes)
    require(not applicability['blockers'], 'applicability is invalid, incomplete or blocked')
    applicable = {c['id'] for c in applicability['check_decisions'] if c['applicability'] == 'applicable'}
    contract = dict(version=2, host=block['host'], project_id=block['project_id'], mr_iid=block['mr_iid'],
                    source_sha=state['head'], target_branch=publication['target_branch'], subject_kind='source_sha',
                    required_jobs=sorted(job for name in applicability['mandatory_ids'] for job in block['checks'][name]),
                    observed_jobs=sorted(job for name in applicable for job in block['checks'][name]),
                    target_head=metadata['target_head'], diff_base_sha=changes['base_sha'], diff_start_sha=changes['start_sha'],
                    applicability_digest=applicability['decision_digest'], require_non_draft=publication['require_ready'],
                    require_pipeline_success=False, require_ready_at_start=False, require_source_review=False,
                    repository=repository, profile=profile, operation=operation, effective_policy_digest=report['effective_digest'],
                    source_snapshot_digest=report['source_snapshot_digest'], check_map_digest=g.digest(block['checks']))
    g.validate_contract(contract)
    return dict(project_root=str(root), repository=repository, operation=operation, profile=profile,
                config=config, config_raw_sha256=expected_digest, repositories=states, identity=ident, contract=contract,
                effective_policy=policy, source_hashes=report['source_hashes'], effective_policy_digest=report['effective_digest'],
                source_snapshot_digest=report['source_snapshot_digest'], check_map=block['checks'],
                check_map_digest=g.digest(block['checks']), check_catalog=catalog, change_inventory=changes, applicability=applicability)


def evaluation(binding, observation):
    statuses = {'success': 'passed', 'failed': 'failed', 'pending': 'pending', 'created': 'pending',
                'preparing': 'pending', 'waiting_for_resource': 'pending', 'scheduled': 'pending',
                'running': 'running', 'canceled': 'canceled', 'skipped': 'skipped', 'manual': 'manual'}
    observations = {}
    decision = binding['applicability']
    for name, names in binding['check_map'].items():
        jobs, missing, ambiguous = [], False, False
        for job_name in names:
            matches = [job for job in observation['jobs'] if job['name'] == job_name]
            missing |= not matches
            ambiguous |= len(matches) > 1
            jobs.extend(dict(job, status=statuses.get(job['status'], 'unknown')) for job in matches)
        values = {job['status'] for job in jobs}
        if observation['pipeline'] is None:
            status = 'not_observed'
        elif ambiguous:
            status = 'ambiguous'
        elif missing:
            status = 'missing'
        else:
            status = next((s for s in ('failed', 'unknown', 'canceled', 'running', 'pending', 'manual', 'skipped') if s in values), 'passed')
        observations[name] = dict(decision_digest=decision['decision_digest'], source_sha=decision['source_sha'], status=status, jobs=jobs)
    return plan.evaluate_check_results(decision, observations=observations)


def execute(root, repository, operation, profile, evidence_file, transport, verify, *, initial_raw=None, wrapper=None):
    global g, require, EvidenceError
    helpers = SimpleNamespace(**wrapper) if wrapper else p
    if wrapper:
        g, require, EvidenceError = helpers.g, helpers.require, helpers.EvidenceError
    v = helpers.sibling('verify_before_push')
    root = Path(root).resolve()
    evidence_file = evidence_file or DEFAULT_EVIDENCE
    path = helpers.safe_evidence(v, root, evidence_file, expected_version=5, expected_keys=RECEIPT_KEYS)
    initial_raw = initial_raw if initial_raw is not None else (root / v.CONFIG_RELATIVE).read_bytes()
    initial = g.loads_strict(initial_raw.decode('utf-8-sig'))
    initial_digest = g.hashlib.sha256(initial_raw).hexdigest()
    block = helpers.validate_gitlab_ci_policy(initial)
    require(block is not None and block.get('version') == 2, 'explicit version 2 GitLab configuration required')
    transport = transport or helpers.g.GlabTransport(block['host'])
    before = context(v, root, repository, operation, profile, transport, initial_digest, helpers)
    old = None
    if verify:
        old = g.loads_strict(path.read_text(encoding='utf-8'))
        require(type(old) is dict and set(old) == RECEIPT_KEYS and type(old['version']) is int and old['version'] == 5
                and old['source'] == 'gitlab-ci' and old['scope'] == 'ci-checks-only' and old['gate_authorized'] is False
                and old['authorization'] == 'not_granted' and old['limitations'] == LIMITATIONS,
                'unsupported or malformed check receipt')
        require(old['receipt_sha256'] == g.digest({k: val for k, val in old.items() if k != 'receipt_sha256'}), 'check receipt integrity mismatch')
        helpers.timestamp(old['checked_at'])
        require(g.digest(old['binding']) == g.digest(before), 'receipt local policy/configuration/repository binding changed')
        g.binding_key(old['observation'])
        helpers.timestamp(old['observation']['observed_from'])
        helpers.timestamp(old['observation']['observed_until'])
        require(old['evaluation'] == evaluation(before, old['observation']), 'stored check evaluation differs from actual observations')
    observation = g.collect(before['contract'], transport)
    after = context(v, root, repository, operation, profile, transport, initial_digest, helpers)
    require(before == after, 'local policy/configuration/identity/source/target changed during collection')
    helpers.safe_evidence(v, root, evidence_file, expected_version=5, expected_keys=RECEIPT_KEYS)
    if verify:
        require(g.binding_key(old['observation']) == g.binding_key(observation), 'provider required-proof state changed; recollect check evidence')
        require(g.digest(g.loads_strict(path.read_text(encoding='utf-8'))) == g.digest(old), 'receipt changed during verification')
    result = dict(version=5, source='gitlab-ci', scope='ci-checks-only', gate_authorized=False,
                  authorization='not_granted', limitations=LIMITATIONS[:], checked_at=g.now(), binding=before,
                  observation=observation, evaluation=evaluation(before, observation))
    result['receipt_sha256'] = g.digest(result)
    if not verify:
        v.write_atomic(path, result)
    return result


def collect_evidence(project_root, repository, operation='merge', profile=None, evidence_file=None, transport=None):
    return execute(project_root, repository, operation, profile, evidence_file, transport, False)


def verify_evidence(project_root, repository, operation='merge', profile=None, evidence_file=None, transport=None):
    return execute(project_root, repository, operation, profile, evidence_file, transport, True)
