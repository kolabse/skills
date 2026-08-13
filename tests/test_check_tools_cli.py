from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIRECTORY = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "operate-yandex-cloud"
    / "scripts"
)
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPT_DIRECTORY))

import check_tools  # noqa: E402
from cloud_skill import CommandResult, ToolResult  # noqa: E402


def missing_installable_tool() -> ToolResult:
    return ToolResult(
        name="terraform",
        scope="required",
        toolset="terraform",
        purpose="Terraform workflows",
        status="missing",
        version="",
        minimum_version="1.5.0",
        guidance="Install Terraform.",
        install_supported=True,
    )


class CheckToolsCliTests(unittest.TestCase):
    def run_cli(self, *arguments: str, answer: str | None = None) -> tuple[int, str]:
        installed = CommandResult(["package-manager", "install"], 0, "installed")
        input_effect = AssertionError("confirmation prompt was not expected")
        if answer is not None:
            input_effect = None
        with (
            patch.object(check_tools, "detect_toolsets", return_value={"base"}),
            patch.object(
                check_tools,
                "inspect_tools",
                return_value=[missing_installable_tool()],
            ),
            patch.object(
                check_tools,
                "install_tools",
                return_value=[installed],
            ) as install_mock,
            patch("builtins.input", return_value=answer, side_effect=input_effect),
            redirect_stdout(io.StringIO()) as output,
        ):
            result = check_tools.main(["--project-path", ".", *arguments])
        self.install_mock = install_mock
        return result, output.getvalue()

    def test_non_interactive_check_never_installs_implicitly(self) -> None:
        result, output = self.run_cli("--non-interactive")

        self.assertEqual(1, result)
        self.assertIn("terraform", output)
        self.install_mock.assert_not_called()

    def test_declined_confirmation_does_not_install(self) -> None:
        result, _ = self.run_cli(answer="n")

        self.assertEqual(1, result)
        self.install_mock.assert_not_called()

    def test_explicit_install_flag_is_required_for_unattended_install(self) -> None:
        result, output = self.run_cli("--install-missing", "--non-interactive")

        self.assertEqual(1, result)
        self.assertIn("Tool installation finished", output)
        self.install_mock.assert_called_once_with({"terraform"})


if __name__ == "__main__":
    unittest.main()
