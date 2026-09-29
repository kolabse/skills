"""Small bounded stdio transport for one bridge-owned app-server process."""

import json
import math
import os
from pathlib import Path
import queue
import subprocess
import threading
import time


class RpcError(RuntimeError):
    """A transport failure, without peer payloads or process diagnostics."""


class AppServer:
    MAX_LINE = 1024 * 1024
    MAX_PENDING = 128

    def __init__(self, command: list[str], cwd: Path, *, write_timeout: float = 10.0):
        if not math.isfinite(write_timeout) or write_timeout <= 0:
            raise ValueError("write_timeout must be finite and positive")
        self.command = list(command)
        self.cwd = cwd
        self.write_timeout = write_timeout
        self.process = None
        self._reader = None
        self._writer = None
        self._messages = queue.Queue(maxsize=self.MAX_PENDING)
        self._finished = threading.Event()
        self._error = None
        self._next_id = 0
        self._write_lock = threading.Lock()
        self._closed = False

    def start(self):
        if self._closed:
            raise RpcError("Transport is closed")
        if self.process is not None:
            return self
        try:
            self.process = subprocess.Popen(
                self.command, cwd=self.cwd, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                shell=False, bufsize=0,
            )
        except (OSError, ValueError):
            raise RpcError("Could not start app-server") from None
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()
        return self

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.close()

    def _read(self):
        try:
            for line in self._lines():
                try:
                    message = json.loads(line)
                except (ValueError, UnicodeError, RecursionError):
                    raise RpcError("Malformed app-server frame") from None
                if not isinstance(message, dict):
                    raise RpcError("App-server frame must be an object")
                try:
                    self._messages.put_nowait(message)
                except queue.Full:
                    raise RpcError("App-server message queue is full") from None
        except (RpcError, OSError, ValueError) as error:
            self._error = (str(error) if isinstance(error, RpcError)
                           else "App-server output failed")
        finally:
            self._finished.set()

    def _lines(self):
        pending = bytearray()
        while not self._closed:
            # Raw pipes avoid buffered-reader locks during bounded shutdown.
            chunk = self.process.stdout.read(min(65536, self.MAX_LINE + 1 - len(pending)))
            if not chunk:
                raise RpcError("Incomplete app-server frame" if pending
                               else "App-server output closed")
            pending.extend(chunk)
            while True:
                end = pending.find(b"\n")
                if end < 0:
                    break
                if end + 1 > self.MAX_LINE:
                    raise RpcError("App-server frame exceeds size limit")
                yield bytes(pending[:end + 1])
                del pending[:end + 1]
            if len(pending) >= self.MAX_LINE:
                raise RpcError("App-server frame exceeds size limit")

    def _write(self, message):
        if self.process is None or self._closed or self._finished.is_set():
            raise RpcError("App-server transport is unavailable")
        try:
            data = (json.dumps(message, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        except (TypeError, ValueError, UnicodeError, RecursionError):
            raise RpcError("Request is not JSON serializable") from None
        if len(data) > self.MAX_LINE:
            raise RpcError("Request exceeds size limit")
        # Anonymous Windows pipes cannot use select() for a write deadline.
        # One worker owns the raw write while the caller retains _write_lock.
        # A timed-out frame may have been partly delivered: retire the entire
        # transport instead of retrying it or allowing another frame to follow.
        completed = threading.Event()
        failed = []
        stream = self.process.stdin

        def write_frame():
            try:
                remaining = memoryview(data)
                while remaining:
                    written = stream.write(remaining)
                    if not written:
                        raise OSError("App-server input failed")
                    remaining = remaining[written:]
                stream.flush()
            except (OSError, ValueError):
                failed.append(True)
            finally:
                completed.set()

        self._writer = threading.Thread(target=write_frame, daemon=True)
        self._writer.start()
        if not completed.wait(self.write_timeout):
            self.close()
            raise RpcError("App-server input write timed out")
        if failed:
            self.close()
            raise RpcError("App-server input failed") from None

    def send(self, method, params=None) -> int:
        with self._write_lock:
            self._next_id += 1
            request_id = self._next_id
            self._write({"jsonrpc": "2.0", "id": request_id,
                         "method": method, "params": params})
            return request_id

    def notify(self, method, params=None):
        with self._write_lock:
            self._write({"jsonrpc": "2.0", "method": method, "params": params})

    def respond(self, request_id, result):
        with self._write_lock:
            self._write({"jsonrpc": "2.0", "id": request_id, "result": result})

    def reject(self, request_id, message="Unsupported request", code=-32601):
        with self._write_lock:
            self._write({"jsonrpc": "2.0", "id": request_id,
                         "error": {"code": code, "message": message}})

    def next_message(self, timeout: float):
        if self.process is None or self._closed:
            raise RpcError("App-server transport is unavailable")
        deadline = time.monotonic() + max(0, timeout)
        while True:
            try:
                return self._messages.get_nowait()
            except queue.Empty:
                if self._finished.is_set():
                    raise RpcError(self._error or "App-server output closed")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            try:
                return self._messages.get(timeout=min(remaining, 0.05))
            except queue.Empty:
                pass

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self.process is None:
            return
        if self.process.poll() is None:
            try:
                self.process.terminate()
            except ProcessLookupError:
                pass
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        for stream in (self.process.stdin, self.process.stdout):
            stream.close()
        if self._reader is not None:
            self._reader.join(timeout=2)
        if self._writer is not None:
            self._writer.join(timeout=2)
