"""Content: Posts and Pages.

Owns saving, status changes, Link generation, and deletion. Routes ask this
module; they do not touch the database themselves. Any Editor or Admin may do
anything to any Post, so there are no per-Post permission checks here. Pages
differ: only an Admin changes a Page's title, and Home is protected for everyone.

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

PAGE_SCHEMA = """
create table if not exists pages (
    id integer primary key,
    title text not null,
    link text not null unique,
    body text not null default '',
    status text not null default 'draft' check (status in ('draft', 'published')),
    is_home integer not null default 0,
    created_at text not null,
    updated_at text not null,
    first_published_at text
)
"""

HOME_BODY = ("Study Hall is every Monday, 8-10pm in Hayes 311. "
             "All are welcome, and there are free snacks.")

_SELECT = ("select posts.*, accounts.display_name as author from posts"
           " join accounts on accounts.id = posts.author_id")


class EmptyTitle(ValueError):
    """A Post or Page must have a title."""


class HomeProtected(ValueError):
    """Home can never be deleted or set to Draft, by anyone."""


def now() -> datetime:
    """The current time. Tests replace this to control dates."""
    return datetime.now(timezone.utc)


def _stamp() -> str:
    return now().strftime("%Y-%m-%dT%H:%M:%SZ")


def init_db() -> None:
    """Create the tables, and Home if it is missing, so the site always has a front page."""
    with connect() as conn:
        conn.execute(SCHEMA)
        conn.execute(PAGE_SCHEMA)
        if not conn.execute("select 1 from pages where is_home = 1").fetchone():
            stamp = _stamp()
            # "index" is the Link because Home is written to index.html.
            conn.execute(
                "insert into pages (title, link, body, status, is_home, created_at,"
                " updated_at, first_published_at) values ('Home', ?, ?, 'published', 1,"
                " ?, ?, ?)", (_unique_link_in(conn, "pages", "index"), HOME_BODY,
                              stamp, stamp, stamp))


def eastern(stamp: str | None) -> str:
    """Show a stored UTC time as US Eastern, e.g. '2026-10-05 14:00'."""
    if not stamp:
        return ""
    when = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return when.astimezone(EASTERN).strftime("%Y-%m-%d %H:%M")


def public_date(stamp: str) -> str:
    """Show a stored UTC time as a Visitor sees it, e.g. 'Monday, October 5, 2026'."""
    when = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    when = when.astimezone(EASTERN)
    return f"{when:%A, %B} {when.day}, {when.year}"


def _slug(title: str, fallback: str = "post") -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or fallback


def _unique_link_in(conn: sqlite3.Connection, table: str, base: str) -> str:
    link, n = base, 1
    while conn.execute(f"select 1 from {table} where link = ?", (link,)).fetchone():
        n += 1
        link = f"{base}-{n}"
    return link


def _unique_link(conn: sqlite3.Connection, title: str) -> str:
    return _unique_link_in(
        conn, "posts", f"{now().astimezone(EASTERN):%Y-%m-%d}-{_slug(title)}")


def _clean_title(title: str, message: str = "A Post needs a title.") -> str:
    title = title.strip()
    if not title:
        raise EmptyTitle(message)
    return title


def list_posts() -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(f"{_SELECT} order by posts.created_at desc, posts.id desc"
                            ).fetchall()


def published_posts() -> list[sqlite3.Row]:
    """Published Posts, latest first by first-published time. No Author is selected."""
    init_db()
    with connect() as conn:
        return conn.execute(
            "select title, link, body, first_published_at from posts"
            " where status = 'published'"
            " order by first_published_at desc, id desc").fetchall()


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


# --- Pages -----------------------------------------------------------------

def list_pages() -> list[sqlite3.Row]:
    """Every Page, Home first, then in the order they were created."""
    init_db()
    with connect() as conn:
        return conn.execute("select * from pages order by is_home desc, created_at, id"
                            ).fetchall()


def published_pages() -> list[sqlite3.Row]:
    """Published Pages in navigation order: Home first, then by creation."""
    return [page for page in list_pages() if page["status"] == "published"]


def get_page(page_id: int) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute("select * from pages where id = ?", (page_id,)).fetchone()


def home_page() -> sqlite3.Row:
    init_db()
    with connect() as conn:
        return conn.execute("select * from pages where is_home = 1").fetchone()


def create_page(title: str, body: str) -> int:
    """Save a new Draft Page. Its Link is made from the title now and never changes."""
    title = _clean_title(title, "A Page needs a title.")
    stamp = _stamp()
    with connect() as conn:
        cur = conn.execute(
            "insert into pages (title, link, body, created_at, updated_at)"
            " values (?, ?, ?, ?, ?)",
            (title, _unique_link_in(conn, "pages", _slug(title, "page")), body, stamp, stamp))
        return cur.lastrowid


def update_page(account, page_id: int, title: str, body: str) -> bool:
    """Change a Page's text. Only an Admin's title is kept; an Editor changes the body."""
    with connect() as conn:
        if account["role"] == "admin":
            title = _clean_title(title, "A Page needs a title.")
            cur = conn.execute("update pages set title = ?, body = ?, updated_at = ?"
                               " where id = ?", (title, body, _stamp(), page_id))
        else:
            cur = conn.execute("update pages set body = ?, updated_at = ? where id = ?",
                               (body, _stamp(), page_id))
        return cur.rowcount == 1


def set_page_status(page_id: int, status: str) -> bool:
    """Mark a Page 'published' or 'draft'. Home cannot go back to Draft."""
    assert status in ("draft", "published")
    page = get_page(page_id)
    if page is not None and page["is_home"] and status == "draft":
        raise HomeProtected("Home cannot be set to Draft.")
    stamp = _stamp()
    with connect() as conn:
        cur = conn.execute(
            "update pages set status = ?, updated_at = ?,"
            " first_published_at = case when ? = 'published' then"
            " coalesce(first_published_at, ?) else first_published_at end"
            " where id = ?", (status, stamp, status, stamp, page_id))
        return cur.rowcount == 1


def delete_page(page_id: int) -> bool:
    page = get_page(page_id)
    if page is not None and page["is_home"]:
        raise HomeProtected("Home cannot be deleted.")
    with connect() as conn:
        return conn.execute("delete from pages where id = ?", (page_id,)).rowcount == 1


def seed_demo_pages() -> None:
    """Create About and Join & Snacks as Published Pages (Home already exists).

    Safe to run twice: a Page that is already there is left alone.
    """
    init_db()
    demo = [("About", "AWM at Kenyon holds a weekly Study Hall. Officers: Co-VP, "
                      "Co-President, Social Chair, and Treasurer."),
            ("Join & Snacks", "Fill out the Google Form to join or to request snacks. "
                              "Add the form link here.")]
    for title, body in demo:
        with connect() as conn:
            if conn.execute("select 1 from pages where title = ?", (title,)).fetchone():
                continue
        set_page_status(create_page(title, body), "published")


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
        "Hello everybody!\n\n"
        "We are CURRENTLY having our study hall tonight from 8-10 in Hayes 311. "
        "All are welcome and we will have lots of free snacks!\n\n"
        "Come and say hi!\n\n"
        "\\- AWM &lt;3",
        author["id"])
    set_status(published, "published")
    create_post("Snack request form is open",
                "Draft: Study Hall is every Monday, 8-10pm in Hayes 311, with free snacks. "
                "Tell us what snacks you want. Add the form link here.",
                author["id"])
