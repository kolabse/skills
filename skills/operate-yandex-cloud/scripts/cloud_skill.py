from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


CONFIG_RELATIVE_PATH = Path(".agents/operate-yandex-cloud/project.yaml")
LOCAL_CONFIG_RELATIVE_PATH = Path(".agents/operate-yandex-cloud/local.yaml")
LOCAL_IGNORE_RELATIVE_PATH = Path(".agents/operate-yandex-cloud/.gitignore")
ID_PATTERN = re.compile(r"^[a-z0-9-]+$")
IGNORED_DIRECTORIES = {
    ".git",
    ".idea",
    ".terraform",
    ".venv",
    ".vscode",
    "dist",
    "node_modules",
    "vendor",
}


@dataclass(frozen=True)
class ProjectConfig:
    cloud_id: str
    folder_id: str = ""
    yc_profile: str = ""
    version: int = 3


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    returncode: int
    output: str


@dataclass(frozen=True)
class ToolResult:
    name: str
    scope: str
    toolset: str
    purpose: str
    status: str
    version: str
    minimum_version: str
    guidance: str
    install_supported: bool


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    status: str
    detail: str


def validate_identifier(value: str, field_name: str, *, required: bool) -> str:
    normalized = value.strip()
    if not normalized:
        if required:
            raise ValueError(f"{field_name} is required")
        return ""
    if not ID_PATTERN.fullmatch(normalized):
        raise ValueError(
            f"{field_name} must contain only lowercase letters, digits, and hyphens"
        )
    return normalized


def validate_profile(value: str) -> str:
    normalized = value.strip()
    if normalized and not re.fullmatch(r"[A-Za-z0-9._-]+", normalized):
        raise ValueError(
            "yc_profile must contain only letters, digits, dots, underscores, and hyphens"
        )
    return normalized


def config_path(project_path: Path) -> Path:
    return project_path.resolve() / CONFIG_RELATIVE_PATH


def local_config_path(project_path: Path) -> Path:
    return project_path.resolve() / LOCAL_CONFIG_RELATIVE_PATH


def _decode_yaml_scalar(raw_value: str) -> str:
    value = raw_value.strip()
    if value.startswith('"'):
        return str(json.loads(value))
    if value in {"null", "~"}:
        return ""
    return value


def _load_yaml(path: Path, *, required: bool) -> dict[str, str]:
    if not path.is_file():
        if required:
            raise FileNotFoundError(f"Project configuration was not found: {path}")
        return {}

    values: dict[str, str] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.fullmatch(r"([a-z_]+):\s*(.*)", stripped)
        if not match:
            raise ValueError(f"Unsupported YAML at {path}:{line_number}")
        values[match.group(1)] = _decode_yaml_scalar(match.group(2))
    return values


def load_config(project_path: Path) -> ProjectConfig:
    project_values = _load_yaml(config_path(project_path), required=True)
    local_values = _load_yaml(local_config_path(project_path), required=False)
    try:
        version = int(project_values.get("version", "1"))
    except ValueError as error:
        raise ValueError("Project configuration version must be an integer") from error
    if version not in {1, 2, 3}:
        raise ValueError(f"Unsupported project configuration version: {version}")
    yc_profile = local_values.get("yc_profile")
    if yc_profile is None:
        yc_profile = project_values.get("yc_profile", "")

    return ProjectConfig(
        version=version,
        cloud_id=validate_identifier(
            project_values.get("cloud_id", ""), "cloud_id", required=True
        ),
        folder_id=validate_identifier(
            project_values.get("folder_id", ""), "folder_id", required=False
        ),
        yc_profile=validate_profile(yc_profile),
    )


def _ensure_local_config_ignored(project_path: Path) -> Path:
    path = project_path.resolve() / LOCAL_IGNORE_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    rule = "/local.yaml"
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    if rule not in lines:
        lines.append(rule)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path


def save_config(project_path: Path, config: ProjectConfig) -> Path:
    path = config_path(project_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(
        [
            "version: 3",
            f"cloud_id: {json.dumps(config.cloud_id)}",
            f"folder_id: {json.dumps(config.folder_id)}",
            "",
        ]
    )
    path.write_text(content, encoding="utf-8", newline="\n")
    local_path = local_config_path(project_path)
    local_path.write_text(
        "\n".join(
            [
                "version: 1",
                f"yc_profile: {json.dumps(config.yc_profile)}",
                "",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )
    _ensure_local_config_ignored(project_path)
    return path


def configure_project(
    project_path: Path,
    cloud_id: str,
    folder_id: str = "",
    yc_profile: str = "",
) -> ProjectConfig:
    config = ProjectConfig(
        cloud_id=validate_identifier(cloud_id, "cloud_id", required=True),
        folder_id=validate_identifier(folder_id, "folder_id", required=False),
        yc_profile=validate_profile(yc_profile),
    )
    save_config(project_path, config)
    return config


def detect_toolsets(paths: Iterable[Path]) -> set[str]:
    toolsets = {"base"}
    for supplied_path in paths:
        root_path = supplied_path.resolve()
        if not root_path.exists():
            continue
        for current_root, directory_names, file_names in os.walk(root_path):
            directory_names[:] = [
                name for name in directory_names if name not in IGNORED_DIRECTORIES
            ]
            lower_directories = {name.lower() for name in directory_names}
            lower_files = {name.lower() for name in file_names}

            if "ansible" in lower_directories or "ansible.cfg" in lower_files:
                toolsets.add("ansible")
            if "helm" in lower_directories or "chart.yaml" in lower_files:
                toolsets.update({"helm", "kubernetes"})
            if {"kubernetes", "k8s"} & lower_directories:
                toolsets.add("kubernetes")
            if ".gitlab-ci.yml" in lower_files:
                toolsets.add("gitlab")
            if any(name.endswith(".tf") for name in lower_files):
                toolsets.add("terraform")
            if any(name.endswith((".jq", ".yq")) for name in lower_files):
                toolsets.add("data")
            for file_name in file_names:
                if not file_name.lower().endswith((".sh", ".bash", ".ps1", ".py")):
                    continue
                script_path = Path(current_root) / file_name
                try:
                    if script_path.stat().st_size > 262_144:
                        continue
                    script_text = script_path.read_text(
                        encoding="utf-8", errors="replace"
                    )
                except OSError:
                    continue
                if re.search(r"(?<![-\w])(jq|yq)(?![-\w])", script_text):
                    toolsets.add("data")
                    break
    return toolsets


def manifest_path() -> Path:
    return Path(__file__).with_name("tool-manifest.json")


def load_tool_manifest(path: Path | None = None) -> list[dict[str, Any]]:
    manifest = json.loads((path or manifest_path()).read_text(encoding="utf-8"))
    return list(manifest["tools"])


def run_command(command: Sequence[str], *, cwd: Path | None = None) -> CommandResult:
    try:
        completed = subprocess.run(
            list(command),
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return CommandResult(list(command), 127, str(error))
    output = "\n".join(
        part
        for part in [completed.stdout.strip(), completed.stderr.strip()]
        if part
    )
    return CommandResult(list(command), completed.returncode, output)


def extract_version(output: str, pattern: str) -> str:
    match = re.search(pattern, output, flags=re.IGNORECASE | re.MULTILINE)
    return match.group(1) if match else ""


def version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", version))


def version_at_least(actual: str, minimum: str) -> bool:
    actual_parts = version_tuple(actual)
    minimum_parts = version_tuple(minimum)
    size = max(len(actual_parts), len(minimum_parts))
    return actual_parts + (0,) * (size - len(actual_parts)) >= minimum_parts + (0,) * (
        size - len(minimum_parts)
    )


def platform_key() -> str:
    system = platform.system().lower()
    return {"windows": "windows", "darwin": "macos", "linux": "linux"}.get(
        system, system
    )


def install_command(tool: dict[str, Any]) -> list[str] | None:
    installation = tool.get("install", {}).get(platform_key())
    if not installation:
        return None
    executable = installation[0]
    if shutil.which(executable) is None:
        return None
    return list(installation)


def inspect_tools(
    toolsets: set[str],
    *,
    include_all: bool = False,
    runner=run_command,
) -> list[ToolResult]:
    results: list[ToolResult] = []
    for tool in load_tool_manifest():
        active = tool["toolset"] in toolsets
        if not active and not include_all:
            continue
        executable = tool["version_command"][0]
        if shutil.which(executable) is None:
            status = "missing"
            version = ""
        else:
            result = runner(tool["version_command"])
            version = extract_version(result.output, tool["version_regex"])
            if result.returncode != 0:
                status = "error"
            elif not version:
                status = "unknown-version"
            elif not version_at_least(version, tool["minimum_version"]):
                status = "outdated"
            else:
                status = "installed"
        results.append(
            ToolResult(
                name=tool["name"],
                scope="required" if active else "available-workflow",
                toolset=tool["toolset"],
                purpose=tool["purpose"],
                status=status,
                version=version,
                minimum_version=tool["minimum_version"],
                guidance=tool["guidance"],
                install_supported=install_command(tool) is not None,
            )
        )
    return results


def install_tools(names: set[str]) -> list[CommandResult]:
    results: list[CommandResult] = []
    for tool in load_tool_manifest():
        if tool["name"] not in names:
            continue
        command = install_command(tool)
        if command:
            results.append(run_command(command))
    return results


def _active_profile(runner=run_command) -> str:
    result = runner(["yc", "config", "profile", "list"])
    if result.returncode != 0:
        return ""
    for line in result.output.splitlines():
        if line.rstrip().endswith(" ACTIVE"):
            return line.rsplit(" ", 1)[0].strip()
    return ""


def _yc_command(config: ProjectConfig, arguments: Sequence[str]) -> list[str]:
    prefix = ["yc"]
    if config.yc_profile:
        prefix.extend(["--profile", config.yc_profile])
    return prefix + list(arguments)


def _json_output(result: CommandResult) -> Any:
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.output)
    except json.JSONDecodeError:
        return None


def _terraform_workspaces(paths: Iterable[Path]) -> list[tuple[str, str]]:
    workspaces: list[tuple[str, str]] = []
    for supplied_path in paths:
        for environment_file in supplied_path.resolve().glob("**/.terraform/environment"):
            workspace = environment_file.read_text(encoding="utf-8", errors="replace").strip()
            workspaces.append((str(environment_file.parent.parent), workspace or "default"))
    return workspaces


def run_preflight(
    project_path: Path,
    scan_paths: Iterable[Path],
    *,
    runner=run_command,
) -> list[PreflightCheck]:
    checks: list[PreflightCheck] = []
    try:
        config = load_config(project_path)
    except (FileNotFoundError, ValueError) as error:
        return [PreflightCheck("project-config", "fail", str(error))]

    checks.append(
        PreflightCheck(
            "project-config",
            "pass",
            f"cloud_id={config.cloud_id}, folder_id={config.folder_id or '<unset>'}, "
            f"yc_profile={config.yc_profile or '<active>'}",
        )
    )

    if shutil.which("yc") is None:
        checks.append(PreflightCheck("yc-cli", "fail", "yc executable was not found"))
        return checks

    subject_result = runner(_yc_command(config, ["iam", "whoami", "--format", "json"]))
    subject = _json_output(subject_result)
    checks.append(
        PreflightCheck(
            "yc-identity",
            "pass" if subject_result.returncode == 0 and subject else "fail",
            f"authenticated subject {subject}" if subject else subject_result.output,
        )
    )

    cloud_result = runner(
        _yc_command(
            config,
            ["resource-manager", "cloud", "get", "--id", config.cloud_id, "--format", "json"],
        )
    )
    cloud = _json_output(cloud_result)
    checks.append(
        PreflightCheck(
            "cloud-access",
            "pass" if isinstance(cloud, dict) and cloud.get("id") == config.cloud_id else "fail",
            f"cloud {config.cloud_id} is accessible" if cloud else cloud_result.output,
        )
    )

    if config.folder_id:
        folder_result = runner(
            _yc_command(
                config,
                [
                    "resource-manager",
                    "folder",
                    "get",
                    "--id",
                    config.folder_id,
                    "--format",
                    "json",
                ],
            )
        )
        folder = _json_output(folder_result)
        folder_matches = (
            isinstance(folder, dict)
            and folder.get("id") == config.folder_id
            and folder.get("cloud_id") == config.cloud_id
        )
        checks.append(
            PreflightCheck(
                "folder-access",
                "pass" if folder_matches else "fail",
                f"folder {config.folder_id} belongs to cloud {config.cloud_id}"
                if folder_matches
                else folder_result.output or "folder does not belong to configured cloud",
            )
        )

    current_cloud = runner(["yc", "config", "get", "cloud-id"])
    current_folder = runner(["yc", "config", "get", "folder-id"])
    active_profile = _active_profile(runner)
    mismatches = []
    if current_cloud.output.strip() != config.cloud_id:
        mismatches.append(f"global cloud={current_cloud.output.strip() or '<unset>'}")
    if config.folder_id and current_folder.output.strip() != config.folder_id:
        mismatches.append(f"global folder={current_folder.output.strip() or '<unset>'}")
    if config.yc_profile and active_profile != config.yc_profile:
        mismatches.append(f"active profile={active_profile or '<unknown>'}")
    checks.append(
        PreflightCheck(
            "global-yc-context",
            "warn" if mismatches else "pass",
            "; ".join(mismatches) + "; use explicit project IDs for every mutation"
            if mismatches
            else "global yc context matches project configuration",
        )
    )

    resolved_scan_paths = list(scan_paths)
    toolsets = detect_toolsets(resolved_scan_paths)
    if "kubernetes" in toolsets and shutil.which("kubectl"):
        context = runner(["kubectl", "config", "current-context"])
        namespace = runner(
            [
                "kubectl",
                "config",
                "view",
                "--minify",
                "--output",
                "jsonpath={..namespace}",
            ]
        )
        checks.append(
            PreflightCheck(
                "kubernetes-context",
                "pass" if context.returncode == 0 else "warn",
                f"context={context.output.strip()}, "
                f"namespace={namespace.output.strip() or 'default'}",
            )
        )

    if "terraform" in toolsets:
        workspaces = _terraform_workspaces(resolved_scan_paths)
        checks.append(
            PreflightCheck(
                "terraform-workspace",
                "pass" if workspaces else "warn",
                ", ".join(f"{path}={workspace}" for path, workspace in workspaces)
                if workspaces
                else "no initialized Terraform workspace was found",
            )
        )

    if shutil.which("ssh-add"):
        ssh_identity = runner(["ssh-add", "-l"])
        checks.append(
            PreflightCheck(
                "ssh-identity",
                "pass" if ssh_identity.returncode == 0 else "warn",
                ssh_identity.output or "no SSH agent identity was reported",
            )
        )
    return checks


def serializable_results(results: Iterable[Any]) -> list[dict[str, Any]]:
    return [asdict(result) for result in results]
