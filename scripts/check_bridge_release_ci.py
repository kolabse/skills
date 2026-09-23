"""Fail closed unless the integrated bridge release source has successful CI."""
import argparse
import json
from pathlib import Path
import subprocess


REQUIRED = {
    "Validate skills": {"skills-cli-discovery"} | {
        f"validate ({os}, {version})" for os in ("ubuntu-latest", "windows-latest", "macos-latest")
        for version in ("3.11", "3.13")},
    "Security": {"static-security"},
    "Telegram bridge prototype": {"windows-prototype (3.11)", "windows-prototype (3.13)"},
}


def validate_runs(runs, commit):
    selected = []
    for workflow in REQUIRED:
        matches = [r for r in runs if r.get("name") == workflow and r.get("head_sha") == commit
                   and r.get("event") == "push" and r.get("head_branch") == "main"]
        if not matches:
            raise ValueError(f"Missing main CI: {workflow}")
        latest = max(matches, key=lambda r: (r["id"], r.get("run_attempt", 1)))
        if latest.get("status") != "completed" or latest.get("conclusion") != "success":
            raise ValueError(f"Main CI has not passed: {workflow}")
        selected.append(latest)
    return selected


def validate_jobs(jobs, workflow):
    for name in REQUIRED[workflow]:
        matching = [job for job in jobs if job.get("name") == name]
        if len(matching) != 1 or matching[0].get("conclusion") != "success":
            raise ValueError(f"Required CI job missing or unsuccessful: {name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    args = parser.parse_args()
    commit = subprocess.check_output(["git", "-C", str(args.source), "rev-parse", "HEAD"], text=True).strip()
    payload = json.loads(subprocess.check_output([
        "gh", "api", f"repos/{args.repository}/actions/runs?head_sha={commit}&event=push&per_page=100"
    ], text=True))
    if payload.get("total_count", 0) > 100:
        raise ValueError("Too many matching runs; inspect CI history before release")
    for run in validate_runs(payload["workflow_runs"], commit):
        jobs = json.loads(subprocess.check_output([
            "gh", "api", f"repos/{args.repository}/actions/runs/{run['id']}/jobs?filter=latest&per_page=100"
        ], text=True))
        if jobs.get("total_count", 0) > 100:
            raise ValueError("Too many CI jobs; inspect required coverage")
        validate_jobs(jobs["jobs"], run["name"])
    print(f"Required main CI passed for {commit}")


if __name__ == "__main__":
    main()
