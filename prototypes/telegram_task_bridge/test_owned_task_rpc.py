"""Offline subprocess tests: no live app-server, model, or Telegram calls."""

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import sys
import tempfile
import time
import unittest

from owned_task_rpc import AppServer, RpcError


class AppServerTest(unittest.TestCase):
    def server(self, source, **options):
        directory = tempfile.TemporaryDirectory(prefix="owned-rpc-test-")
        self.addCleanup(directory.cleanup)
        fixture = Path(directory.name) / "fixture.py"
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
