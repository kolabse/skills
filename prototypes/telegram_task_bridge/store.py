"""Durable task-scoped question/answer state. Answers never grant approval."""

from contextlib import contextmanager
import hashlib
import hmac
import secrets
import sqlite3
import threading
import time


MAX_TEXT = 3500
MAX_TTL = 86400


class Store:
    def __init__(self, path):
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(path), timeout=30, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY, secret_hash TEXT NOT NULL, label TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS questions (
                question_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL REFERENCES tasks(task_id),
                text TEXT NOT NULL, status TEXT NOT NULL,
                expires_at REAL NOT NULL, message_id INTEGER UNIQUE, answer TEXT
            );
            CREATE INDEX IF NOT EXISTS questions_task ON questions(task_id, status);
            CREATE TABLE IF NOT EXISTS updates (update_id INTEGER PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY, offset INTEGER NOT NULL);
            INSERT OR IGNORE INTO state VALUES (1, 0);
        """)

    def close(self):
        with self._lock:
            self._db.close()

    @contextmanager
    def _transaction(self):
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                yield self._db
                self._db.commit()
            except BaseException:
                self._db.rollback()
                raise

    @staticmethod
    def _text(value, limit):
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError(f"text must contain 1..{limit} characters")
        return value

    @staticmethod
    def _integer(value):
        if type(value) is not int or value < 0 or value >= 2**63 - 1:
            raise ValueError("expected a nonnegative 64-bit integer")
        return value

    @staticmethod
    def _authorize(db, task_id, secret):
        if not isinstance(task_id, str) or not isinstance(secret, str):
            raise PermissionError("invalid task credentials")
        row = db.execute("SELECT secret_hash FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        digest = hashlib.sha256(secret.encode()).hexdigest()
        expected = row[0] if row else "0" * 64
        if not hmac.compare_digest(digest, expected) or row is None:
            raise PermissionError("invalid task credentials")

    @staticmethod
    def _expire(db):
        db.execute("UPDATE questions SET status='expired' WHERE status IN ('pending','sent','unknown') AND expires_at<=?", (time.time(),))

    @staticmethod
    def _public(row):
        return {key: row[key] for key in ("question_id", "status", "text", "expires_at", "answer")}

    def register(self, label):
        self._text(label, 120)
        task_id, secret = secrets.token_urlsafe(18), secrets.token_urlsafe(32)
        with self._transaction() as db:
            db.execute("INSERT INTO tasks VALUES (?,?,?)", (task_id, hashlib.sha256(secret.encode()).hexdigest(), label))
        return {"task_id": task_id, "secret": secret}

    def authenticate(self, task_id, secret):
        with self._transaction() as db:
            self._authorize(db, task_id, secret)
        return True

    def task_label(self, task_id, secret):
        with self._transaction() as db:
            self._authorize(db, task_id, secret)
            return db.execute("SELECT label FROM tasks WHERE task_id=?", (task_id,)).fetchone()[0]

    def create_question(self, task_id, secret, text, ttl_seconds=3600):
        self._text(text, MAX_TEXT)
        if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= MAX_TTL:
            raise ValueError(f"ttl_seconds must be an integer in 1..{MAX_TTL}")
        question_id = secrets.token_urlsafe(18)
        with self._transaction() as db:
            self._authorize(db, task_id, secret)
            db.execute("INSERT INTO questions(question_id,task_id,text,status,expires_at) VALUES (?,?,?,'pending',?)", (question_id, task_id, text, time.time() + ttl_seconds))
            return self._public(db.execute("SELECT * FROM questions WHERE question_id=?", (question_id,)).fetchone())

    def mark_sent(self, question_id, message_id):
        self._integer(message_id)
        with self._transaction() as db:
            self._expire(db)
            row = db.execute("SELECT status,message_id FROM questions WHERE question_id=?", (question_id,)).fetchone()
            if row is None:
                raise ValueError("unknown question")
            if row["status"] == "sent" and row["message_id"] == message_id:
                return
            if row["status"] != "pending":
                raise ValueError("question is not pending")
            db.execute("UPDATE questions SET status='sent',message_id=? WHERE question_id=?", (message_id, question_id))

    def mark_failed(self, question_id):
        """Transport errors have unknown delivery outcome; never retry blindly."""
        with self._transaction() as db:
            self._expire(db)
            db.execute("UPDATE questions SET status='unknown' WHERE question_id=? AND status='pending'", (question_id,))

    def receive(self, update_id, reply_message_id, text):
        self._integer(update_id)
        with self._transaction() as db:
            if not db.execute("INSERT OR IGNORE INTO updates VALUES (?)", (update_id,)).rowcount:
                return {"status": "duplicate"}
            self._expire(db)
            if type(reply_message_id) is not int or not 0 <= reply_message_id < 2**63 - 1:
                return {"status": "unknown"}
            row = db.execute("SELECT * FROM questions WHERE message_id=?", (reply_message_id,)).fetchone()
            if row is None:
                return {"status": "unknown"}
            if row["status"] == "expired":
                return {"status": "expired"}
            if row["status"] in ("answered", "acknowledged"):
                return {"status": "already_answered"}
            if row["status"] != "sent":
                return {"status": "unknown"}
            try:
                self._text(text, MAX_TEXT)
            except ValueError:
                return {"status": "invalid_text"}
            db.execute("UPDATE questions SET status='answered',answer=? WHERE question_id=?", (text, row["question_id"]))
            return {"status": "answered", "question_id": row["question_id"], "task_id": row["task_id"]}

    def get_question(self, task_id, secret, question_id):
        with self._transaction() as db:
            self._authorize(db, task_id, secret)
            self._expire(db)
            row = db.execute("SELECT * FROM questions WHERE question_id=? AND task_id=?", (question_id, task_id)).fetchone()
            if row is None:
                raise ValueError("unknown question")
            return self._public(row)

    def poll(self, task_id, secret):
        with self._transaction() as db:
            self._authorize(db, task_id, secret)
            self._expire(db)
            return [self._public(row) for row in db.execute("SELECT * FROM questions WHERE task_id=? AND status='answered' ORDER BY rowid", (task_id,))]

    def ack(self, task_id, secret, question_id):
        with self._transaction() as db:
            self._authorize(db, task_id, secret)
            row = db.execute("SELECT status FROM questions WHERE question_id=? AND task_id=?", (question_id, task_id)).fetchone()
            if row is None:
                raise ValueError("unknown question")
            if row["status"] not in ("answered", "acknowledged"):
                raise ValueError("question has no answer")
            db.execute("UPDATE questions SET status='acknowledged' WHERE question_id=?", (question_id,))

    def offset(self):
        with self._transaction() as db:
            return db.execute("SELECT offset FROM state WHERE id=1").fetchone()[0]

    def advance_offset(self, update_id):
        self._integer(update_id)
        with self._transaction() as db:
            db.execute("UPDATE state SET offset=MAX(offset,?) WHERE id=1", (update_id + 1,))
