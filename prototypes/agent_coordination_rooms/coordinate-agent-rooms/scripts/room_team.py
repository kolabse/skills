"""One-time bearer invitations and renewable credentials for one private room."""
import re
import secrets
import time

import room


SESSION_MINUTES = 60
CREDENTIAL_SECONDS = 7 * 24 * 60 * 60
MODE = "team"
SCHEMA = (
    """CREATE TABLE IF NOT EXISTS room_team_invites (
        digest TEXT PRIMARY KEY, actor TEXT NOT NULL UNIQUE REFERENCES members(id) ON DELETE CASCADE,
        expires_at INTEGER NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS room_team_credentials (
        digest TEXT PRIMARY KEY, actor TEXT NOT NULL UNIQUE REFERENCES members(id) ON DELETE CASCADE,
        expires_at INTEGER NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS room_team_retired (actor TEXT PRIMARY KEY)""",
)


class TeamAccessError(Exception):
    pass


def install(db):
    for statement in SCHEMA:
        db.execute(statement)


def issue_invite(db, actor, minutes):
    if not 1 <= minutes <= 1440:
        raise ValueError("invitation lifetime must be between 1 and 1440 minutes")
    room.member(db, actor)
    if db.execute("SELECT 1 FROM room_team_retired WHERE actor=?", (actor,)).fetchone():
        raise room.RoomError("use a new participant ID for an invitation after revocation")
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    db.execute("DELETE FROM room_team_invites WHERE expires_at <= ? OR actor = ?", (now, actor))
    db.execute("INSERT INTO room_team_invites VALUES (?, ?, ?)", (room.token_digest(token), actor, now + minutes * 60))
    return token


def payload_digest(payload, field):
    if payload.keys() != {field}:
        raise ValueError(f"expected only {field}")
    value = payload[field]
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", value):
        raise TeamAccessError("invalid or expired team access secret")
    return room.token_digest(value)


def join(db, payload):
    digest = payload_digest(payload, "invite")
    now = int(time.time())
    invite = db.execute("SELECT actor FROM room_team_invites WHERE digest = ? AND expires_at > ?",
                        (digest, now)).fetchone()
    if invite is None:
        raise TeamAccessError("invalid or expired team access secret")
    actor = invite["actor"]
    credential = secrets.token_urlsafe(32)
    db.execute("DELETE FROM room_team_invites WHERE digest = ?", (digest,))
    db.execute("""INSERT INTO room_team_credentials VALUES (?, ?, ?)
        ON CONFLICT(actor) DO UPDATE SET digest = excluded.digest, expires_at = excluded.expires_at""",
               (room.token_digest(credential), actor, now + CREDENTIAL_SECONDS))
    room.membership_event(db, actor, "invitation_redeemed")
    return {"actor": actor, "credential": credential, "token": room.mint_token(db, actor, SESSION_MINUTES, MODE)}


def renew(db, payload):
    digest = payload_digest(payload, "credential")
    current = db.execute("SELECT actor FROM room_team_credentials WHERE digest = ? AND expires_at > ?",
                         (digest, int(time.time()))).fetchone()
    if current is None:
        raise TeamAccessError("invalid or expired team access secret")
    actor = current["actor"]
    return {"actor": actor, "token": room.mint_token(db, actor, SESSION_MINUTES, MODE)}
