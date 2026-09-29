import unittest
import json
import tempfile
import time
import sys
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import Mock, patch

from owned_task import TaskError, TaskCancelled, TelegramChannel, run_task, main
from owned_task_report import RunReport
from store import Store


def question(**changes):
    params = {"threadId": "owned", "turnId": "turn", "callId": "call",
              "tool": "askTelegram", "arguments": {"question": "Word?"}}
    params.update(changes)
    return {"id": "server-1", "method": "item/tool/call", "params": params}


def completed(status="completed"):
    return {"method": "turn/completed", "params": {
        "threadId": "owned", "turn": {"id": "turn", "status": status}}}


FINAL = {"method": "item/completed", "params": {"threadId": "owned", "turnId": "turn",
         "item": {"type": "agentMessage", "phase": "final_answer", "text": "Done"}}}


class RPC:
    def __init__(self, events):
        self.events = list(events)
        self.responses = []
        self.rejected = []
        self.sent = []
        self.setup = []

    def send(self, method, params):
        self.sent.append((method, params))
        request_id = len(self.sent)
        results = {"initialize": {}, "thread/start": {
            "thread": {"id": "owned"}, "approvalPolicy": "never", "sandbox": {"type": "readOnly"}},
            "turn/start": {"turn": {"id": "turn"}}}
        if method in results:
            self.setup.append({"id": request_id, "result": results[method]})
        return request_id

    def notify(self, method):
        pass

    def next_message(self, timeout):
        if timeout == 0 and not self.responses and self.events and self.events[0] is FINAL:
            return None
        return self.setup.pop(0) if self.setup else self.events.pop(0) if self.events else None

    def respond(self, request_id, result):
        self.responses.append((request_id, result))

    def reject(self, request_id, message):
        self.rejected.append(request_id)


class Channel:
    def __init__(self, reply="blue"):
        self.reply = reply
        self.asked = []
        self.acked = False
        self.finished = []

    def ask(self, text, ttl, *, checkpoint=lambda: None):
        checkpoint()
        self.asked.append(text)

    def poll(self):
        return self.reply

    def acknowledge(self):
        self.acked = True

    def finish(self, text):
        self.finished.append(text)


class OwnedTaskTests(unittest.TestCase):
    def test_user_cancel_before_start_has_no_external_actions(self):
        rpc, channel = RPC([]), Channel()
        with self.assertRaises(TaskCancelled):
            run_task(rpc, channel, Path.cwd(), is_cancelled=lambda: True)
        self.assertFalse(rpc.sent)
        self.assertFalse(channel.asked)

    def test_user_cancel_at_dispatch_stops_reply_and_owned_turn(self):
        rpc, channel = RPC([question(), None]), Channel()
        canceled = [False]
        def phase(value):
            if value == "dispatching_reply":
                canceled[0] = True
        with self.assertRaises(TaskCancelled):
            run_task(rpc, channel, Path.cwd(), on_phase=phase,
                     is_cancelled=lambda: canceled[0])
        self.assertFalse(rpc.responses)
        self.assertFalse(channel.acked)
        self.assertEqual(rpc.sent[-1][0], "turn/interrupt")

    def test_user_cancel_after_turn_completion_prevents_final_send(self):
        rpc, channel = RPC([question(), None, None, FINAL, completed()]), Channel()
        canceled = [False]
        def phase(value):
            if value == "sending_result":
                canceled[0] = True
        with self.assertRaises(TaskCancelled):
            run_task(rpc, channel, Path.cwd(), on_phase=phase,
                     is_cancelled=lambda: canceled[0])
        self.assertTrue(channel.acked)
        self.assertFalse(channel.finished)

    def run_scenario(self, rpc, channel):
        ticks = iter(range(1000))
        return run_task(rpc, channel, Path.cwd(), timeout=100, clock=lambda: next(ticks))

    def test_reply_continues_matching_turn_and_sends_result(self):
        rpc, channel = RPC([question(), None, None, FINAL, completed()]), Channel()
        result = self.run_scenario(rpc, channel)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(rpc.responses, [("server-1", {
            "contentItems": [{"type": "inputText", "text": "blue"}], "success": True})])
        self.assertTrue(channel.acked)
        self.assertEqual(channel.finished, ["Done"])

    def test_foreign_or_approval_requests_never_dispatch_reply(self):
        for event in [question(threadId="desktop"), question(turnId="other"),
                      question(tool="shell"), question(namespace="other"),
                      {"id": 0, "method": "item/permissions/requestApproval", "params": {}}]:
            with self.subTest(event=event):
                rpc, channel = RPC([event]), Channel()
                with self.assertRaises(TaskError):
                    self.run_scenario(rpc, channel)
                self.assertFalse(rpc.responses)
                self.assertFalse(channel.asked)
                self.assertEqual(rpc.rejected, [event["id"]])

    def test_canceled_question_never_consumes_late_reply(self):
        canceled = {"method": "serverRequest/resolved", "params": {
            "threadId": "owned", "requestId": "server-1"}}
        rpc, channel = RPC([question(), canceled]), Channel("already available")
        with self.assertRaisesRegex(TaskError, "canceled"):
            self.run_scenario(rpc, channel)
        self.assertFalse(rpc.responses)
        self.assertFalse(channel.acked)

    def test_failed_or_premature_completion_never_sends_result(self):
        for events in [[FINAL, completed()], [question(), FINAL, completed("failed")],
                       [question(), question(), FINAL, completed()]]:
            rpc, channel = RPC(events), Channel()
            with self.assertRaises(TaskError):
                self.run_scenario(rpc, channel)
            self.assertFalse(channel.finished)

    def test_timeout_interrupts_only_owned_turn(self):
        rpc, channel = RPC([question()]), Channel(None)
        with self.assertRaisesRegex(TaskError, "deadline"):
            self.run_scenario(rpc, channel)
        self.assertEqual(rpc.sent[-1], ("turn/interrupt", {"threadId": "owned", "turnId": "turn"}))
        self.assertFalse(channel.acked)

    def test_uncertain_write_is_not_acknowledged_or_retried(self):
        rpc, channel = RPC([question()]), Channel()
        def fail(request_id, result):
            raise OSError("write outcome unknown")
        rpc.respond = fail
        with self.assertRaises(OSError):
            self.run_scenario(rpc, channel)
        self.assertFalse(channel.acked)
        self.assertFalse(channel.finished)

    def test_cancellation_arriving_during_poll_prevents_dispatch(self):
        rpc, channel = RPC([question(), None]), Channel()
        def poll():
            rpc.events.append({"method": "serverRequest/resolved", "params": {
                "threadId": "owned", "requestId": "server-1"}})
            return "blue"
        channel.poll = poll
        with self.assertRaisesRegex(TaskError, "canceled"):
            self.run_scenario(rpc, channel)
        self.assertFalse(rpc.responses)
        self.assertFalse(channel.acked)

    def test_deadline_checked_after_blocking_poll(self):
        rpc, channel = RPC([question(), None]), Channel()
        now = [0]
        def poll():
            now[0] = 101
            return "too late"
        channel.poll = poll
        with self.assertRaisesRegex(TaskError, "deadline"):
            run_task(rpc, channel, Path.cwd(), timeout=100, clock=lambda: now[0])
        self.assertFalse(rpc.responses)
        self.assertFalse(channel.acked)

    def test_report_save_cannot_bypass_deadline_or_cancellation(self):
        for cancel in (True, False):
            with self.subTest(cancel=cancel):
                rpc, channel = RPC([question(), None]), Channel()
                now = [0]
                def phase(value):
                    if value == "dispatching_reply":
                        if cancel:
                            rpc.events.append({"method": "serverRequest/resolved", "params": {
                                "threadId": "owned", "requestId": "server-1"}})
                        else:
                            now[0] = 101
                with self.assertRaises(TaskError):
                    run_task(rpc, channel, Path.cwd(), timeout=100,
                             clock=lambda: now[0], on_phase=phase)
                self.assertFalse(rpc.responses)
                self.assertFalse(channel.acked)


class ReportTests(unittest.TestCase):
    def test_main_finishes_cancellation_notice_before_terminal_report(self):
        executable = Path(self.temp.name) / "codex.exe"
        executable.touch()
        scratch = Path(self.temp.name) / "scratch"
        scratch.mkdir()
        channel = Mock()
        def cancel():
            data = json.loads(self.path.read_text())
            self.assertEqual(data["phase"], "cancelling")
            self.assertEqual(data["status"], "running")
            return "edit_failed"
        channel.cancel_question.side_effect = cancel
        argv = ["owned_task.py", "--live", "--codex-executable", str(executable),
                "--workdir", str(scratch), "--report", str(self.path), "--database", "db", "--config", "config"]
        with patch.object(sys, "argv", argv), patch("owned_task.TelegramChannel", return_value=channel), \
                patch("owned_task.AppServer", return_value=nullcontext(object())), \
                patch("owned_task.run_task", side_effect=TaskCancelled("cancel")):
            self.assertEqual(main(), 130)
        data = json.loads(self.path.read_text())
        self.assertEqual(data["status"], "interrupted")
        self.assertEqual(data["cancellation_notice"], "edit_failed")
        channel.close.assert_called_once()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "result.json"

    def test_progress_survives_failed_atomic_replace_and_refuses_replay(self):
        report = RunReport(self.path)
        report.phase("dispatching_reply")
        previous = self.path.read_bytes()
        with patch("owned_task_report.os.replace", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                report.phase("reply_dispatched")
        self.assertEqual(self.path.read_bytes(), previous)
        self.assertFalse(json.loads(previous)["reply_dispatched"])
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])
        with self.assertRaises(FileExistsError):
            RunReport(self.path)

    def test_success_report_contains_no_message_contents(self):
        report = RunReport(self.path)
        rpc, channel = RPC([question(), None, None, FINAL, completed()]), Channel("private reply")
        run_task(rpc, channel, Path.cwd(), on_phase=report.phase)
        data = json.loads(self.path.read_text())
        self.assertEqual(data["status"], "completed")
        self.assertTrue(data["turn_completed"])
        self.assertTrue(data["reply_dispatched"])
        self.assertTrue(data["result_sent"])
        self.assertNotIn("private reply", self.path.read_text())

    def test_result_send_failure_keeps_completed_turn_without_claiming_delivery(self):
        report = RunReport(self.path)
        rpc, channel = RPC([question(), None, None, FINAL, completed()]), Channel()
        channel.finish = Mock(side_effect=OSError("unknown delivery"))
        with self.assertRaises(OSError):
            run_task(rpc, channel, Path.cwd(), on_phase=report.phase)
        report.stop()
        data = json.loads(self.path.read_text())
        self.assertEqual(data["status"], "failed")
        self.assertEqual(data["phase"], "sending_result")
        self.assertTrue(data["turn_completed"])
        self.assertFalse(data["result_sent"])
        channel.finish.assert_called_once()

    def test_report_failure_prevents_question_send(self):
        rpc, channel = RPC([question()]), Channel()
        def phase(value):
            if value == "sending_question":
                raise OSError("disk full")
        with self.assertRaises(OSError):
            run_task(rpc, channel, Path.cwd(), on_phase=phase)
        self.assertFalse(channel.asked)


class TelegramChannelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "live.sqlite3"
        Store(self.db).close()
        Path(str(self.db) + ".receiver-health.json").write_text(json.dumps({
            "state": "ready", "updated_at": time.time()}))
        self.telegram = Mock(chat_id=123)
        self.telegram.preflight.return_value = 456
        self.telegram.send.return_value = 789
        for name, value in [("Telegram", Mock(return_value=self.telegram)),
                            ("bind_bot_database", Mock()),
                            ("receiver_lock", Mock(side_effect=lambda *a, **kw: nullcontext()))]:
            patcher = patch("owned_task." + name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def channel(self):
        channel = TelegramChannel(self.db, "unused-config")
        self.addCleanup(channel.close)
        return channel

    def test_real_store_exact_reply_and_ack(self):
        channel = self.channel()
        channel.ask("Question", 60)
        self.assertIsNone(channel.poll())
        self.assertEqual(channel.store.receive(1, 111, "wrong")["status"], "unknown")
        self.assertIsNone(channel.poll())
        channel.store.receive(2, 789, "blue")
        self.assertEqual(channel.poll(), "blue")
        channel.acknowledge()
        self.assertIsNone(channel.poll())
        channel.finish("Done")
        self.assertFalse(self.telegram.send.call_args.kwargs["force_reply"])

    def test_uncertain_send_stays_unknown_without_retry(self):
        channel = self.channel()
        self.telegram.send.side_effect = OSError("secret diagnostic")
        with self.assertRaisesRegex(TaskError, "uncertain"):
            channel.ask("Question", 60)
        state = channel.store.get_question(**channel.credentials, question_id=channel.question)
        self.assertEqual(state["status"], "unknown")
        self.assertEqual(self.telegram.send.call_count, 1)

    def test_cancel_after_delivery_lock_prevents_send(self):
        channel = self.channel()
        def checkpoint():
            raise TaskCancelled("Canceled while waiting for delivery lock")
        with self.assertRaises(TaskCancelled):
            channel.ask("Question", 60, checkpoint=checkpoint)
        self.telegram.send.assert_not_called()

    def test_cancel_closes_reply_before_edit_and_edits_once(self):
        channel = self.channel()
        channel.ask("Question", 60)
        self.assertFalse(self.telegram.send.call_args.kwargs["force_reply"])
        def edit(message_id):
            self.assertEqual(message_id, 789)
            self.assertEqual(channel.store.receive(4, 789, "late")["status"], "cancelled")
        self.telegram.mark_obsolete.side_effect = edit
        self.assertEqual(channel.cancel_question(), "updated")
        self.assertEqual(channel.cancel_question(), "not_needed")
        self.telegram.mark_obsolete.assert_called_once()
        self.assertEqual(channel.store.poll(**channel.credentials), [])

    def test_edit_failure_does_not_reopen_question_or_retry(self):
        channel = self.channel()
        channel.ask("Question", 60)
        self.telegram.mark_obsolete.side_effect = OSError("unavailable")
        self.assertEqual(channel.cancel_question(), "edit_failed")
        self.assertEqual(channel.store.receive(5, 789, "late")["status"], "cancelled")
        self.assertEqual(channel.cancel_question(), "not_needed")
        self.telegram.mark_obsolete.assert_called_once()

    def test_cancel_discards_unconsumed_answer(self):
        channel = self.channel()
        channel.ask("Question", 60)
        channel.store.receive(6, 789, "unused")
        channel.cancel_question()
        self.assertEqual(channel.store.poll(**channel.credentials), [])
        self.assertIsNone(channel.store.get_question(**channel.credentials, question_id=channel.question)["answer"])

    def test_cancel_preserves_already_consumed_answer(self):
        channel = self.channel()
        channel.ask("Question", 60)
        channel.store.receive(7, 789, "consumed")
        channel.acknowledge()
        self.assertEqual(channel.cancel_question(), "not_needed")
        self.telegram.mark_obsolete.assert_not_called()
        self.assertEqual(channel.store.get_question(**channel.credentials, question_id=channel.question)["status"], "acknowledged")

    def test_paused_receiver_prevents_network_calls(self):
        (self.db.parent / "receiver-paused").touch()
        with self.assertRaises(TaskError):
            self.channel()
        self.telegram.preflight.assert_not_called()


if __name__ == "__main__":
    unittest.main()
