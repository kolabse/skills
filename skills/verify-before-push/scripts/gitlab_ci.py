#!/usr/bin/env python3
"""Bounded read-only GitLab MR CI collector; observations are not gate receipts."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import quote, urlsplit


class EvidenceError(ValueError):
    """Incomplete, unsupported or changed provider evidence."""


def require(condition, message):
    if not condition:
        raise EvidenceError(message)


def loads_strict(text):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    try:
        return json.loads(text, object_pairs_hook=pairs,
                          parse_constant=lambda _: require(False, 'nonfinite JSON number'))
    except (ValueError, TypeError) as exc:
        raise EvidenceError('invalid JSON document') from exc


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def observation_digest(observation):
    return digest({k: v for k, v in observation.items() if k != 'integrity_digest'})


def valid_host(host):
    require(isinstance(host, str) and len(host) <= 253 and
            re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?', host) and
            all(re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?', label)
                for label in host.split('.')), 'invalid configured host')


def positive(value):
    return type(value) is int and value > 0


def sha(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', value)


CONTRACT_KEYS = {
    'version', 'host', 'project_id', 'mr_iid', 'source_sha', 'target_branch',
    'subject_kind', 'required_jobs', 'require_non_draft', 'require_pipeline_success',
    'require_ready_at_start', 'require_source_review', 'repository', 'profile',
    'operation', 'effective_policy_digest', 'source_snapshot_digest', 'check_map_digest',
}


def validate_contract(contract):
    require(type(contract) is dict and set(contract) == CONTRACT_KEYS,
            'contract must contain exactly the documented keys')
    require(type(contract['version']) is int and contract['version'] == 1, 'unsupported contract version')
    valid_host(contract['host'])
    require(positive(contract['project_id']) and positive(contract['mr_iid']), 'invalid project or MR identity')
    require(sha(contract['source_sha']), 'invalid source SHA')
    for key in ('effective_policy_digest', 'source_snapshot_digest', 'check_map_digest'):
        require(isinstance(contract[key], str) and re.fullmatch('[0-9a-f]{64}', contract[key]),
                'invalid policy/check-map digest')
    for key in ('repository', 'profile', 'target_branch'):
        require(isinstance(contract[key], str) and 0 < len(contract[key]) <= 255 and
                not any(ord(c) < 32 for c in contract[key]), 'invalid contract text')
    require(contract['operation'] in ('push', 'merge', 'build', 'deploy', 'cleanup'), 'invalid operation')
    jobs = contract['required_jobs']
    require(type(jobs) is list and jobs and all(isinstance(x, str) and x and len(x) <= 255 and
            not any(ord(c) < 32 for c in x) for x in jobs) and len(set(jobs)) == len(jobs),
            'required jobs must be nonempty unique exact names')
    for key in ('require_non_draft', 'require_pipeline_success', 'require_ready_at_start', 'require_source_review'):
        require(type(contract[key]) is bool, 'requirement flags must be booleans')
    require(contract['subject_kind'] == 'source_sha', 'only detached source_sha evidence is supported')
    require(not contract['require_ready_at_start'], 'Ready-at-start history is unconfirmed')
    require(not contract['require_source_review'], 'independent source review is unconfirmed')
    return contract


class GlabTransport:
    """Only fixed GET endpoints; glab owns credentials, which are never printed."""
    def __init__(self, host, timeout=60):
        valid_host(host)
        self.host = host
        self.timeout = timeout

    def get(self, endpoint):
        patterns = (
            r'projects/[1-9][0-9]*/merge_requests/[1-9][0-9]*',
            r'projects/[1-9][0-9]*/merge_requests/[1-9][0-9]*/pipelines\?per_page=100&page=[1-9][0-9]*',
            r'projects/[1-9][0-9]*/pipelines/[1-9][0-9]*',
            r'projects/[1-9][0-9]*/pipelines/[1-9][0-9]*/jobs\?per_page=100&page=[1-9][0-9]*&include_retried=false',
            r'projects/[1-9][0-9]*/repository/branches/(?:[A-Za-z0-9_~-]|\.(?!\.)|%[0-9A-F]{2})+',
        )
        require(isinstance(endpoint, str) and '..' not in endpoint and
                any(re.fullmatch(p, endpoint) for p in patterns), 'unsupported API endpoint')
        try:
            result = subprocess.run(['glab', 'api', '--method', 'GET', '--hostname', self.host, endpoint],
                                    capture_output=True, text=True, timeout=self.timeout, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise EvidenceError('GitLab read failed; no provider diagnostic exported') from None
        require(result.returncode == 0, 'GitLab read failed; no provider diagnostic exported')
        return loads_strict(result.stdout)


def object_response(value):
    require(type(value) is dict, 'expected provider object')
    return value


def pages(transport, endpoint, jobs=False):
    result, ids = [], set()
    for page in range(1, 1001):
        suffix = '&include_retried=false' if jobs else ''
        batch = transport.get(f'{endpoint}?per_page=100&page={page}{suffix}')
        require(type(batch) is list and len(batch) <= 100, 'invalid pagination response')
        for entry in batch:
            object_response(entry)
            identity = entry.get('id')
            require(positive(identity) and identity not in ids, 'duplicate or invalid paginated identity')
            ids.add(identity)
            result.append(entry)
        if len(batch) < 100:
            return result
    raise EvidenceError('pagination limit reached; evidence incomplete')


def safe_url(url, host):
    require(isinstance(url, str), 'missing provider URL')
    try:
        parsed = urlsplit(url)
        require(parsed.scheme == 'https' and parsed.netloc.lower() == host.lower() and
                not parsed.username and not parsed.password and not parsed.query and not parsed.fragment and
                not any(ord(c) < 32 for c in url), 'unsafe provider URL')
    except ValueError:
        raise EvidenceError('unsafe provider URL') from None
    return url


def snapshot(contract, transport):
    project = contract['project_id']
    iid = contract['mr_iid']
    base = f'projects/{project}'
    mr_base = f'{base}/merge_requests/{iid}'
    mr = object_response(transport.get(mr_base))
    require(all(type(mr.get(k)) is int and mr[k] == v for k, v in
                [('iid', iid), ('project_id', project), ('source_project_id', project),
                 ('target_project_id', project)]), 'MR identity mismatch or unsupported fork')
    require(mr.get('state') == 'opened' and mr.get('sha') == contract['source_sha'] and
            mr.get('target_branch') == contract['target_branch'], 'MR state/source/target mismatch')
    require(type(mr.get('draft')) is bool, 'unknown MR Draft state')
    require(not contract['require_non_draft'] or not mr['draft'], 'MR is Draft')
    require(type(mr.get('diff_refs')) is dict and
            mr['diff_refs'].get('head_sha') == contract['source_sha'], 'incomplete MR diff refs')
    branch = object_response(transport.get(f"{base}/repository/branches/{quote(contract['target_branch'], safe='')}"))
    require(branch.get('name') == contract['target_branch'] and type(branch.get('commit')) is dict and
            sha(branch['commit'].get('id')), 'invalid current target HEAD')
    pipelines = pages(transport, f'{mr_base}/pipelines')
    relevant = []
    for entry in pipelines:
        pipeline = object_response(transport.get(f"{base}/pipelines/{entry['id']}"))
        require(type(pipeline.get('id')) is int and pipeline['id'] == entry['id'] and
                type(pipeline.get('project_id')) is int and pipeline['project_id'] == project,
                'pipeline identity mismatch')
        if pipeline.get('sha') != contract['source_sha'] or pipeline.get('source') != 'merge_request_event':
            continue
        # Exact MR head ref is a deliberately narrow detached-source provenance boundary.
        require(pipeline.get('ref') == f'refs/merge-requests/{iid}/head',
                'unknown or merged-results pipeline provenance')
        relevant.append(pipeline)
    require(relevant, 'no supported current MR source pipeline')
    pipeline = max(relevant, key=lambda p: p['id'])
    require(pipeline.get('status') in {'created', 'waiting_for_resource', 'preparing', 'pending',
                'running', 'success', 'failed', 'canceled', 'skipped', 'manual', 'scheduled'},
                'unknown pipeline status')
    if contract['require_pipeline_success']:
        require(pipeline['status'] == 'success', 'latest relevant pipeline is not successful')
    selected = {key: pipeline[key] for key in ('id', 'project_id', 'sha', 'source', 'ref', 'status')}
    selected['web_url'] = safe_url(pipeline.get('web_url'), contract['host'])
    jobs = pages(transport, f"{base}/pipelines/{pipeline['id']}/jobs", jobs=True)
    current = []
    for job in jobs:
        identity = job.get('pipeline')
        require(type(identity) is dict and type(identity.get('id')) is int and
                identity['id'] == pipeline['id'] and type(identity.get('project_id')) is int and
                identity['project_id'] == project and identity.get('sha') == contract['source_sha'],
                'job pipeline/project/source mismatch')
        require(job.get('retried', False) is False, 'retried job returned as current')
        require(isinstance(job.get('name'), str) and isinstance(job.get('status'), str), 'invalid job identity/status')
        current.append(dict(id=job['id'], name=job['name'], status=job['status'],
                            web_url=safe_url(job.get('web_url'), contract['host'])))
    for name in contract['required_jobs']:
        matches = [j for j in current if j['name'] == name]
        require(len(matches) == 1 and matches[0]['status'] == 'success',
                'required job missing, ambiguous or unsuccessful')
    return dict(mr=dict(iid=iid, project_id=project, source_project_id=project,
                        target_project_id=project, state=mr['state'], draft=mr['draft'],
                        sha=mr['sha'], target_branch=mr['target_branch'],
                        source_branch=mr.get('source_branch'), diff_refs=mr['diff_refs']),
                target_head=branch['commit']['id'], pipeline=selected,
                relevant_pipeline_ids=sorted(p['id'] for p in relevant),
                jobs=sorted(current, key=lambda j: j['id']))


def now():
    return datetime.now(timezone.utc).isoformat()


def collect(contract, transport):
    """Collect and reobserve; caller must recollect at gate use and recheck policy."""
    contract = copy.deepcopy(validate_contract(contract))
    started = now()
    first = snapshot(contract, transport)
    second = snapshot(contract, transport)
    require(first == second, 'provider state changed during collection; recollect')
    result = dict(kind='gitlab-ci-observation', observation_version=1,
                  contract=contract, contract_digest=digest(contract),
                  observed_from=started, observed_until=now(), reused_existing_pipeline=True,
                  unconfirmed_conditions=['ready_at_start', 'source_review'],
                  authority='observation_only',
                  unproved_bindings=['tracked_remote', 'source_review', 'ready_at_start',
                                     'policy_file_freshness', 'action_authorization'], **second)
    result['integrity_digest'] = observation_digest(result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    command = commands.add_parser('collect', help='read and reobserve MR CI; never authorizes a gate')
    command.add_argument('--contract', required=True, type=Path)
    command.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        raw = args.contract.read_bytes()
        contract = validate_contract(loads_strict(raw.decode('utf-8-sig')))
        result = collect(contract, GlabTransport(contract['host']))
        require(args.contract.read_bytes() == raw, 'contract changed during collection')
        require(args.output.resolve() != args.contract.resolve(), 'output cannot overwrite contract')
        # Exclusive creation avoids overwriting a caller artifact or following an existing symlink.
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, indent=2, sort_keys=True)
            stream.write('\n')
        return 0
    except (EvidenceError, OSError, UnicodeError):
        print('GitLab observation blocked: incomplete, unsupported, changed, or unreadable evidence.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
