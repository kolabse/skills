"""Execute only the explicitly supported, project-scoped Compute operations.

Membership checks are point-in-time observations, not an IAM fence. Callers
must use suitable folder-scoped IAM and avoid concurrent resource moves.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

from cloud_skill import config_path, load_config, local_config_path


IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9-]{0,49}\Z")
OPERATIONS = {"list", "get", "start", "stop", "restart"}
MUTATIONS = {"start": "RUNNING", "stop": "STOPPED", "restart": "RUNNING"}
STATUSES = {"STATUS_UNSPECIFIED", "PROVISIONING", "RUNNING", "STOPPING", "STOPPED",
            "STARTING", "RESTARTING", "UPDATING", "ERROR", "CRASHED", "DELETING"}
USAGE = "yc_project.py --project-path PATH -- compute instance {list|get|start|stop|restart} [--id ID]"


class OperationError(RuntimeError):
    """Contains only safe, fixed messages and validated resource identifiers."""

    def __init__(self, phase: str, message: str, *, exit_code: int = 1,
                 context: dict[str, Any] | None = None):
        super().__init__(message)
        self.phase = phase
        self.exit_code = exit_code
        self.context = dict(context or {})

    def as_dict(self) -> dict[str, Any]:
        return {**self.context, "status": "unverified" if self.context.get("mutation_attempted") else "blocked",
                "phase": self.phase, "message": str(self), "exit_code": self.exit_code}


def valid_id(value: Any) -> bool:
    return isinstance(value, str) and IDENTIFIER.fullmatch(value) is not None


def parse_operation(arguments: Sequence[str]) -> tuple[str, str]:
    if (not isinstance(arguments, (list, tuple)) or not all(isinstance(value, str) for value in arguments)
            or len(arguments) < 3 or list(arguments[:2]) != ["compute", "instance"]
            or arguments[2] not in OPERATIONS):
        raise OperationError("arguments", "Unsupported operation; use the documented Compute instance grammar.", exit_code=2)
    action = arguments[2]
    if action == "list" and len(arguments) == 3:
        return action, ""
    if action != "list" and len(arguments) == 5 and arguments[3] == "--id" and valid_id(arguments[4]):
        return action, arguments[4]
    raise OperationError("arguments", "List accepts no arguments; other operations require only --id and an ID of at most 50 characters.", exit_code=2)


def configuration_snapshot(project: Path):
    def read_inputs():
        shared = config_path(project).read_bytes()
        try:
            local = local_config_path(project).read_bytes()
        except FileNotFoundError:
            local = None
        return shared, local

    try:
        before = read_inputs()
        config = load_config(project)
        if before != read_inputs():
            raise OperationError("configuration", "Project configuration changed while being read.")
        if not valid_id(config.cloud_id) or not valid_id(config.folder_id):
            raise OperationError("configuration", "Configure valid cloud_id and folder_id before running project operations.")
        if not config.yc_profile:
            raise OperationError("configuration", "Configure yc_profile in local.yaml or the supported project configuration before running operations.")
        return config, before
    except OperationError:
        raise
    except (OSError, ValueError, UnicodeError):
        raise OperationError("configuration", "Project configuration is missing, unreadable, or invalid; configure the project first.") from None


def decode_json(output: str) -> Any:
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result
    return json.loads(output, object_pairs_hook=unique_object)


def run_operation(project_path: Path, arguments: Sequence[str], *, runner=None) -> dict[str, Any]:
    action, target_id = parse_operation(arguments)  # Reject all overrides before filesystem or CLI work.
    context: dict[str, Any] = {"operation": f"compute instance {action}", "target_id": target_id,
                               "mutation_attempted": False}
    phase = "configuration"
    try:
        project = project_path.resolve()
        snapshot = configuration_snapshot(project)
        config = snapshot[0]
        context.update(cloud_id=config.cloud_id, folder_id=config.folder_id)
        phase = "executable"
        environment = dict(os.environ)
        discovered = shutil.which("yc", path=environment.get("PATH", ""))
        if not discovered:
            raise OperationError(phase, "yc executable was not found; install the CLI before running operations.")
        executable = Path(discovered).resolve(strict=True)
        if not executable.is_file():
            raise OperationError(phase, "yc executable is unavailable.")
        original_stat = executable.stat()
        executable_identity = (original_stat.st_dev, original_stat.st_ino, original_stat.st_size, original_stat.st_mtime_ns)
        scoped = [str(executable), f"--profile={config.yc_profile}", f"--cloud-id={config.cloud_id}",
                  f"--folder-id={config.folder_id}", "--format=json", "--no-browser"]
        execute = runner or subprocess.run

        def unchanged_configuration():
            if snapshot != configuration_snapshot(project):
                raise OperationError("configuration", "Project configuration changed during the operation; start a fresh invocation.")

        def call(tokens: list[str], current_phase: str, *, mutation: bool = False, subject: bool = False):
            nonlocal phase
            phase = current_phase
            current_stat = executable.stat()
            if executable_identity != (current_stat.st_dev, current_stat.st_ino, current_stat.st_size, current_stat.st_mtime_ns):
                raise OperationError(phase, "The yc executable changed during the operation; start a fresh invocation.")
            if mutation:
                context["mutation_attempted"] = True
            try:
                result = execute([*scoped, *tokens], cwd=project, env=dict(environment),
                                 stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8",
                                 errors="replace", timeout=600 if mutation else 30, check=False)
            except subprocess.TimeoutExpired:
                raise OperationError(phase, "yc timed out; inspect the target before retrying an attempted mutation.", exit_code=124) from None
            except OSError:
                raise OperationError(phase, "yc could not be executed.", exit_code=127) from None
            if type(result.returncode) is not int or result.returncode != 0:
                code = result.returncode if type(result.returncode) is int and result.returncode else 1
                raise OperationError(phase, "yc failed; no raw CLI output is included in this summary.", exit_code=code)
            if mutation:
                # Native synchronous actions need not return an instance body.
                # Discard their output and establish state with a fresh get.
                return None
            if not isinstance(result.stdout, str):
                raise OperationError(phase, "yc returned an invalid response.")
            try:
                return decode_json(result.stdout)
            except (ValueError, TypeError):
                # whoami also supports the documented single subject ID on STDOUT.
                if subject and valid_id(result.stdout.strip()):
                    return result.stdout.strip()
                raise OperationError(phase, "yc returned invalid or ambiguous JSON.") from None

        def instance(value: Any, *, requested: str = "") -> dict[str, str]:
            if (not isinstance(value, dict) or not valid_id(value.get("id"))
                    or value.get("folder_id") != config.folder_id
                    or (requested and value["id"] != requested)
                    or not isinstance(value.get("status"), str) or value["status"] not in STATUSES):
                raise OperationError(phase, "Instance identity, folder membership, or status could not be verified.")
            return {"id": value["id"], "folder_id": config.folder_id, "status": value["status"]}

        subject = call(["iam", "whoami"], "identity", subject=True)
        subject_id = subject.get("id") if isinstance(subject, dict) else subject
        if not valid_id(subject_id):
            raise OperationError(phase, "Authenticated subject could not be verified.")
        cloud = call(["resource-manager", "cloud", "get", "--id", config.cloud_id], "cloud")
        if not isinstance(cloud, dict) or cloud.get("id") != config.cloud_id:
            raise OperationError(phase, "Configured cloud identity could not be verified.")
        folder = call(["resource-manager", "folder", "get", "--id", config.folder_id], "folder")
        if not isinstance(folder, dict) or folder.get("id") != config.folder_id or folder.get("cloud_id") != config.cloud_id:
            raise OperationError(phase, "Configured folder ownership could not be verified.")
        unchanged_configuration()
        if action == "list":
            response = call(["compute", "instance", "list"], "list")
            if not isinstance(response, list):
                raise OperationError(phase, "yc returned an invalid instance list.")
            instances = [instance(item) for item in response]
            if len({item["id"] for item in instances}) != len(instances):
                raise OperationError(phase, "yc returned duplicate instance identities.")
        else:
            target = ["compute", "instance", "get", "--id", target_id]
            observed = instance(call(target, "target"), requested=target_id)
            instances = [observed]
            if action in MUTATIONS:
                unchanged_configuration()
                call(["compute", "instance", action, "--id", target_id], "action", mutation=True)
                observed = instance(call(target, "postverify"), requested=target_id)
                if observed["status"] != MUTATIONS[action]:
                    raise OperationError(phase, "Mutation was attempted, but the expected instance state was not observed.")
                instances = [observed]
        unchanged_configuration()
        return {**context, "status": "verified", "phase": "complete", "instances": instances, "exit_code": 0}
    except OperationError as error:
        error.context = context
        raise
    except Exception:
        raise OperationError(phase, "Operation could not be verified; inspect the configured target before retrying.",
                             context=context) from None


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments == ["--help"]:
        print(USAGE)
        return 0
    try:
        if len(arguments) < 4 or arguments[0] != "--project-path" or arguments[2] != "--" or not arguments[1]:
            raise OperationError("arguments", "Use --project-path PATH followed by -- and the documented operation.", exit_code=2)
        result = run_operation(Path(arguments[1]), arguments[3:])
        print(json.dumps(result, sort_keys=True))
        return 0
    except OperationError as error:
        print(json.dumps(error.as_dict(), sort_keys=True))
        return error.exit_code
    except Exception:
        print(json.dumps({"status": "blocked", "phase": "arguments", "exit_code": 1,
                          "message": "Operation arguments could not be processed."}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
