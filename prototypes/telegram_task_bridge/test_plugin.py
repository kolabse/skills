import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from build_plugin import build, FILES


class PluginTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows lifecycle wrapper')
    def test_serve_forwards_client_identity_and_shared_paths(self):
        for agent in (None, 'codex', 'claude-code'):
            with self.subTest(agent=agent), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                controller = root / 'plugin_control.ps1'
                shutil.copyfile(Path(__file__).with_name('plugin_control.ps1'), controller)
                # A private pause marker bypasses scheduler access in the bootstrap.
                (root / 'receiver-paused').touch()
                config = root / 'config.json'
                config.write_text('{}')
                database = root / 'shared.sqlite3'
                fake_server = root / 'server.py'
                fake_server.write_text('import json, sys; print(json.dumps(sys.argv[1:]))')
                command = ['powershell.exe', '-NoProfile', '-NonInteractive', '-File',
                           str(controller), 'serve', '-PythonPath', sys.executable,
                           '-ServerPath', str(fake_server), '-DatabasePath', str(database),
                           '-ConfigPath', str(config)]
                if agent is not None:
                    command += ['-Agent', agent]
                result = subprocess.run(command, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout),
                                 ['serve', '--db', str(database), '--config', str(config),
                                  '--agent', agent or 'codex'])
                self.assertIn('paused', result.stderr)

    def test_build_from_fresh_checkout_and_refuse_unrelated_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'telegram-task-bridge'
            build(root)
            self.assertEqual(json.loads((root / '.codex-plugin/plugin.json').read_text())['version'], '0.1.0')
            self.assertTrue((root / 'LICENSE').is_file())
            other = Path(folder) / 'unrelated'
            other.mkdir()
            (other / 'keep.txt').write_text('preserve')
            with self.assertRaises(ValueError):
                build(other)
            self.assertEqual((other / 'keep.txt').read_text(), 'preserve')

    @unittest.skipUnless(os.name == 'nt', 'Windows lifecycle wrapper')
    def test_explicit_resume_clears_pause_before_launch_and_restores_on_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            shutil.copyfile(Path(__file__).with_name('plugin_control.ps1'), root / 'plugin_control.ps1')
            marker = root / 'codex/telegram-task-bridge/receiver-paused'
            marker.parent.mkdir(parents=True)
            marker.touch()
            (root / 'manage_receiver.ps1').write_text('''param($Action,$PythonPath,$ServerPath,$DatabasePath,$ConfigPath)
if (Test-Path (Join-Path $env:LOCALAPPDATA 'codex/telegram-task-bridge/receiver-paused')) { exit 2 }
[IO.File]::WriteAllText((Join-Path $PSScriptRoot 'attempted'), 'pause was cleared')
exit 1
''')
            result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-File',
                                     str(root / 'plugin_control.ps1'), 'start'],
                                    env=dict(os.environ, LOCALAPPDATA=str(root)), capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 1)
            self.assertTrue((root / 'attempted').exists())
            self.assertTrue(marker.exists())

    def test_bundle_contains_only_runtime_and_no_host_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / '.codex-plugin').mkdir()
            (root / 'hooks').mkdir()
            (root / 'scripts').mkdir()
            (root / 'hooks/hooks.json').write_text('{"hooks": {"SessionStart": []}}')
            (root / 'scripts/session_start.ps1').write_text('# old generated hook')
            (root / '.codex-plugin/plugin.json').write_text(json.dumps({
                'name': 'telegram-task-bridge', 'interface': {}}))
            build(root)
            self.assertEqual({p.name for p in (root / 'scripts/runtime').iterdir()}, set(FILES))
            self.assertFalse((root / 'hooks/hooks.json').exists())
            self.assertFalse((root / 'scripts/session_start.ps1').exists())
            self.assertNotIn(str(Path.home()), (root / '.mcp.json').read_text())

    @unittest.skipUnless(os.name == 'nt', 'Windows lifecycle wrapper')
    def test_mcp_bootstrap_respects_pause_failure_and_single_receiver(self):
        cases = [
            ({'installed': False}, False, False, 'setup_needed'),
            ({'installed': True, 'scheduler_state': 'Ready', 'health': None,
              'health_error': None, 'last_task_result': 267011}, False, True, 'starting'),
            ({'installed': True, 'scheduler_state': 'Ready', 'health': {'state': 'failed'},
              'health_error': None, 'last_task_result': 1}, False, False, 'manual_start_needed'),
            ({'installed': True, 'scheduler_state': 'Running', 'receiver_state': 'ready'}, False, False, 'ready'),
            ({}, True, False, 'paused'),
        ]
        for status, paused, should_start, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                shutil.copyfile(Path(__file__).with_name('plugin_control.ps1'), root / 'plugin_control.ps1')
                (root / 'status.json').write_text(json.dumps(status))
                (root / 'manage_receiver.ps1').write_text('''param($Action,$PythonPath,$ServerPath,$DatabasePath,$ConfigPath)
if ($Action -eq 'start') { [IO.File]::WriteAllText((Join-Path $PSScriptRoot 'started'), 'yes') }
Get-Content (Join-Path $PSScriptRoot 'status.json') -Raw
exit 0
''')
                if paused:
                    marker = root / 'codex/telegram-task-bridge/receiver-paused'
                    marker.parent.mkdir(parents=True)
                    marker.touch()
                env = dict(os.environ, LOCALAPPDATA=str(root))
                result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-File',
                                         str(root / 'plugin_control.ps1'), 'ensure'], env=env,
                                        capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)
                output = json.loads(result.stdout)
                self.assertIn(expected, json.dumps(output))
                self.assertEqual((root / 'started').exists(), should_start)
                # Exercise the actual MCP launcher path: bootstrap diagnostics
                # must stay off stdout, including pause and permanent failure.
                fake_server = root / 'server.py'
                fake_server.write_text('print("MCP_STDOUT_ONLY")')
                result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-File',
                                         str(root / 'plugin_control.ps1'), 'serve',
                                         '-PythonPath', sys.executable, '-ServerPath', str(fake_server),
                                         '-ConfigPath', str(root / 'status.json')], env=env,
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), 'MCP_STDOUT_ONLY')
                self.assertIn(expected, result.stderr)


if __name__ == '__main__':
    unittest.main()
