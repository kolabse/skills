#!/usr/bin/env python3
"""Policy-bound GitLab CI-check receipts; read-only and never gate authorization."""
import argparse
import copy
from datetime import datetime
import importlib.util
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit


def sibling(name):
    spec = importlib.util.spec_from_file_location('_policy_ci_' + name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


g = sibling('gitlab_ci')
policy_loader = sibling('project_policy')
EvidenceError = g.EvidenceError
require = g.require
DEFAULT_EVIDENCE = '.agents/verify-before-push/gitlab-ci-evidence.json'
LIMITATIONS = ['source_review_unconfirmed', 'ready_at_start_unconfirmed',
               'whole_pipeline_success_required', 'no_push_or_merge_authorization',
               'no_pipeline_mutation_or_local_execution']
RECEIPT_KEYS = {'version', 'source', 'scope', 'gate_authorized', 'authorization',
                'limitations', 'checked_at', 'binding', 'observation', 'receipt_sha256'}


def text(value):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 255 and not any(ord(c) < 32 for c in value)


def validate_gitlab_ci_policy(config):
    """Validate explicit mapping only; never reads Git, policy, files or provider."""
    if 'gitlab_ci' not in config:
        return None
    block = config['gitlab_ci']
    require(type(block) is dict and set(block) == {'host', 'project_id', 'remote', 'mr_iid', 'checks'},
            'gitlab_ci requires exactly host, project_id, remote, mr_iid and checks')
    g.valid_host(block['host'])
    require(g.positive(block['project_id']) and g.positive(block['mr_iid']), 'invalid configured project/MR identity')
    require(text(block['remote']) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', block['remote']), 'invalid remote name')
    checks = config.get('checks')
    require(type(checks) is list and checks, 'checks must be a nonempty list')
    required, names = set(), set()
    for check in checks:
        require(type(check) is dict and text(check.get('name')), 'invalid check name')
        require(check['name'] not in names, 'duplicate check name')
        names.add(check['name'])
        enabled, mandatory = check.get('enabled', True), check.get('required', True)
        require(type(enabled) is bool and type(mandatory) is bool, 'check flags must be booleans')
        require(enabled or not mandatory, 'required checks cannot be disabled')
        if enabled and mandatory:
            required.add(check['name'])
    mapping = block['checks']
    require(type(mapping) is dict and required and set(mapping) == required,
            'GitLab mapping must cover exactly all enabled required checks')
    jobs = []
    for values in mapping.values():
        require(type(values) is list and values and all(text(x) for x in values),
                'check jobs must be nonempty exact names')
        jobs.extend(values)
    require(len(jobs) == len(set(jobs)), 'job names must be unique across the check map')
    return copy.deepcopy(block)


def remote_path(value, host):
    """Accept only credential-free standard HTTPS or GitLab git SSH URLs."""
    require(isinstance(value, str) and value and not any(ord(c) < 33 for c in value), 'unsafe remote URL')
    scp = re.fullmatch(r'git@([^/:]+):([^?#]+)', value)
    if scp:
        require(scp[1].lower() == host.lower(), 'foreign remote host')
        path = scp[2]
    else:
        try:
            parsed = urlsplit(value)
            require(parsed.scheme in ('https', 'ssh') and parsed.hostname and parsed.hostname.lower() == host.lower()
                    and parsed.port is None and not parsed.password and not parsed.query and not parsed.fragment,
                    'unsafe or foreign remote URL')
            require((parsed.scheme == 'https' and parsed.username is None) or
                    (parsed.scheme == 'ssh' and parsed.username == 'git'), 'credential-bearing remote URL')
            path = parsed.path.removeprefix('/')
        except ValueError:
            raise EvidenceError('unsafe remote URL') from None
    path = path.removesuffix('.git')
    require(re.fullmatch(r'[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+', path) and
            all(part not in ('.', '..') for part in path.split('/')), 'invalid remote project path')
    return path


def git_lines(v, root, *args):
    return v.git(root, *args).decode('utf-8').strip().splitlines()


def identity(v, root, block, transport):
    branch = git_lines(v, root, 'branch', '--show-current')
    require(len(branch) == 1 and text(branch[0]), 'detached or ambiguous local branch')
    branch = branch[0]
    remote = git_lines(v, root, 'config', '--get-all', f'branch.{branch}.remote')
    merge = git_lines(v, root, 'config', '--get-all', f'branch.{branch}.merge')
    require(remote == [block['remote']] and len(merge) == 1 and merge[0].startswith('refs/heads/')
            and len(merge[0]) > len('refs/heads/'), 'tracked remote/source ref mismatch')
    source_branch = merge[0][len('refs/heads/'):]
    urls = {}
    for kind, args in [('stored_fetch', ('config', '--get-all', f"remote.{block['remote']}.url")),
                       ('fetch', ('remote', 'get-url', '--all', block['remote'])),
                       ('push', ('remote', 'get-url', '--push', '--all', block['remote']))]:
        values = git_lines(v, root, *args)
        require(len(values) == 1, 'ambiguous remote URLs')
        urls[kind] = values[0]
    # Inspect raw pushurl as well: rewrite rules must not conceal stored credentials.
    raw_push = v.git(root, 'config', '--get-all', f"remote.{block['remote']}.pushurl", check=False).decode().strip().splitlines()
    require(len(raw_push) <= 1, 'ambiguous stored push URL')
    if raw_push:
        urls['stored_push'] = raw_push[0]
    # A separate configured push remote would not publish the subject to this project.
    for option in (f'branch.{branch}.pushRemote', 'remote.pushDefault'):
        selected = v.git(root, 'config', '--get-all', option, check=False).decode().strip().splitlines()
        require(not selected or selected == [block['remote']], 'foreign or ambiguous push remote')
    paths = {remote_path(url, block['host']) for url in urls.values()}
    require(len(paths) == 1, 'fetch/push project mismatch')
    project = g.object_response(transport.get(f"projects/{block['project_id']}"))
    require(type(project.get('id')) is int and project['id'] == block['project_id'] and
            project.get('path_with_namespace') == next(iter(paths)), 'configured project does not match tracked remote')
    return dict(remote=block['remote'], branch=branch, source_ref=merge[0], source_branch=source_branch,
                urls=urls, project_id=project['id'], path_with_namespace=project['path_with_namespace'])


def safe_evidence(v, root, value):
    path = Path(value or DEFAULT_EVIDENCE)
    require(not path.is_absolute() and ':' not in str(path) and '..' not in path.parts,
            'evidence path must stay inside project root')
    path = root / path
    v.reject_workspace_links(root, path)
    require(path.resolve().is_relative_to(root) and path != root and
            '.git' not in path.relative_to(root).parts and
            path not in {root / relative for relative in (*policy_loader.CANDIDATES, *policy_loader.LEGACY)},
            'evidence cannot overwrite configuration, policy or Git metadata')
    for option in ('--git-dir', '--git-common-dir'):
        metadata = Path(git_lines(v, root, 'rev-parse', '--path-format=absolute', option)[0]).resolve()
        require(not path.resolve().is_relative_to(metadata), 'evidence cannot overwrite actual Git metadata')
    result = v.run_process(['git', '-C', str(root), 'check-ignore', '--quiet', '--', str(path)], root)
    require(result.returncode == 0, 'Evidence must be ignored by Git; explicitly add the evidence path to .gitignore first')
    if path.exists():
        require(path.is_file(), 'evidence must be a regular file')
        existing = g.loads_strict(path.read_text(encoding='utf-8'))
        require(type(existing) is dict and set(existing) == RECEIPT_KEYS and
                type(existing.get('version')) is int and existing['version'] == 4 and
                existing.get('source') == 'gitlab-ci' and existing.get('scope') == 'ci-checks-only',
                'refusing to overwrite a non-policy-CI receipt or configuration')
    return path


def context(v, root, repository, operation, profile, transport, expected_config_digest):
    require(operation == 'merge', 'only merge-context CI-check collection is supported')
    for relative in ('.agents', '.agents/verify-before-push', '.agents/kolabse', str(v.CONFIG_RELATIVE), policy_loader.POLICY):
        v.reject_workspace_links(root, root / relative)
    config_raw = (root / v.CONFIG_RELATIVE).read_bytes()
    # Strictly parse first even when legacy config parsing is less restrictive.
    parsed = g.loads_strict(config_raw.decode('utf-8-sig'))
    require(g.hashlib.sha256(config_raw).hexdigest() == expected_config_digest,
            'configuration changed after provider host selection')
    config, _ = v.load_config(root)
    require(g.digest(parsed) == g.digest(config), 'configuration changed during loading')
    block = validate_gitlab_ci_policy(config)
    require(block is not None, 'explicit gitlab_ci configuration is required')
    require(getattr(transport, 'host', block['host']) == block['host'], 'transport host differs from selected configuration')
    entries = config['repositories']
    require(len(entries) == 1 and entries[0]['name'] == repository and
            (root / entries[0]['path']).resolve() == root and
            entries[0].get('require_clean', True) is True and
            entries[0].get('require_upstream_current', True) is True,
            'only one clean/current repository at project root is supported')
    for check in config['checks']:
        v.validate_check(check, root, [root])
    report = policy_loader.load_project_policy(root, repository=repository, operation=operation, profile=profile)
    require(report['status'] == 'configured' and not report['dependent_action_blockers'].get(operation),
            'policy is absent, invalid, expired or blocked for operation')
    policy = report['effective_policy']
    verification = policy['verification']
    require(verification['execution'] == 'ci' and verification['provider'] == 'gitlab' and
            verification['subject'] == 'source_sha', 'unsupported policy provider/execution/subject')
    require(verification['reuse_successful_result'] is True, 'read-only successful-result reuse is unsupported by policy')
    publication = policy['publication']['pipeline']
    require(publication['event'] == 'merge_request', 'policy must declare merge_request pipeline events')
    ident = identity(v, root, block, transport)
    v.refresh_required_upstreams(config, root)
    states = v.capture_states(config, root)
    state = states[0]
    require(state['clean'] and state['head'] == state['upstream_sha'] and state['ahead'] == state['behind'] == 0,
            'source HEAD must equal fresh remote upstream')
    contract = dict(version=1, host=block['host'], project_id=block['project_id'], mr_iid=block['mr_iid'],
                    source_sha=state['head'], target_branch=publication['target_branch'], subject_kind='source_sha',
                    required_jobs=sorted(job for jobs in block['checks'].values() for job in jobs),
                    require_non_draft=publication['require_ready'], require_pipeline_success=True,
                    require_ready_at_start=False, require_source_review=False, repository=repository,
                    profile=profile, operation=operation, effective_policy_digest=report['effective_digest'],
                    source_snapshot_digest=report['source_snapshot_digest'], check_map_digest=g.digest(block['checks']))
    g.validate_contract(contract)
    binding = dict(project_root=str(root), repository=repository, operation=operation, profile=profile,
                   config=config, config_raw_sha256=g.hashlib.sha256(config_raw).hexdigest(),
                   repositories=states, identity=ident, contract=contract,
                   effective_policy=policy, source_hashes=report['source_hashes'],
                   effective_policy_digest=report['effective_digest'], source_snapshot_digest=report['source_snapshot_digest'],
                   check_map=block['checks'], check_map_digest=g.digest(block['checks']),
                   unconfirmed_diagnostics=[{'code': x['code'], 'severity': x['severity'], 'path': x['path'],
                                            'pointer': x['pointer']} for x in report['diagnostics'] if not x['blocking']])
    return binding


def semantic(observation):
    return {key: value for key, value in observation.items()
            if key not in ('observed_from', 'observed_until', 'integrity_digest')}


def timestamp(value):
    require(isinstance(value, str), 'invalid receipt timestamp')
    try:
        require(datetime.fromisoformat(value).utcoffset() is not None, 'timestamp needs timezone')
    except ValueError:
        raise EvidenceError('invalid receipt timestamp') from None


def execute(root, repository, operation, profile, evidence_file, transport, verify):
    root = Path(root).resolve()
    v = sibling('verify_before_push')
    path = safe_evidence(v, root, evidence_file)
    # Host is configured locally, never taken from caller-supplied receipt.
    initial_raw = (root / v.CONFIG_RELATIVE).read_bytes()
    initial = g.loads_strict(initial_raw.decode('utf-8-sig'))
    initial_digest = g.hashlib.sha256(initial_raw).hexdigest()
    block = validate_gitlab_ci_policy(initial)
    require(block is not None, 'explicit gitlab_ci configuration is required')
    transport = transport or g.GlabTransport(block['host'])
    before = context(v, root, repository, operation, profile, transport, initial_digest)
    old = None
    if verify:
        old = g.loads_strict(path.read_text(encoding='utf-8'))
        require(type(old) is dict and set(old) == RECEIPT_KEYS and type(old['version']) is int and old['version'] == 4
                and old['source'] == 'gitlab-ci' and old['scope'] == 'ci-checks-only'
                and old['gate_authorized'] is False and old['authorization'] == 'not_granted'
                and old['limitations'] == LIMITATIONS, 'unsupported or malformed CI-check receipt')
        require(old['receipt_sha256'] == g.digest({k: val for k, val in old.items() if k != 'receipt_sha256'}),
                'CI-check receipt integrity mismatch')
        timestamp(old['checked_at'])
        require(g.digest(old['binding']) == g.digest(before), 'receipt local policy/configuration/repository binding changed')
    observation = g.collect(before['contract'], transport)
    require(observation['mr']['source_branch'] == before['identity']['source_branch'], 'MR source branch differs from tracked source ref')
    after = context(v, root, repository, operation, profile, transport, initial_digest)
    require(before == after, 'local policy/configuration/identity/source changed during collection')
    safe_evidence(v, root, evidence_file)
    if verify:
        previous = old['observation']
        require(type(previous) is dict and set(previous) == set(observation), 'invalid observation shape')
        timestamp(previous['observed_from'])
        timestamp(previous['observed_until'])
        require(previous['integrity_digest'] == g.observation_digest(previous), 'observation integrity mismatch')
        require(g.digest(semantic(previous)) == g.digest(semantic(observation)), 'provider state changed; recollect CI-check evidence')
        require(g.digest(g.loads_strict(path.read_text(encoding='utf-8'))) == g.digest(old), 'receipt changed during verification')
        return old
    result = dict(version=4, source='gitlab-ci', scope='ci-checks-only', gate_authorized=False,
                  authorization='not_granted', limitations=LIMITATIONS[:], checked_at=g.now(),
                  binding=before, observation=observation)
    result['receipt_sha256'] = g.digest(result)
    v.write_atomic(path, result)
    return result


def collect_evidence(project_root, repository, operation='merge', profile=None, evidence_file=None, transport=None):
    return execute(project_root, repository, operation, profile, evidence_file, transport, False)


def verify_evidence(project_root, repository, operation='merge', profile=None, evidence_file=None, transport=None):
    return execute(project_root, repository, operation, profile, evidence_file, transport, True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('collect', 'verify'))
    parser.add_argument('--project-root', required=True, type=Path)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--operation', choices=('merge',), required=True)
    parser.add_argument('--profile')
    parser.add_argument('--evidence-file')
    args = parser.parse_args(argv)
    try:
        action = collect_evidence if args.command == 'collect' else verify_evidence
        result = action(args.project_root, args.repository, args.operation, args.profile, args.evidence_file)
        print('GitLab CI checks ' + ('collected' if args.command == 'collect' else 'revalidated') +
              '; push/merge authorization not granted; source review and Ready-at-start unconfirmed.')
        return 0
    except Exception as exc:
        # Never export provider diagnostics, repository URLs, tokens or caller artifact contents.
        message = str(exc) if isinstance(exc, EvidenceError) else 'unreadable, unsupported or changed local/provider state'
        print('GitLab CI checks blocked: ' + message, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
