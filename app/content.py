"""Content: Posts.

Owns saving, status changes, Link generation, and deletion. Routes ask this
module; they do not touch the database themselves. Any Editor or Admin may do
anything to any Post, so there are no per-Post permission checks here.

Times are stored as UTC ISO strings and shown in US Eastern.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.accounts import connect

EASTERN = ZoneInfo("America/New_York")

SCHEMA = """
create table if not exists posts (
    id integer primary key,
    title text not null,
    link text not null unique,
    body text not null default '',
    status text not null default 'draft' check (status in ('draft', 'published')),
    author_id integer not null references accounts(id),
    created_at text not null,
    updated_at text not null,
    first_published_at text
)
"""

_SELECT = ("select posts.*, accounts.display_name as author from posts"
           " join accounts on accounts.id = posts.author_id")


class EmptyTitle(ValueError):
    """A Post must have a title."""


def now() -> datetime:
    """The current time. Tests replace this to control dates."""
    return datetime.now(timezone.utc)


def _stamp() -> str:
    return now().strftime("%Y-%m-%dT%H:%M:%SZ")


def init_db() -> None:
    with connect() as conn:
        conn.execute(SCHEMA)


def eastern(stamp: str | None) -> str:
    """Show a stored UTC time as US Eastern, e.g. '2026-10-05 14:00'."""
    if not stamp:
        return ""
    when = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return when.astimezone(EASTERN).strftime("%Y-%m-%d %H:%M")


def _slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "post"


def _unique_link(conn: sqlite3.Connection, title: str) -> str:
    base = f"{now().astimezone(EASTERN):%Y-%m-%d}-{_slug(title)}"
    link, n = base, 1
    while conn.execute("select 1 from posts where link = ?", (link,)).fetchone():
        n += 1
        link = f"{base}-{n}"
    return link


def _clean_title(title: str) -> str:
    title = title.strip()
    if not title:
        raise EmptyTitle("A Post needs a title.")
    return title


def list_posts() -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(f"{_SELECT} order by posts.created_at desc, posts.id desc"
                            ).fetchall()


def get_post(post_id: int) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(f"{_SELECT} where posts.id = ?", (post_id,)).fetchone()


def create_post(title: str, body: str, author_id: int) -> int:
    """Save a new Draft. Its Link is made now and never changes."""
    title = _clean_title(title)
    stamp = _stamp()
    with connect() as conn:
        cur = conn.execute(
            "insert into posts (title, link, body, author_id, created_at, updated_at)"
            " values (?, ?, ?, ?, ?, ?)",
            (title, _unique_link(conn, title), body, author_id, stamp, stamp))
        return cur.lastrowid


def update_post(post_id: int, title: str, body: str) -> bool:
    """Change the text of a Post. The Author and the Link stay as they were."""
    title = _clean_title(title)
    with connect() as conn:
        cur = conn.execute("update posts set title = ?, body = ?, updated_at = ?"
                           " where id = ?", (title, body, _stamp(), post_id))
        return cur.rowcount == 1


def set_status(post_id: int, status: str) -> bool:
    """Mark a Post 'published' or 'draft'. First-published time is set once."""
    assert status in ("draft", "published")
    stamp = _stamp()
    with connect() as conn:
        cur = conn.execute(
            "update posts set status = ?, updated_at = ?,"
            " first_published_at = case when ? = 'published' then"
            " coalesce(first_published_at, ?) else first_published_at end"
            " where id = ?", (status, stamp, status, stamp, post_id))
        return cur.rowcount == 1


def delete_post(post_id: int) -> bool:
    with connect() as conn:
        return conn.execute("delete from posts where id = ?", (post_id,)).rowcount == 1


def seed_demo_posts() -> None:
    """Create a Published and a Draft demo Post. Safe to run twice."""
    init_db()
    with connect() as conn:
        if conn.execute("select 1 from posts").fetchone():
            return
        author = conn.execute("select id from accounts where display_name = 'Social Chair'"
                              ).fetchone()
        if author is None:
            return
    published = create_post(
        "Study Hall tonight",
        "Study Hall is **tonight**, 8-10pm in Hayes 311. Bring something to work on.",
        author["id"])
    set_status(published, "published")
    create_post("Snack request form is open",
                "Draft: tell us what snacks you want. Add the form link here.",
                author["id"])
