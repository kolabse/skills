from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1


class EvalError(RuntimeError):
    pass


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def load_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise EvalError(f"{label} is missing: {path}") from error
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise EvalError(f"{label} is invalid: {path}: {error}") from error


def frontmatter(path: Path) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise EvalError(f"Skill file is missing: {path}") from error
    except UnicodeDecodeError as error:
        raise EvalError(f"Skill file is not valid UTF-8: {path}") from error
    if not text.startswith("---\n"):
        raise EvalError(f"Skill frontmatter is missing: {path}")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise EvalError(f"Skill frontmatter is not terminated: {path}")
    values: dict[str, str] = {}
    for line in text[4:end].splitlines():
        key, separator, value = line.partition(":")
        if not separator:
            raise EvalError(f"Invalid frontmatter line in {path}: {line}")
        values[key.strip()] = value.strip().strip('"')
    return values


def load_collection(
    repository_root: Path, corpus: str = "development"
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    catalog = load_json(repository_root / "skill-catalog.json", "Skill catalog")
    entries = catalog.get("skills") if isinstance(catalog, dict) else None
    if not isinstance(entries, list) or not entries:
        raise EvalError("Skill catalog must contain a non-empty skills list")

    skills: list[dict[str, str]] = []
    assertions: list[dict[str, Any]] = []
    seen_prompts: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise EvalError("Every catalog skill must be an object")
        name = entry.get("name")
        if not isinstance(name, str):
            raise EvalError("Every catalog skill requires a name")
        metadata = frontmatter(repository_root / "skills" / name / "SKILL.md")
        description = metadata.get("description", "")
        if not description:
            raise EvalError(f"Skill description is missing: {name}")
        skills.append({"name": name, "description": description})

    if corpus == "development":
        sources: dict[str, Any] = {}
        for entry in entries:
            name = entry["name"]
            eval_path = entry.get("trigger_evals")
            if not isinstance(eval_path, str):
                raise EvalError("Every catalog skill requires trigger_evals")
            data = load_json(repository_root / eval_path, f"Trigger evals for {name}")
            if not isinstance(data, dict) or data.get("skill") != name:
                raise EvalError(f"Trigger eval file does not identify {name}")
            sources[name] = data
    elif corpus == "release-holdout":
        holdout = catalog.get("release_holdout")
        if not isinstance(holdout, dict):
            raise EvalError("Skill catalog does not define release_holdout")
        path = holdout.get("path")
        expected_digest = holdout.get("sha256")
        if not isinstance(path, str) or not isinstance(expected_digest, str):
            raise EvalError("release_holdout requires path and sha256")
        data = load_json(repository_root / path, "Release holdout")
        if sha256(data) != expected_digest:
            raise EvalError("Release holdout does not match its locked canonical digest")
        if (
            not isinstance(data, dict)
            or data.get("schema_version") != SCHEMA_VERSION
            or data.get("name") != holdout.get("name")
        ):
            raise EvalError("Release holdout schema or name does not match the catalog")
        sources = data.get("skills") if isinstance(data, dict) else None
        if not isinstance(sources, dict):
            raise EvalError("Release holdout must contain a skills object")
    else:
        raise EvalError(f"Unknown corpus: {corpus}")

    known_names = {item["name"] for item in skills}
    evaluated_names = (
        known_names
        if corpus == "development"
        else {
            entry["name"]
            for entry in entries
            if isinstance(entry, dict) and entry.get("status") == "stable"
        }
    )
    if set(sources) != evaluated_names:
        scope = "catalog" if corpus == "development" else "stable catalog"
        raise EvalError(
            f"Evaluation corpus must contain exactly the {scope} skills"
        )
    for name in sorted(sources):
        data = sources[name]
        if not isinstance(data, dict):
            raise EvalError(f"Evaluation data for {name} must be an object")
        for branch, expected in (("positive", True), ("negative", False)):
            cases = data.get(branch)
            if not isinstance(cases, list):
                raise EvalError(f"{corpus}/{name}: {branch} must be a list")
            for case in cases:
                prompt = case.get("prompt") if isinstance(case, dict) else None
                if not isinstance(prompt, str) or not prompt.strip():
                    raise EvalError(f"{corpus}/{name}: every case requires a prompt")
                previous = seen_prompts.get(prompt)
                if previous:
                    raise EvalError(
                        f"Prompt is duplicated across trigger evals: {name} and {previous}"
                    )
                seen_prompts[prompt] = name
                identifier = hashlib.sha256(
                    f"{name}\0{branch}\0{prompt}".encode("utf-8")
                ).hexdigest()[:16]
                assertions.append(
                    {
                        "id": identifier,
                        "prompt": prompt,
                        "target_skill": name,
                        "expected": expected,
                    }
                )
    if corpus == "development" and catalog.get("composition_evals") is not None:
        composition_path = catalog.get("composition_evals")
        if not isinstance(composition_path, str):
            raise EvalError("composition_evals must be a path string")
        composition_data = load_json(
            repository_root / composition_path, "Composition trigger evals"
        )
        cases = composition_data.get("cases") if isinstance(composition_data, dict) else None
        if (
            not isinstance(composition_data, dict)
            or composition_data.get("schema_version") != SCHEMA_VERSION
            or not isinstance(cases, list)
        ):
            raise EvalError("Composition trigger evals must contain schema_version 1 and cases")
        for index, case in enumerate(cases):
            if not isinstance(case, dict):
                raise EvalError(f"composition case {index} must be an object")
            prompt = case.get("prompt")
            expected_skills = case.get("expected_skills")
            reason = case.get("reason")
            if not isinstance(prompt, str) or not prompt.strip():
                raise EvalError(f"composition case {index} requires a prompt")
            if prompt in seen_prompts:
                raise EvalError(
                    f"Prompt is duplicated across trigger evals: compositions and {seen_prompts[prompt]}"
                )
            if (
                not isinstance(expected_skills, list)
                or not expected_skills
                or not all(isinstance(name, str) for name in expected_skills)
                or len(expected_skills) != len(set(expected_skills))
                or set(expected_skills) - known_names
            ):
                raise EvalError(
                    f"composition case {index} expected_skills must be unique known skills"
                )
            if not isinstance(reason, str) or not reason.strip():
                raise EvalError(f"composition case {index} requires a reason")
            seen_prompts[prompt] = "compositions"
            identifier = hashlib.sha256(
                f"composition\0{prompt}".encode("utf-8")
            ).hexdigest()[:16]
            for name in sorted(known_names):
                assertions.append(
                    {
                        "id": identifier,
                        "prompt": prompt,
                        "target_skill": name,
                        "expected": name in expected_skills,
                        "composition": True,
                        "expected_skills": expected_skills,
                    }
                )
    return sorted(skills, key=lambda item: item["name"]), sorted(
        assertions, key=lambda item: (item["id"], item["target_skill"])
    )


def prepare_suite(
    repository_root: Path, corpus: str = "development"
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    skills, assertions = load_collection(repository_root, corpus)
    public = {
        "schema_version": SCHEMA_VERSION,
        "corpus": corpus,
        "instructions": (
            "For each case, select every skill whose description should trigger for the "
            "user prompt. Return strict JSON with schema_version, suite_digest, optional "
            "selector metadata, and predictions containing id, selected_skills, and a "
            "short reason. Select no skills when none apply. When several skills form a "
            "workflow, return them in their intended execution order."
        ),
        "skills": skills,
        "cases": list(
            {
                item["id"]: {"id": item["id"], "prompt": item["prompt"]}
                for item in assertions
            }.values()
        ),
    }
    public["suite_digest"] = sha256(public)
    return public, assertions


def validate_predictions(
    suite: dict[str, Any], predictions: Any
) -> dict[str, dict[str, Any]]:
    if not isinstance(predictions, dict):
        raise EvalError("Prediction root must be an object")
    if predictions.get("schema_version") != SCHEMA_VERSION:
        raise EvalError("Prediction schema_version must be 1")
    if predictions.get("suite_digest") != suite["suite_digest"]:
        raise EvalError("Predictions do not match this blind suite")
    rows = predictions.get("predictions")
    if not isinstance(rows, list):
        raise EvalError("predictions must be a list")
    known_skills = {item["name"] for item in suite["skills"]}
    expected_ids = {item["id"] for item in suite["cases"]}
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise EvalError("Every prediction must be an object")
        identifier = row.get("id")
        selected = row.get("selected_skills")
        reason = row.get("reason")
        if identifier not in expected_ids or identifier in indexed:
            raise EvalError(f"Unknown or duplicated prediction id: {identifier!r}")
        if not isinstance(selected, list) or not all(
            isinstance(name, str) for name in selected
        ):
            raise EvalError(f"Prediction {identifier} selected_skills must be a list")
        if len(selected) != len(set(selected)) or set(selected) - known_skills:
            raise EvalError(f"Prediction {identifier} contains duplicate or unknown skills")
        if not isinstance(reason, str) or not reason.strip():
            raise EvalError(f"Prediction {identifier} requires a short reason")
        indexed[identifier] = row
    missing = expected_ids - set(indexed)
    if missing:
        raise EvalError(f"Predictions are incomplete; missing {len(missing)} case(s)")
    return indexed


def ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def score_suite(
    suite: dict[str, Any], assertions: list[dict[str, Any]], predictions: Any
) -> dict[str, Any]:
    indexed = validate_predictions(suite, predictions)
    asserted_skills = {item["target_skill"] for item in assertions}
    metrics: dict[str, dict[str, int]] = {
        name: {"tp": 0, "fn": 0, "fp": 0, "tn": 0}
        for name in sorted(asserted_skills)
    }
    failures: list[dict[str, Any]] = []
    for assertion in assertions:
        row = indexed[assertion["id"]]
        actual = assertion["target_skill"] in row["selected_skills"]
        expected = assertion["expected"]
        bucket = "tp" if expected and actual else "fn" if expected else "fp" if actual else "tn"
        metrics[assertion["target_skill"]][bucket] += 1
        if actual != expected:
            failures.append(
                {
                    "id": assertion["id"],
                    "target_skill": assertion["target_skill"],
                    "expected_trigger": expected,
                    "selected_skills": row["selected_skills"],
                    "prompt": assertion["prompt"],
                    "selector_reason": row["reason"],
                }
            )

    composition_failures: list[dict[str, Any]] = []
    composition_cases: dict[str, dict[str, Any]] = {}
    for assertion in assertions:
        if assertion.get("composition"):
            composition_cases.setdefault(assertion["id"], assertion)
    for identifier, assertion in sorted(composition_cases.items()):
        actual = indexed[identifier]["selected_skills"]
        expected = assertion["expected_skills"]
        if actual != expected:
            composition_failures.append(
                {
                    "id": identifier,
                    "expected_skills": expected,
                    "selected_skills": actual,
                    "prompt": assertion["prompt"],
                    "selector_reason": indexed[identifier]["reason"],
                }
            )

    per_skill: list[dict[str, Any]] = []
    totals = {key: 0 for key in ("tp", "fn", "fp", "tn")}
    for name in sorted(metrics):
        counts = metrics[name]
        for key in totals:
            totals[key] += counts[key]
        per_skill.append(
            {
                "skill": name,
                **counts,
                "precision": ratio(counts["tp"], counts["tp"] + counts["fp"]),
                "recall": ratio(counts["tp"], counts["tp"] + counts["fn"]),
                "specificity": ratio(counts["tn"], counts["tn"] + counts["fp"]),
            }
        )
    selector = predictions.get("selector", {})
    if not isinstance(selector, dict):
        raise EvalError("selector metadata must be an object")
    return {
        "schema_version": SCHEMA_VERSION,
        "suite_digest": suite["suite_digest"],
        "corpus": suite.get("corpus", "development"),
        "assertion_digest": sha256(assertions),
        "selector": selector,
        "summary": {
            **totals,
            "assertions": len(assertions),
            "passed": len(assertions) - len(failures),
            "failed": len(failures),
            "accuracy": ratio(totals["tp"] + totals["tn"], len(assertions)),
            "precision": ratio(totals["tp"], totals["tp"] + totals["fp"]),
            "recall": ratio(totals["tp"], totals["tp"] + totals["fn"]),
            "composition_cases": len(composition_cases),
            "composition_passed": len(composition_cases) - len(composition_failures),
            "composition_failed": len(composition_failures),
            "composition_accuracy": ratio(
                len(composition_cases) - len(composition_failures), len(composition_cases)
            ),
        },
        "per_skill": per_skill,
        "failures": failures,
        "composition_failures": composition_failures,
    }


def markdown_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Trigger evaluation report",
        "",
        f"- Assertions: {summary['assertions']}",
        f"- Passed: {summary['passed']}",
        f"- Failed: {summary['failed']}",
        f"- Accuracy: {summary['accuracy']:.2%}",
        f"- Precision: {summary['precision']:.2%}",
        f"- Recall: {summary['recall']:.2%}",
        "",
        "| Skill | TP | FN | FP | TN | Precision | Recall | Specificity |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    if summary.get("composition_cases"):
        lines[8:8] = [
            f"- Composition cases: {summary['composition_cases']}",
            f"- Exact composition accuracy: {summary['composition_accuracy']:.2%}",
        ]
    for item in report["per_skill"]:
        lines.append(
            f"| `{item['skill']}` | {item['tp']} | {item['fn']} | {item['fp']} | "
            f"{item['tn']} | {item['precision']:.2%} | {item['recall']:.2%} | "
            f"{item['specificity']:.2%} |"
        )
    if report["failures"]:
        lines.extend(["", "## Failures", ""])
        for failure in report["failures"]:
            expectation = "trigger" if failure["expected_trigger"] else "do not trigger"
            selected = ", ".join(failure["selected_skills"]) or "none"
            lines.extend(
                [
                    f"### `{failure['id']}` — `{failure['target_skill']}` should {expectation}",
                    "",
                    f"Prompt: {failure['prompt']}",
                    "",
                    f"Selected: {selected}",
                    "",
                    f"Reason: {failure['selector_reason']}",
                    "",
                ]
            )
    if report.get("composition_failures"):
        lines.extend(["", "## Composition failures", ""])
        for failure in report["composition_failures"]:
            expected = ", ".join(failure["expected_skills"])
            selected = ", ".join(failure["selected_skills"]) or "none"
            lines.extend(
                [
                    f"### `{failure['id']}` — exact ordered selection",
                    "",
                    f"Prompt: {failure['prompt']}",
                    "",
                    f"Expected: {expected}",
                    "",
                    f"Selected: {selected}",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def compare_reports(
    baseline: Any,
    candidate: Any,
    max_accuracy_drop: float = 0.0,
    max_precision_drop: float = 0.0,
    max_recall_drop: float = 0.0,
    max_per_skill_drop: float = 0.0,
) -> dict[str, Any]:
    for label, report in (("baseline", baseline), ("candidate", candidate)):
        if not isinstance(report, dict) or not isinstance(report.get("summary"), dict):
            raise EvalError(f"{label} report is invalid")
        if not isinstance(report.get("assertion_digest"), str):
            raise EvalError(f"{label} report has no assertion_digest")
    if baseline["assertion_digest"] != candidate["assertion_digest"]:
        raise EvalError("Reports use different evaluation assertions")
    baseline_rows = baseline.get("per_skill")
    candidate_rows = candidate.get("per_skill")
    if not isinstance(baseline_rows, list) or not all(
        isinstance(item, dict) for item in baseline_rows
    ):
        raise EvalError("baseline report per_skill is invalid")
    if not isinstance(candidate_rows, list) or not all(
        isinstance(item, dict) for item in candidate_rows
    ):
        raise EvalError("candidate report per_skill is invalid")
    baseline_skills = {item.get("skill"): item for item in baseline_rows}
    candidate_skills = {item.get("skill"): item for item in candidate_rows}
    if None in baseline_skills or None in candidate_skills:
        raise EvalError("Reports contain a skill row without a name")
    if len(baseline_skills) != len(baseline_rows) or len(candidate_skills) != len(
        candidate_rows
    ):
        raise EvalError("Reports contain duplicate skill rows")
    if baseline_skills.keys() != candidate_skills.keys():
        raise EvalError("Reports contain different skill sets")

    limits = {
        "accuracy": max_accuracy_drop,
        "precision": max_precision_drop,
        "recall": max_recall_drop,
    }
    deltas: dict[str, float] = {}
    regressions: list[dict[str, Any]] = []
    for metric, allowed_drop in limits.items():
        before = baseline["summary"].get(metric)
        after = candidate["summary"].get(metric)
        if not isinstance(before, (int, float)) or not isinstance(after, (int, float)):
            raise EvalError(f"Reports are missing numeric {metric}")
        delta = round(after - before, 4)
        deltas[metric] = delta
        if delta < -allowed_drop:
            regressions.append(
                {
                    "scope": "overall",
                    "metric": metric,
                    "baseline": before,
                    "candidate": after,
                    "delta": delta,
                    "allowed_drop": allowed_drop,
                }
            )
    per_skill: list[dict[str, Any]] = []
    for name in sorted(baseline_skills):
        row = {"skill": name}
        for metric in ("precision", "recall", "specificity"):
            before = baseline_skills[name].get(metric)
            after = candidate_skills[name].get(metric)
            if not isinstance(before, (int, float)) or not isinstance(after, (int, float)):
                raise EvalError(f"Reports are missing numeric {metric} for {name}")
            row[metric] = round(after - before, 4)
            if row[metric] < -max_per_skill_drop:
                regressions.append(
                    {
                        "scope": name,
                        "metric": metric,
                        "baseline": before,
                        "candidate": after,
                        "delta": row[metric],
                        "allowed_drop": max_per_skill_drop,
                    }
                )
        per_skill.append(row)
    return {
        "schema_version": SCHEMA_VERSION,
        "assertion_digest": baseline["assertion_digest"],
        "baseline_selector": baseline.get("selector", {}),
        "candidate_selector": candidate.get("selector", {}),
        "deltas": deltas,
        "per_skill_deltas": per_skill,
        "regressions": regressions,
        "passed": not regressions,
    }


def comparison_markdown(comparison: dict[str, Any]) -> str:
    status = "PASS" if comparison["passed"] else "FAIL"
    lines = [
        "# Trigger evaluation comparison",
        "",
        f"- Status: {status}",
        f"- Accuracy delta: {comparison['deltas']['accuracy']:+.2%}",
        f"- Precision delta: {comparison['deltas']['precision']:+.2%}",
        f"- Recall delta: {comparison['deltas']['recall']:+.2%}",
        "",
        "| Skill | Precision delta | Recall delta | Specificity delta |",
        "|---|---:|---:|---:|",
    ]
    for item in comparison["per_skill_deltas"]:
        lines.append(
            f"| `{item['skill']}` | {item['precision']:+.2%} | "
            f"{item['recall']:+.2%} | {item['specificity']:+.2%} |"
        )
    if comparison["regressions"]:
        lines.extend(["", "## Regressions", ""])
        for item in comparison["regressions"]:
            lines.append(
                f"- {item['scope']} {item['metric']}: {item['baseline']:.2%} -> "
                f"{item['candidate']:.2%} (allowed drop {item['allowed_drop']:.2%})"
            )
    return "\n".join(lines) + "\n"


def aggregate_predictions(suite: dict[str, Any], runs: list[Any]) -> dict[str, Any]:
    if len(runs) < 3 or len(runs) % 2 == 0:
        raise EvalError("Aggregation requires an odd number of at least 3 prediction runs")
    indexed_runs = [validate_predictions(suite, run) for run in runs]
    threshold = len(runs) // 2 + 1
    predictions: list[dict[str, Any]] = []
    for case in suite["cases"]:
        identifier = case["id"]
        counts = {item["name"]: 0 for item in suite["skills"]}
        for indexed in indexed_runs:
            for name in indexed[identifier]["selected_skills"]:
                counts[name] += 1
        selected_names = [name for name, count in counts.items() if count >= threshold]
        positions: dict[str, list[int]] = {name: [] for name in selected_names}
        for indexed in indexed_runs:
            ordered = indexed[identifier]["selected_skills"]
            for position, name in enumerate(ordered):
                if name in positions:
                    positions[name].append(position)
        selected = sorted(
            selected_names,
            key=lambda name: (
                sum(positions[name]) / len(positions[name]) if positions[name] else 10**6,
                name,
            ),
        )
        decisions = ", ".join(
            f"{name}={count}/{len(runs)}" for name, count in sorted(counts.items()) if count
        )
        predictions.append(
            {
                "id": identifier,
                "selected_skills": selected,
                "reason": f"Majority vote ({decisions or 'no selections'}).",
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "suite_digest": suite["suite_digest"],
        "selector": {
            "method": "majority-vote",
            "run_count": len(runs),
            "threshold": threshold,
            "runs": [run.get("selector", {}) if isinstance(run, dict) else {} for run in runs],
        },
        "predictions": predictions,
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def invoke_selector(command: list[str], suite: dict[str, Any], timeout: int) -> Any:
    if not command:
        raise EvalError("Selector command is required after --")
    try:
        result = subprocess.run(
            command,
            input=json.dumps(suite).encode("utf-8"),
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise EvalError(f"Selector could not run: {error}") from error
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise EvalError(f"Selector exited with {result.returncode}: {detail[-500:]}")
    try:
        return json.loads(result.stdout.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise EvalError(f"Selector did not return strict JSON: {error}") from error


def run_selector(
    command: list[str], suite: dict[str, Any], timeout: int, batch_size: int = 0
) -> Any:
    cases = suite.get("cases")
    if not isinstance(cases, list):
        raise EvalError("Suite cases must be a list")
    if batch_size <= 0 or len(cases) <= batch_size:
        return invoke_selector(command, suite, timeout)
    predictions: list[dict[str, Any]] = []
    selectors: list[dict[str, Any]] = []
    batch_count = (len(cases) + batch_size - 1) // batch_size
    for index in range(batch_count):
        batch_suite = dict(suite)
        parent_suite_digest = batch_suite.pop("suite_digest")
        batch_suite["cases"] = cases[index * batch_size : (index + 1) * batch_size]
        batch_suite["batch"] = {
            "index": index + 1,
            "count": batch_count,
            "case_count": len(batch_suite["cases"]),
            "parent_suite_digest": parent_suite_digest,
        }
        batch_suite["suite_digest"] = sha256(batch_suite)
        batch_predictions = invoke_selector(command, batch_suite, timeout)
        validate_predictions(batch_suite, batch_predictions)
        predictions.extend(batch_predictions["predictions"])
        selector = batch_predictions.get("selector", {})
        selectors.append(selector if isinstance(selector, dict) else {})
    return {
        "schema_version": SCHEMA_VERSION,
        "suite_digest": suite["suite_digest"],
        "selector": {
            "method": "batched-external-selector",
            "batch_size": batch_size,
            "batch_count": batch_count,
            "batches": selectors,
        },
        "predictions": predictions,
    }


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repository-root", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument(
        "--corpus",
        choices=("development", "release-holdout"),
        default="development",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare and score blind skill trigger evaluations."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    add_common(prepare)
    prepare.add_argument("--output", type=Path, required=True)
    score = commands.add_parser("score")
    add_common(score)
    score.add_argument("--predictions", type=Path, required=True)
    score.add_argument("--json-output", type=Path)
    score.add_argument("--markdown-output", type=Path)
    score.add_argument("--min-accuracy", type=float, default=0.0)
    run = commands.add_parser("run")
    add_common(run)
    run.add_argument("--predictions-output", type=Path, required=True)
    run.add_argument("--json-output", type=Path)
    run.add_argument("--markdown-output", type=Path)
    run.add_argument("--timeout", type=int, default=600)
    run.add_argument("--batch-size", type=int, default=64)
    run.add_argument("--min-accuracy", type=float, default=0.0)
    run.add_argument("selector_command", nargs=argparse.REMAINDER)
    aggregate = commands.add_parser("aggregate")
    add_common(aggregate)
    aggregate.add_argument("--predictions", type=Path, nargs="+", required=True)
    aggregate.add_argument("--predictions-output", type=Path, required=True)
    aggregate.add_argument("--json-output", type=Path)
    aggregate.add_argument("--markdown-output", type=Path)
    aggregate.add_argument("--min-accuracy", type=float, default=0.0)
    compare = commands.add_parser("compare")
    compare.add_argument("--repository-root", type=Path, default=REPOSITORY_ROOT)
    compare.add_argument("--baseline", type=Path)
    compare.add_argument("--candidate", type=Path, required=True)
    compare.add_argument("--json-output", type=Path)
    compare.add_argument("--markdown-output", type=Path)
    compare.add_argument("--max-accuracy-drop", type=float, default=0.0)
    compare.add_argument("--max-precision-drop", type=float, default=0.0)
    compare.add_argument("--max-recall-drop", type=float, default=0.0)
    compare.add_argument("--max-per-skill-drop", type=float, default=0.0)
    args = parser.parse_args(argv)
    try:
        if args.command == "compare":
            thresholds = (
                args.max_accuracy_drop,
                args.max_precision_drop,
                args.max_recall_drop,
                args.max_per_skill_drop,
            )
            if any(value < 0.0 or value > 1.0 for value in thresholds):
                raise EvalError("comparison drop limits must be between 0 and 1")
            baseline_path = args.baseline
            if baseline_path is None:
                catalog = load_json(
                    args.repository_root.resolve() / "skill-catalog.json",
                    "Skill catalog",
                )
                holdout = catalog.get("release_holdout") if isinstance(catalog, dict) else None
                baseline_name = (
                    holdout.get("baseline_report") if isinstance(holdout, dict) else None
                )
                if not isinstance(baseline_name, str):
                    raise EvalError("Skill catalog does not define a holdout baseline report")
                baseline_path = args.repository_root.resolve() / baseline_name
            comparison = compare_reports(
                load_json(baseline_path, "Baseline report"),
                load_json(args.candidate, "Candidate report"),
                *thresholds,
            )
            if args.json_output:
                write_json(args.json_output, comparison)
            if args.markdown_output:
                args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
                args.markdown_output.write_text(
                    comparison_markdown(comparison), encoding="utf-8"
                )
            print("Trigger comparison: " + ("passed" if comparison["passed"] else "failed"))
            return 0 if comparison["passed"] else 1
        if hasattr(args, "min_accuracy") and not 0.0 <= args.min_accuracy <= 1.0:
            raise EvalError("min-accuracy must be between 0 and 1")
        if hasattr(args, "timeout") and args.timeout <= 0:
            raise EvalError("timeout must be positive")
        if hasattr(args, "batch_size") and args.batch_size <= 0:
            raise EvalError("batch-size must be positive")
        root = args.repository_root.resolve()
        suite, assertions = prepare_suite(root, args.corpus)
        if args.command == "prepare":
            write_json(args.output, suite)
            print(f"Prepared {len(suite['cases'])} blind case(s): {args.output}")
            return 0
        if args.command == "run":
            command = args.selector_command
            if command[:1] == ["--"]:
                command = command[1:]
            predictions = run_selector(command, suite, args.timeout, args.batch_size)
            validate_predictions(suite, predictions)
            write_json(args.predictions_output, predictions)
        elif args.command == "aggregate":
            runs = [load_json(path, f"Predictions {path}") for path in args.predictions]
            predictions = aggregate_predictions(suite, runs)
            write_json(args.predictions_output, predictions)
        else:
            predictions = load_json(args.predictions, "Predictions")
        report = score_suite(suite, assertions, predictions)
        if args.json_output:
            write_json(args.json_output, report)
        if args.markdown_output:
            args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
            args.markdown_output.write_text(markdown_report(report), encoding="utf-8")
        summary = report["summary"]
        print(
            f"Trigger evals: {summary['passed']}/{summary['assertions']} passed; "
            f"accuracy={summary['accuracy']:.2%}, precision={summary['precision']:.2%}, "
            f"recall={summary['recall']:.2%}"
        )
        return 0 if summary["accuracy"] >= args.min_accuracy else 1
    except EvalError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
