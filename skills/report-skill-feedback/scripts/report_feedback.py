from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


REPOSITORY = "kolabse/skills"
MAX_INPUT_BYTES = 32_768
MAX_REPORT_BYTES = 24_000
NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")
FORBIDDEN = (
    ("URL", re.compile(r"(?i)\b(?:https?|ssh|git)://|\bwww\.")),
    ("email address", re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")),
    ("Windows path", re.compile(r"(?i)(?<![A-Z0-9_])[A-Z]:[\\/]")),
    ("home path", re.compile(r"(?i)(?<![A-Z0-9_])(?:/home/|/Users/|~[/\\])")),
    ("secret-like value", re.compile(r"(?i)\b(?:gh[pousr]_|sk-|xox[baprs]-|AKIA)[A-Za-z0-9_-]{8,}")),
    ("code fence", re.compile(r"```")),
)
OUTCOMES = {"success", "partial", "blocked", "error"}
AGENTS = {"codex", "claude-code"}
OS_VALUES = {"linux", "macos", "windows", "other"}
PROJECT_KINDS = {
    "application", "library", "documentation", "infrastructure",
    "skill-collection", "mixed", "other",
}
EXPECTED = {"automatic", "explicit", "none", "unsure"}
OBSERVED = {"automatic", "explicit", "not-invoked", "wrong-skill"}
SIGNALS = {
    "false-negative-trigger", "false-positive-trigger", "wrong-workflow",
    "manual-install", "manual-update", "manual-configuration", "manual-correction",
    "retry-required", "required-stage-skipped", "stopped-safely",
    "unwanted-change", "unclear-instruction", "no-problem-observed",
}
EVIDENCE_KINDS = {"trigger", "workflow", "verification", "safety", "user-observation"}
EVIDENCE_STATUS = {"passed", "failed", "partial", "not-observed"}
INSTALLATION_SCOPES = {"global", "project", "plugin", "source", "unknown"}
LANGUAGES = {"en", "ru"}
SUBMISSION_TIMEOUT_SECONDS = 60


class FeedbackError(RuntimeError):
    def __init__(self, message: str, category: str = "validation", submission_state: str = "not-attempted"):
        super().__init__(message)
        self.category = category
        self.submission_state = submission_state

    def as_result(self) -> dict[str, Any]:
        return {"schema_version": 1, "error": str(self), "category": self.category,
                "submission_state": self.submission_state,
                "submitted": None if self.submission_state == "unknown" else False,
                "retry_allowed": False}


def member(value: object, choices: set[str]) -> bool:
    return isinstance(value, str) and value in choices


def load_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except (OSError, ValueError) as error:
        raise FeedbackError("cannot read feedback input", "local-io") from error
    if len(raw) > MAX_INPUT_BYTES:
        raise FeedbackError("feedback input exceeds the size limit")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (ValueError, RecursionError) as error:
        raise FeedbackError("feedback input is invalid JSON") from error
    if not isinstance(value, dict):
        raise FeedbackError("feedback input must be a JSON object")
    return value


def exact_object(value: object, required: set[str], optional: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not required.issubset(value) or set(value) - required - optional:
        raise FeedbackError(f"{label} fields do not match the version 1 contract")
    return value


def bounded_text(value: object, label: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise FeedbackError(f"{label} must be non-empty text no longer than {limit} characters")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise FeedbackError(f"{label} contains invalid Unicode text") from error
    normalized = " ".join(value.split())
    for kind, pattern in FORBIDDEN:
        if pattern.search(normalized):
            raise FeedbackError(f"{label} contains a forbidden {kind}")
    return normalized


def validate(value: dict[str, Any]) -> dict[str, Any]:
    required = {"schema_version", "skill", "agent", "environment", "invocation", "outcome", "signals"}
    optional = {"task_summary", "evidence", "unclear", "improvement", "language"}
    exact_object(value, required, optional, "feedback")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise FeedbackError("feedback schema_version must be 1")
    if "language" in value and not member(value["language"], LANGUAGES):
        raise FeedbackError("language is invalid")
    skill = exact_object(value["skill"], {"name", "version"}, {"artifact"}, "skill")
    if not isinstance(skill["name"], str) or not NAME.fullmatch(skill["name"]):
        raise FeedbackError("skill name is invalid")
    if not isinstance(skill["version"], str) or not VERSION.fullmatch(skill["version"]):
        raise FeedbackError("skill version is invalid")
    if "artifact" in skill:
        artifact = exact_object(skill["artifact"], {"installation_scope", "skill_sha256"}, set(), "skill.artifact")
        if not member(artifact["installation_scope"], INSTALLATION_SCOPES):
            raise FeedbackError("installation scope is invalid")
        if not isinstance(artifact["skill_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", artifact["skill_sha256"]):
            raise FeedbackError("skill SHA-256 is invalid")
    agent = exact_object(value["agent"], {"name"}, {"version"}, "agent")
    if not member(agent["name"], AGENTS):
        raise FeedbackError("agent name is invalid")
    if "version" in agent:
        agent["version"] = bounded_text(agent["version"], "agent.version", 80)
    environment = exact_object(
        value["environment"], {"os", "project_kind", "repository_count"}, set(), "environment"
    )
    if not member(environment["os"], OS_VALUES) or not member(environment["project_kind"], PROJECT_KINDS):
        raise FeedbackError("environment classification is invalid")
    count = environment["repository_count"]
    if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= 50:
        raise FeedbackError("repository_count must be an integer from 0 to 50")
    invocation = exact_object(value["invocation"], {"expected", "observed"}, set(), "invocation")
    if not member(invocation["expected"], EXPECTED) or not member(invocation["observed"], OBSERVED):
        raise FeedbackError("invocation classification is invalid")
    if not member(value["outcome"], OUTCOMES):
        raise FeedbackError("outcome is invalid")
    signals = value["signals"]
    if (not isinstance(signals, list) or not all(member(item, SIGNALS) for item in signals)
            or len(signals) != len(set(signals))):
        raise FeedbackError("signals must be a unique list of supported values")
    for key in ("task_summary", "unclear", "improvement"):
        if key in value:
            value[key] = bounded_text(value[key], key, 500)
    evidence = value.get("evidence", [])
    if not isinstance(evidence, list) or len(evidence) > 12:
        raise FeedbackError("evidence must contain at most 12 entries")
    for index, item in enumerate(evidence):
        item = exact_object(item, {"kind", "status", "summary"}, set(), f"evidence[{index}]")
        if not member(item["kind"], EVIDENCE_KINDS) or not member(item["status"], EVIDENCE_STATUS):
            raise FeedbackError(f"evidence[{index}] classification is invalid")
        item["summary"] = bounded_text(item["summary"], f"evidence[{index}].summary", 300)
    return value


def artifact_metadata(root: Path) -> dict[str, Any]:
    """Read only the two declared artifact files; the digest covers SKILL.md bytes."""
    try:
        raw = (root / "SKILL.md").read_bytes()
        if len(raw) > 1_048_576:
            raise FeedbackError("selected SKILL.md exceeds the size limit", "artifact")
        text = raw.decode("utf-8-sig")
    except (OSError, UnicodeDecodeError) as error:
        raise FeedbackError("cannot read selected SKILL.md", "artifact") from error
    frontmatter = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.DOTALL)
    names = re.findall(r"^name:[ \t]*([^\r\n]+?)[ \t]*$", frontmatter.group(1), re.MULTILINE) if frontmatter else []
    name = names[0].strip() if len(names) == 1 else ""
    if len(name) >= 2 and name[0] in "\"'" and name[-1] == name[0]:
        name = name[1:-1]
    metadata = load_json(root / "collection-metadata.json")
    if not NAME.fullmatch(name) or metadata.get("skill") != name:
        raise FeedbackError("selected skill name does not match collection metadata", "artifact")
    version = metadata.get("version")
    if not isinstance(version, str) or not VERSION.fullmatch(version):
        raise FeedbackError("selected collection metadata has no valid version", "artifact")
    return {"name": name, "version": version, "skill_sha256": hashlib.sha256(raw).hexdigest()}


def reporter_provenance() -> dict[str, Any]:
    result: dict[str, Any] = {"name": "report-skill-feedback", "root": "unknown",
                              "version": "unknown", "skill_sha256": "unknown"}
    try:
        root = Path(__file__).resolve().parents[1]
        result["root"] = str(root)
    except (OSError, ValueError, RuntimeError):
        return result
    try:
        metadata = artifact_metadata(root)
        if metadata["name"] == result["name"]:
            result.update(metadata)
    except (OSError, ValueError, RuntimeError):
        # Optional local diagnostics must never hide a confirmed issue URL.
        # RuntimeError includes FeedbackError and JSON recursion failures.
        try:
            result["skill_sha256"] = hashlib.sha256((root / "SKILL.md").read_bytes()).hexdigest()
        except (OSError, ValueError, RuntimeError):
            pass
    return result


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    """A pure questionnaire: do not inspect files, environment, or installations."""
    if not isinstance(args.skill, str) or not NAME.fullmatch(args.skill):
        raise FeedbackError("skill name is invalid")
    if not member(args.language, LANGUAGES):
        raise FeedbackError("language is invalid")
    ru = args.language == "ru"
    result = {
        "schema_version": 1, "operation": "prepare", "skill": args.skill, "language": args.language,
        "collection_consent_required": True, "submission_consent_required": True,
        "checklist": ([
            f"Назовите один предлагаемый отчёт о навыке {args.skill} и согласуйте его состав до сбора данных; этот список не даёт согласия на все категории.",
            "Предложите только нужные для этого отчёта категории: имя и версия навыка, область установки и SHA-256 файла SKILL.md; агент и его версия; ОС, тип проекта и количество репозиториев; ожидаемый и наблюдаемый вызов; результат, сигналы и краткие пересказы наблюдений.",
            "Объясните, что отказ от сбора или отправки отзыва не влияет на выполнение исходной задачи. Получите явное согласие на выбранные категории для этого отчёта.",
            "Укажите точный каталог выбранного навыка и область установки. Каталог остаётся локальным; сведения об артефакте не доказывают его использование в прошлом.",
            "Проверьте каждый краткий пересказ: исключите личные данные, секреты, пути, адреса, ссылки, исходный код, логи и скрытое содержимое проекта; оставьте только одобренные наблюдения.",
            "Объясните, что обезличенный текст не делает отправку анонимной: публикация на GitHub связана с учётной записью отправителя.",
            "Покажите полный черновик и точное назначение kolabse/skills; получите отдельное согласие на отправку именно этого просмотренного отчёта.",
        ] if ru else [
            f"Identify one proposed report about {args.skill} and tailor its categories before collection; this checklist does not grant consent to every category.",
            "Propose only categories needed for this report: skill name and version, installation scope and SKILL.md SHA-256; agent and version; OS, project kind and repository count; expected and observed invocation; outcome, signals and short paraphrases of observations.",
            "Explain that declining collection or submission does not affect the original task. Obtain explicit collection consent for the selected categories of this report.",
            "Select the exact skill directory and installation scope. The directory stays local; artifact provenance does not prove historical use.",
            "Check every paraphrase for privacy: exclude identifying data, secrets, paths, addresses, links, source code, logs and hidden project content; retain only approved observations.",
            "Explain that de-identified text does not make submission anonymous: a GitHub submission remains attributable to the submitting account.",
            "Show the complete draft and exact kolabse/skills destination; obtain separate consent to submit that reviewed report.",
        ]),
        "questions": [
            {"field": "agent", "required": True, "names": sorted(AGENTS)},
            {"field": "environment", "required": True, "os": sorted(OS_VALUES),
             "project_kind": sorted(PROJECT_KINDS), "repository_count": {"minimum": 0, "maximum": 50}},
            {"field": "invocation", "required": True, "expected": sorted(EXPECTED), "observed": sorted(OBSERVED)},
            {"field": "outcome", "required": True, "choices": sorted(OUTCOMES)},
            {"field": "signals", "required": True, "choices": sorted(SIGNALS)},
            {"field": "task_summary", "required": False, "max_length": 500},
            {"field": "evidence", "required": False, "max_items": 12,
             "kind": sorted(EVIDENCE_KINDS), "status": sorted(EVIDENCE_STATUS), "summary_max_length": 300},
            {"field": "unclear", "required": False, "max_length": 500},
            {"field": "improvement", "required": False, "max_length": 500},
        ], "submitted": False, "submission_state": "not-attempted",
    }
    prompts = {
        "agent": ("Which agent was used, and what is its version if known?", "Какой агент использовался и какова его версия, если она известна?"),
        "environment": ("Which OS, project kind, and repository count apply?", "Укажите ОС, тип проекта и количество репозиториев."),
        "invocation": ("How was invocation expected, and what was observed?", "Как ожидался вызов навыка и что наблюдалось?"),
        "outcome": ("What outcome was actually observed?", "Какой результат наблюдался фактически?"),
        "signals": ("Which signals were observed? An empty list is allowed.", "Какие сигналы наблюдались? Допустим пустой список."),
        "task_summary": ("What was the task in de-identified terms?", "Кратко опишите задачу без идентифицирующих данных."),
        "evidence": ("Which approved observations support the report?", "Какие одобренные наблюдения подтверждают отчёт?"),
        "unclear": ("What was unclear?", "Что было непонятно?"),
        "improvement": ("What improvement would help?", "Какое улучшение помогло бы?"),
    }
    for question in result["questions"]:
        question["prompt"] = prompts[question["field"]][1 if ru else 0]
    return result


def build_input(args: argparse.Namespace) -> dict[str, Any]:
    if not args.collection_consent:
        raise FeedbackError("build-input requires --collection-consent for this report", "consent")
    if not member(args.installation_scope, INSTALLATION_SCOPES):
        raise FeedbackError("installation scope is invalid")
    answers = load_json(args.answers)
    exact_object(answers, {"agent", "environment", "invocation", "outcome", "signals"},
                 {"task_summary", "evidence", "unclear", "improvement"}, "answers")
    selected = artifact_metadata(args.skill_root.expanduser())
    skill = {"name": selected["name"], "version": selected["version"],
             "artifact": {"installation_scope": args.installation_scope, "skill_sha256": selected["skill_sha256"]}}
    value = {"schema_version": 1, "skill": skill, **answers}
    if getattr(args, "language", None) is not None:
        value["language"] = args.language
    value = validate(value)
    write_atomic(args.output, json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    return {"schema_version": 1, "operation": "build-input", "input": str(args.output.expanduser().resolve()),
            "observed_skill": {**skill, "root": str(args.skill_root.expanduser().resolve())},
            "reporter": reporter_provenance(), "submitted": False, "submission_state": "not-attempted"}


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def report_id(value: dict[str, Any]) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()[:16]


def render(value: dict[str, Any]) -> str:
    identifier = report_id(value)
    translations = {
        "Context": "Контекст", "Skill version": "Версия навыка", "Agent": "Агент", "OS": "ОС",
        "Project kind": "Тип проекта", "Repository count": "Количество репозиториев",
        "Expected invocation": "Ожидаемый вызов", "Observed invocation": "Наблюдаемый вызов",
        "Outcome": "Результат", "Task summary": "Краткое описание задачи", "Signals": "Сигналы",
        "None reported": "Не указаны", "Observable evidence": "Наблюдаемые свидетельства",
        "What was unclear": "Что было непонятно", "Suggested improvement": "Предлагаемое улучшение",
        "Installation scope": "Область установки", "SKILL.md SHA-256": "SHA-256 файла SKILL.md",
    }
    def t(label: str) -> str:
        return translations.get(label, label) if value.get("language") == "ru" else label

    notice = ("Отчёт подготовлен с явным согласием на сбор данных. Его содержимое обезличено, "
              "но отправка на GitHub остаётся связанной с учётной записью отправителя."
              if value.get("language") == "ru" else
              "This report was prepared with explicit collection consent. Its body is de-identified, "
              "but a GitHub submission remains attributable to the submitting account.")
    lines = [
        f"# Skill feedback: {value['skill']['name']}", "",
        f"Report ID: `{identifier}`", "",
        notice, "", "## " + t("Context"), "",
        f"- {t('Skill version')}: `{value['skill']['version']}`",
        f"- {t('Agent')}: `{value['agent']['name']}`" + (f" (`{value['agent']['version']}`)" if value['agent'].get('version') else ""),
        f"- {t('OS')}: `{value['environment']['os']}`",
        f"- {t('Project kind')}: `{value['environment']['project_kind']}`",
        f"- {t('Repository count')}: `{value['environment']['repository_count']}`",
        f"- {t('Expected invocation')}: `{value['invocation']['expected']}`",
        f"- {t('Observed invocation')}: `{value['invocation']['observed']}`",
        f"- {t('Outcome')}: `{value['outcome']}`", "",
    ]
    if "artifact" in value["skill"]:
        artifact = value["skill"]["artifact"]
        lines.extend([f"- {t('Installation scope')}: `{artifact['installation_scope']}`",
                      f"- {t('SKILL.md SHA-256')}: `{artifact['skill_sha256']}`", ""])
        lines.extend([("Артефакт выбран вызывающей стороной; эти данные не подтверждают его использование в прошлом."
                       if value.get("language") == "ru" else
                       "The artifact is caller-selected; this provenance does not prove a historical invocation."), ""])
    if value.get("task_summary"):
        lines.extend(["## " + t("Task summary"), "", value["task_summary"], ""])
    lines.extend(["## " + t("Signals"), ""])
    lines.extend([f"- `{signal}`" for signal in value["signals"]] or ["- " + t("None reported")])
    lines.append("")
    if value.get("evidence"):
        lines.extend(["## " + t("Observable evidence"), ""])
        lines.extend(
            f"- `{item['kind']}` / `{item['status']}`: {item['summary']}"
            for item in value["evidence"]
        )
        lines.append("")
    if value.get("unclear"):
        lines.extend(["## " + t("What was unclear"), "", value["unclear"], ""])
    if value.get("improvement"):
        lines.extend(["## " + t("Suggested improvement"), "", value["improvement"], ""])
    body = "\n".join(lines)
    seal = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return body + f"<!-- report-skill-feedback:v1 sha256={seal} -->\n"


def default_output(value: dict[str, Any]) -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    return base / "kolabse" / "skill-feedback" / f"{value['skill']['name']}-{report_id(value)}.md"


def write_atomic(path: Path, content: str) -> None:
    try:
        path = path.expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(content, encoding="utf-8", newline="\n")
        temporary.replace(path)
    except OSError as error:
        raise FeedbackError("cannot write local feedback output", "local-io") from error


def validate_report(path: Path) -> tuple[str, str, str]:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise FeedbackError("cannot read report", "local-io") from error
    if len(raw) > MAX_REPORT_BYTES:
        raise FeedbackError("report exceeds the size limit")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise FeedbackError("report is not UTF-8") from error
    match = re.search(r"^# Skill feedback: (?P<skill>[a-z0-9]+(?:-[a-z0-9]+)*)\r?$", text, re.MULTILINE)
    seal = re.search(r"<!-- report-skill-feedback:v1 sha256=(?P<sha>[0-9a-f]{64}) -->\r?\n?$", text)
    report = re.search(r"^Report ID: `(?P<id>[0-9a-f]{16})`\r?$", text, re.MULTILINE)
    if not match or not seal or not report:
        raise FeedbackError("report is not a sealed version 1 feedback draft")
    expected_seal = hashlib.sha256(text[:seal.start()].encode("utf-8")).hexdigest()
    if seal.group("sha") != expected_seal:
        raise FeedbackError("report changed after its reviewed preview")
    for kind, pattern in FORBIDDEN:
        if pattern.search(text):
            raise FeedbackError(f"report contains a forbidden {kind}")
    title = f"Skill feedback: {match.group('skill')} ({report.group('id')})"
    return text, title, report.group("id")


def draft(args: argparse.Namespace) -> dict[str, Any]:
    if not args.collection_consent:
        raise FeedbackError("draft requires --collection-consent for this report", "consent")
    value = validate(load_json(args.input))
    output = args.output or default_output(value)
    content = render(value)
    write_atomic(output, content)
    return {
        "schema_version": 1, "operation": "draft", "report_id": report_id(value),
        "report": str(output.expanduser().resolve()), "submitted": False,
        "preview": content, "reporter": reporter_provenance(), "submission_state": "not-attempted",
    }


def submission_category(stderr: str) -> str:
    """Classify captured diagnostics internally; never include them in output."""
    diagnostic = stderr.lower()
    if any(word in diagnostic for word in ("auth", "login", "credential", "401", "403")):
        return "auth"
    if any(word in diagnostic for word in ("network", "timeout", "timed out", "connection", "dns", "resolve host")):
        return "network"
    if any(word in diagnostic for word in ("500", "502", "503", "504", "service unavailable", "rate limit")):
        return "service"
    if any(word in diagnostic for word in ("422", "404", "rejected", "validation", "disabled", "not found")):
        return "rejected"
    return "unknown"


def submit(args: argparse.Namespace) -> dict[str, Any]:
    if not args.submission_consent:
        raise FeedbackError("submit requires --submission-consent for the reviewed report", "consent")
    report = args.report.expanduser().resolve()
    _text, title, identifier = validate_report(report)
    gh = shutil.which("gh")
    if gh is None:
        raise FeedbackError("GitHub CLI is unavailable; keep the reviewed report for manual submission", "missing-gh")
    try:
        completed = subprocess.run(
            [gh, "issue", "create", "--repo", REPOSITORY, "--title", title, "--body-file", str(report)],
            shell=False, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=SUBMISSION_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise FeedbackError("GitHub submission outcome is unknown; verify it manually before another attempt",
                            "network", "unknown") from error
    except OSError as error:
        raise FeedbackError("GitHub CLI could not be started", "spawn-failed") from error
    if completed.returncode:
        raise FeedbackError("GitHub submission outcome is unknown; verify it manually before another attempt",
                            submission_category(completed.stderr), "unknown")
    url = completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else ""
    if not re.fullmatch(r"https://github\.com/kolabse/skills/issues/[1-9][0-9]*", url):
        raise FeedbackError("GitHub CLI did not return the expected kolabse/skills issue URL; submission outcome is unknown",
                            "unknown", "unknown")
    return {"schema_version": 1, "operation": "submit", "report_id": identifier, "submitted": True,
            "issue_url": url, "reporter": reporter_provenance()}


class FeedbackArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # argparse diagnostics include user-supplied values and option names.
        raise FeedbackError("invalid command arguments; use --help for supported options", "validation")


def parser() -> argparse.ArgumentParser:
    result = FeedbackArgumentParser(description="Prepare and submit de-identified skill feedback.")
    sub = result.add_subparsers(dest="command", required=True)
    status_parser = sub.add_parser("status")
    status_parser.add_argument("--json", action="store_true")
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--skill", required=True)
    prepare_parser.add_argument("--language", choices=sorted(LANGUAGES), default="en")
    prepare_parser.add_argument("--json", action="store_true")
    build_parser = sub.add_parser("build-input")
    build_parser.add_argument("--answers", type=Path, required=True)
    build_parser.add_argument("--skill-root", type=Path, required=True)
    build_parser.add_argument("--installation-scope", choices=sorted(INSTALLATION_SCOPES), required=True)
    build_parser.add_argument("--collection-consent", action="store_true")
    build_parser.add_argument("--output", type=Path, required=True)
    build_parser.add_argument("--language", choices=sorted(LANGUAGES))
    build_parser.add_argument("--json", action="store_true")
    draft_parser = sub.add_parser("draft")
    draft_parser.add_argument("--input", type=Path, required=True)
    draft_parser.add_argument("--output", type=Path)
    draft_parser.add_argument("--collection-consent", action="store_true")
    draft_parser.add_argument("--json", action="store_true")
    submit_parser = sub.add_parser("submit")
    submit_parser.add_argument("--report", type=Path, required=True)
    submit_parser.add_argument("--submission-consent", action="store_true")
    submit_parser.add_argument("--json", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    try:
        args = parser().parse_args(argv)
        if args.command == "status":
            result = {
                "schema_version": 1,
                "skill": "report-skill-feedback",
                "configured": True,
                "collection_consent_required": True,
                "submission_consent_required": True,
                "submission_repository": REPOSITORY,
                "reporter": reporter_provenance(),
            }
        else:
            result = {"prepare": prepare, "build-input": build_input, "draft": draft, "submit": submit}[args.command](args)
        print(json.dumps(result, ensure_ascii=False, indent=2 if args.json else None))
        return 0
    except FeedbackError as error:
        print(json.dumps(error.as_result(), ensure_ascii=False))
        return 1
    except OSError:
        print(json.dumps(FeedbackError("local feedback operation failed", "local-io").as_result()))
        return 1


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
