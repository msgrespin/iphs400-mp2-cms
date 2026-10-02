"""Accounts and sessions.

An Account belongs to a Position, not a person (ADR-003). This module stores
Accounts, hashes passwords with argon2, verifies a sign-in, and exposes the
guard routes use for "must be signed in". Passwords are never logged or stored
in plain text.
"""
from __future__ import annotations

import secrets
import sqlite3
from contextlib import contextmanager
from typing import Iterator

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request

from app import settings

_hasher = PasswordHasher()
# Verified against when the email is unknown, so both failures take similar time.
_DUMMY_HASH = _hasher.hash("not-a-real-password")

SCHEMA = """
create table if not exists accounts (
    id integer primary key,
    email text not null unique,
    display_name text not null,
    password_hash text not null,
    role text not null check (role in ('admin', 'editor')),
    active integer not null default 1,
    created_at text not null default (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
)
"""

# Position, email, role, which demo password it uses.
DEMO_ACCOUNTS = [
    ("Co-VP", "admin@example.test", "admin", "admin"),
    ("Social Chair", "editor@example.test", "editor", "editor"),
    ("Co-President", "copresident@example.test", "editor", "editor"),
    ("Treasurer", "treasurer@example.test", "editor", "editor"),
]


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(settings.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.execute(SCHEMA)


class AccountProblem(Exception):
    """An Accounts action was refused; the message says why, in plain words."""


class NotFound(AccountProblem):
    pass


ROLES = ("admin", "editor")
LAST_ADMIN = "That is the last active Admin. Make another Account an active Admin first."


def create_account(email: str, display_name: str, password: str, role: str) -> None:
    email, display_name = email.strip().lower(), display_name.strip()
    if not (email and display_name and password):
        raise AccountProblem("Position name, email, and password are all required.")
    if role not in ROLES:
        raise AccountProblem("Role must be Admin or Editor.")
    with connect() as conn:
        if conn.execute("select 1 from accounts where email = ?", (email,)).fetchone():
            raise AccountProblem(f"An Account with the email {email} already exists.")
        try:
            conn.execute(
                "insert into accounts (email, display_name, password_hash, role)"
                " values (?, ?, ?, ?)",
                (email, display_name, _hasher.hash(password), role))
        except sqlite3.IntegrityError:  # another request created it just now
            raise AccountProblem(f"An Account with the email {email} already exists.")


def list_accounts() -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute("select * from accounts order by id").fetchall()


def _target(conn: sqlite3.Connection, account_id: int) -> sqlite3.Row:
    try:
        account = conn.execute("select * from accounts where id = ?", (account_id,)).fetchone()
    except OverflowError:  # an id too big for SQLite cannot exist
        account = None
    if account is None:
        raise NotFound("No such Account.")
    return account


def _other_active_admins(conn: sqlite3.Connection, account_id: int) -> int:
    return conn.execute("select count(*) from accounts"
                        " where role = 'admin' and active = 1 and id != ?",
                        (account_id,)).fetchone()[0]


def set_role(account_id: int, role: str) -> sqlite3.Row:
    if role not in ROLES:
        raise AccountProblem("Role must be Admin or Editor.")
    with connect() as conn:
        conn.execute("begin immediate")  # hold the write lock from the check to the update
        account = _target(conn, account_id)
        if (role != "admin" and account["role"] == "admin" and account["active"]
                and not _other_active_admins(conn, account_id)):
            raise AccountProblem(LAST_ADMIN)
        conn.execute("update accounts set role = ? where id = ?", (role, account_id))
        return account


def set_password(account_id: int, password: str) -> sqlite3.Row:
    if not password:
        raise AccountProblem("A new password is required.")
    with connect() as conn:
        account = _target(conn, account_id)
        conn.execute("update accounts set password_hash = ? where id = ?",
                     (_hasher.hash(password), account_id))
        return account


def deactivate(account_id: int) -> sqlite3.Row:
    """Accounts are deactivated, never deleted, so their Posts stay on the site."""
    with connect() as conn:
        conn.execute("begin immediate")  # hold the write lock from the check to the update
        account = _target(conn, account_id)
        if (account["role"] == "admin" and account["active"]
                and not _other_active_admins(conn, account_id)):
            raise AccountProblem(LAST_ADMIN)
        conn.execute("update accounts set active = 0 where id = ?", (account_id,))
        return account


def reactivate(account_id: int) -> sqlite3.Row:
    with connect() as conn:
        account = _target(conn, account_id)
        conn.execute("update accounts set active = 1 where id = ?", (account_id,))
        return account


def seed_demo_accounts(admin_password: str, editor_password: str) -> None:
    """Create the four demo Accounts. Safe to run twice."""
    hashes = {"admin": _hasher.hash(admin_password),
              "editor": _hasher.hash(editor_password)}
    init_db()
    with connect() as conn:
        for display_name, email, role, pw_key in DEMO_ACCOUNTS:
            exists = conn.execute("select 1 from accounts where email = ?",
                                  (email,)).fetchone()
            if not exists:
                conn.execute(
                    "insert into accounts (email, display_name, password_hash, role)"
                    " values (?, ?, ?, ?)",
                    (email, display_name, hashes[pw_key], role))


def set_active(email: str, active: bool) -> None:
    with connect() as conn:
        conn.execute("update accounts set active = ? where email = ?",
                     (int(active), email))


def authenticate(email: str, password: str) -> sqlite3.Row | None:
    """Return the active Account for these credentials, or None."""
    with connect() as conn:
        account = conn.execute("select * from accounts where email = ?",
                               (email.strip().lower(),)).fetchone()
    stored = account["password_hash"] if account else _DUMMY_HASH
    try:
        ok = _hasher.verify(stored, password)
    except (VerificationError, InvalidHashError):
        ok = False
    return account if (ok and account and account["active"]) else None


def get_account(account_id: int) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute("select * from accounts where id = ? and active = 1",
                            (account_id,)).fetchone()


# --- sessions and CSRF -----------------------------------------------------

def sign_in(request: Request, account: sqlite3.Row) -> None:
    request.session.clear()  # new session on sign-in, with a fresh CSRF token
    request.session["account_id"] = account["id"]
    request.session["csrf"] = secrets.token_urlsafe(32)


def sign_out(request: Request) -> None:
    request.session.clear()


def csrf_token(request: Request) -> str:
    token = request.session.get("csrf")
    if not token:
        token = request.session["csrf"] = secrets.token_urlsafe(32)
    return token


async def require_csrf(request: Request) -> None:
    """Dependency for every state-changing route: reject a missing or bad token."""
    form = await request.form()
    sent = str(form.get("csrf_token", ""))
    expected = request.session.get("csrf", "")
    if not expected or not secrets.compare_digest(sent, expected):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token.")


class NoPermission(Exception):
    """A signed-in Account asked for something its Role may not do."""


def require_account(request: Request) -> sqlite3.Row:
    """Guard: must be signed in. Anonymous requests go to the sign-in screen."""
    account_id = request.session.get("account_id")
    account = get_account(account_id) if account_id else None
    if account is None:
        request.session.pop("account_id", None)
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return account


def require_admin(account: sqlite3.Row = Depends(require_account)) -> sqlite3.Row:
    """Guard: must be an Admin. A signed-in Editor gets the "no permission" screen."""
    if account["role"] != "admin":
        raise NoPermission()
    return account
