"""Offline subprocess tests: no live app-server, model, or Telegram calls."""

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import os
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from owned_task_rpc import AppServer, RpcError


def assert_fixture_stopped(server):
    """Do not let filesystem retries conceal a failed transport shutdown."""
    if server is None:
        return
    if server.process is not None and server.process.poll() is None:
        raise AssertionError("Owned fixture process is still running")
    for worker in (server._reader, server._writer):
        if worker is not None and worker.is_alive():
            raise AssertionError("Owned fixture worker is still running")


def cleanup_owned_fixture(directory, owned_path, stopped_probe, *,
                          windows=os.name == "nt", clock=time.monotonic,
                          sleep=time.sleep):
    """Retry only transient Windows sharing locks on this fixture's temp dir."""
    target = Path(directory.name).resolve()
    if (target != Path(owned_path).resolve()
            or target.parent != Path(tempfile.gettempdir()).resolve()
            or not target.name.startswith("owned-rpc-test-")):
        raise ValueError("Cleanup target is not the owned fixture temp directory")
    deadline = clock() + 1.0
    for attempt in range(21):
        stopped_probe()
        try:
            directory.cleanup()
            return
        except OSError as error:
            if (not windows or getattr(error, "winerror", None) != 32
                    or attempt == 20 or clock() >= deadline):
                raise
            sleep(min(0.05, max(0.0, deadline - clock())))


class FixtureCleanupTest(unittest.TestCase):
    def setUp(self):
        self.path = Path(tempfile.gettempdir()).resolve() / "owned-rpc-test-fake"
        self.directory = SimpleNamespace(name=str(self.path), cleanup=Mock())
        self.probe = Mock()
        self.now = 0.0
        self.sleeps = []

    def sleep(self, delay):
        self.sleeps.append(delay)
        self.now += delay

    def cleanup(self, **options):
        cleanup_owned_fixture(self.directory, self.path, self.probe,
                              windows=True, clock=lambda: self.now,
                              sleep=self.sleep, **options)

    def error(self, winerror):
        error = PermissionError("fixture cleanup failed")
        error.winerror = winerror
        return error

    def test_sharing_violation_retries_after_shutdown_probe(self):
        events = []
        self.probe.side_effect = lambda: events.append("stopped")
        def attempt():
            events.append("cleanup")
            if events.count("cleanup") == 1:
                raise self.error(32)
        self.directory.cleanup.side_effect = attempt
        self.cleanup()
        self.assertEqual(events, ["stopped", "cleanup", "stopped", "cleanup"])
        self.assertEqual(self.sleeps, [0.05])

    def test_exhausted_sharing_violation_is_raised_even_if_clock_stalls(self):
        error = self.error(32)
        self.directory.cleanup.side_effect = error
        with self.assertRaises(PermissionError) as raised:
            cleanup_owned_fixture(self.directory, self.path, self.probe,
                                  windows=True, clock=lambda: 0.0,
                                  sleep=self.sleeps.append)
        self.assertIs(raised.exception, error)
        self.assertEqual(self.directory.cleanup.call_count, 21)
        self.assertEqual(len(self.sleeps), 20)

    def test_deadline_stops_retries(self):
        self.directory.cleanup.side_effect = self.error(32)
        def sleep(delay):
            self.sleeps.append(delay)
            self.now += 2
        with self.assertRaises(PermissionError):
            cleanup_owned_fixture(self.directory, self.path, self.probe,
                                  windows=True, clock=lambda: self.now, sleep=sleep)
        self.assertEqual(self.directory.cleanup.call_count, 2)
        self.assertEqual(len(self.sleeps), 1)

    def test_other_errors_and_nonwindows_sharing_errors_are_immediate(self):
        for windows, code in ((True, 5), (True, None), (False, 32)):
            with self.subTest(windows=windows, code=code):
                self.directory.cleanup.reset_mock()
                error = self.error(code)
                self.directory.cleanup.side_effect = error
                with self.assertRaises(PermissionError) as raised:
                    cleanup_owned_fixture(self.directory, self.path, self.probe,
                                          windows=windows, sleep=self.sleep)
                self.assertIs(raised.exception, error)
                self.directory.cleanup.assert_called_once_with()
        self.assertEqual(self.sleeps, [])

    def test_live_owned_child_or_thread_prevents_cleanup(self):
        for process, reader, writer in ((None, False, False), (0, True, False),
                                        (0, False, True)):
            with self.subTest(process=process, reader=reader, writer=writer):
                server = SimpleNamespace(
                    process=SimpleNamespace(poll=lambda: process),
                    _reader=SimpleNamespace(is_alive=lambda: reader),
                    _writer=SimpleNamespace(is_alive=lambda: writer))
                with self.assertRaises(AssertionError):
                    cleanup_owned_fixture(self.directory, self.path,
                                          lambda: assert_fixture_stopped(server))
                self.directory.cleanup.assert_not_called()

    def test_unsafe_or_mismatched_directory_is_rejected(self):
        for path in (self.path.parent, self.path.parent / "unowned",
                     self.path / "owned-rpc-test-nested"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                cleanup_owned_fixture(self.directory, path, self.probe)
        self.directory.cleanup.assert_not_called()
        self.probe.assert_not_called()


class AppServerTest(unittest.TestCase):
    def server(self, source, **options):
        directory = tempfile.TemporaryDirectory(prefix="owned-rpc-test-")
        owned_path = Path(directory.name).resolve()
        server = None
        self.addCleanup(cleanup_owned_fixture, directory, owned_path,
                        lambda: assert_fixture_stopped(server))
        fixture = owned_path / "fixture.py"
        fixture.write_text(source, encoding="utf-8")
        server = AppServer([sys.executable, "-u", str(fixture)], Path(directory.name), **options)
        self.addCleanup(server.close)
        return server

    def test_initialize_ids_notification_and_response_ids(self):
        source = '''import json, sys
def read(): return json.loads(sys.stdin.readline())
def send(value): print(json.dumps(value), flush=True)
request = read()
send({"id": request["id"], "result": {"method": request["method"]}})
send({"id": "server-007", "method": "approval/request"})
send({"method": "echo", "params": read()})
send({"method": "echo", "params": read()})
send({"method": "echo", "params": read()})
send({"method": "echo", "params": read()})
sys.stdin.read()
'''
        with self.server(source) as server:
            first = server.send("initialize", {"clientInfo": {"name": "offline"}})
            self.assertEqual(server.next_message(3), {
                "id": first, "result": {"method": "initialize"}})
            request = server.next_message(3)
            server.respond(request["id"], {"ok": True})
            self.assertEqual(server.next_message(3)["params"]["id"], "server-007")
            server.reject(0)
            rejection = server.next_message(3)["params"]
            self.assertEqual(rejection["id"], 0)
            self.assertEqual(rejection["error"], {
                "code": -32601, "message": "Unsupported request"})
            server.notify("initialized")
            self.assertNotIn("id", server.next_message(3)["params"])
            second = server.send("thread/start")
            self.assertEqual(second, first + 1)
            self.assertEqual(server.next_message(3)["params"]["id"], second)

    def test_malformed_nonobject_partial_and_eof_are_errors(self):
        for payload in (b"not json\n", b"[]\n", b"{}", b""):
            with self.subTest(payload=payload):
                source = f"import sys\nsys.stdout.buffer.write({payload!r})\nsys.stdout.flush()\n"
                with self.server(source) as server:
                    with self.assertRaises(RpcError):
                        server.next_message(3)

    def test_timeout_then_receive(self):
        with self.server('import time\ntime.sleep(0.3)\nprint(\'{"result": "late"}\', flush=True)\n') as server:
            self.assertIsNone(server.next_message(0.01))
            self.assertEqual(server.next_message(3), {"result": "late"})
            with self.assertRaises(RpcError):
                server.next_message(3)

    def test_overlong_unterminated_frame_fails_without_waiting_for_eof(self):
        source = f"import sys, time\nsys.stdout.buffer.write(b'x' * {AppServer.MAX_LINE + 1})\nsys.stdout.flush()\ntime.sleep(30)\n"
        with self.server(source) as server:
            with self.assertRaisesRegex(RpcError, "size limit"):
                server.next_message(3)

    def test_bounded_queue_fails_on_flood(self):
        source = "import sys, time\nsys.stdout.write('{}\\n' * 500)\nsys.stdout.flush()\ntime.sleep(30)\n"
        with self.server(source) as server:
            self.assertTrue(server._finished.wait(3))
            self.assertLessEqual(server._messages.qsize(), server.MAX_PENDING)
            for _ in range(server.MAX_PENDING):
                self.assertEqual(server.next_message(0), {})
            with self.assertRaisesRegex(RpcError, "queue is full"):
                server.next_message(0)

    def test_context_cleans_up_process_and_pipes_even_on_error(self):
        server = self.server("import time\ntime.sleep(30)\n")
        with self.assertRaisesRegex(ValueError, "test failure"):
            with server:
                process = server.process
                self.assertIsNone(process.poll())
                raise ValueError("test failure")
        self.assertIsNotNone(process.poll())
        self.assertTrue(process.stdin.closed)
        self.assertTrue(process.stdout.closed)
        self.assertFalse(server._reader.is_alive())
        server.close()

    def test_write_timeout_retires_transport_and_cleans_up(self):
        source = 'import time\nprint(\'{"ready": true}\', flush=True)\ntime.sleep(30)\n'
        server = self.server(source, write_timeout=0.15)
        with server:
            self.assertEqual(server.next_message(3), {"ready": True})
            started = time.monotonic()
            # Larger than the OS pipe capacity, smaller than the frame limit.
            with self.assertRaisesRegex(RpcError, "write timed out"):
                server.send("blocked", {"payload": "x" * (AppServer.MAX_LINE // 2)})
            self.assertLess(time.monotonic() - started, 5)
            self.assertIsNotNone(server.process.poll())
            self.assertTrue(server.process.stdin.closed)
            self.assertTrue(server.process.stdout.closed)
            self.assertFalse(server._writer.is_alive())
            self.assertFalse(server._reader.is_alive())
            for operation in (lambda: server.send("retry"),
                              lambda: server.notify("retry"),
                              lambda: server.respond(1, {}),
                              lambda: server.reject(1), server.start):
                with self.assertRaises(RpcError):
                    operation()

    def test_concurrent_writes_are_complete_serial_frames(self):
        source = '''import json, sys
for line in sys.stdin:
    value = json.loads(line)
    print(json.dumps({"id": value["id"], "length": len(value["params"])}), flush=True)
'''
        with self.server(source) as server:
            with ThreadPoolExecutor(max_workers=4) as workers:
                ids = list(workers.map(lambda _: server.send("echo", "x" * 20000), range(12)))
            replies = [server.next_message(3) for _ in ids]
            self.assertEqual(sorted(ids), list(range(1, 13)))
            self.assertEqual([reply["id"] for reply in replies], list(range(1, 13)))
            self.assertTrue(all(reply["length"] == 20000 for reply in replies))

    def test_waiting_writer_fails_after_first_writer_times_out(self):
        source = 'import time\nprint(\'{"ready": true}\', flush=True)\ntime.sleep(30)\n'
        with self.server(source, write_timeout=0.15) as server:
            self.assertEqual(server.next_message(3), {"ready": True})
            with ThreadPoolExecutor(max_workers=2) as workers:
                pending = [workers.submit(server.send, "blocked", "x" * 524288)
                           for _ in range(2)]
                failures = []
                for future in pending:
                    with self.assertRaises(RpcError) as failure:
                        future.result(timeout=5)
                    failures.append(str(failure.exception))
            self.assertCountEqual(failures, ["App-server input write timed out",
                                            "App-server transport is unavailable"])

    def test_invalid_write_timeout_is_rejected(self):
        for timeout in (0, -1, float("nan"), float("inf")):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                AppServer([], Path.cwd(), write_timeout=timeout)


if __name__ == "__main__":
    unittest.main()
