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


def load_collection(repository_root: Path) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
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
        eval_path = entry.get("trigger_evals")
        if not isinstance(name, str) or not isinstance(eval_path, str):
            raise EvalError("Every catalog skill requires name and trigger_evals")
        metadata = frontmatter(repository_root / "skills" / name / "SKILL.md")
        description = metadata.get("description", "")
        if not description:
            raise EvalError(f"Skill description is missing: {name}")
        skills.append({"name": name, "description": description})

        data = load_json(repository_root / eval_path, f"Trigger evals for {name}")
        if not isinstance(data, dict) or data.get("skill") != name:
            raise EvalError(f"Trigger eval file does not identify {name}")
        for branch, expected in (("positive", True), ("negative", False)):
            cases = data.get(branch)
            if not isinstance(cases, list):
                raise EvalError(f"{eval_path}: {branch} must be a list")
            for case in cases:
                prompt = case.get("prompt") if isinstance(case, dict) else None
                if not isinstance(prompt, str) or not prompt.strip():
                    raise EvalError(f"{eval_path}: every case requires a prompt")
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
    return sorted(skills, key=lambda item: item["name"]), sorted(
        assertions, key=lambda item: item["id"]
    )


def prepare_suite(repository_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    skills, assertions = load_collection(repository_root)
    public = {
        "schema_version": SCHEMA_VERSION,
        "instructions": (
            "For each case, select every skill whose description should trigger for the "
            "user prompt. Return strict JSON with schema_version, suite_digest, optional "
            "selector metadata, and predictions containing id, selected_skills, and a "
            "short reason. Select no skills when none apply."
        ),
        "skills": skills,
        "cases": [{"id": item["id"], "prompt": item["prompt"]} for item in assertions],
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
    metrics: dict[str, dict[str, int]] = {
        item["name"]: {"tp": 0, "fn": 0, "fp": 0, "tn": 0}
        for item in suite["skills"]
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
        "selector": selector,
        "summary": {
            **totals,
            "assertions": len(assertions),
            "passed": len(assertions) - len(failures),
            "failed": len(failures),
            "accuracy": ratio(totals["tp"] + totals["tn"], len(assertions)),
            "precision": ratio(totals["tp"], totals["tp"] + totals["fp"]),
            "recall": ratio(totals["tp"], totals["tp"] + totals["fn"]),
        },
        "per_skill": per_skill,
        "failures": failures,
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
    return "\n".join(lines).rstrip() + "\n"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_selector(command: list[str], suite: dict[str, Any], timeout: int) -> Any:
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


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repository-root", type=Path, default=REPOSITORY_ROOT)


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
    run.add_argument("--min-accuracy", type=float, default=0.0)
    run.add_argument("selector_command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    try:
        if hasattr(args, "min_accuracy") and not 0.0 <= args.min_accuracy <= 1.0:
            raise EvalError("min-accuracy must be between 0 and 1")
        if hasattr(args, "timeout") and args.timeout <= 0:
            raise EvalError("timeout must be positive")
        root = args.repository_root.resolve()
        suite, assertions = prepare_suite(root)
        if args.command == "prepare":
            write_json(args.output, suite)
            print(f"Prepared {len(suite['cases'])} blind case(s): {args.output}")
            return 0
        if args.command == "run":
            command = args.selector_command
            if command[:1] == ["--"]:
                command = command[1:]
            predictions = run_selector(command, suite, args.timeout)
            validate_predictions(suite, predictions)
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
