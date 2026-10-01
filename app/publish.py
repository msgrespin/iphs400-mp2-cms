"""Render the public site into site/ as plain HTML.

Only PUBLISHED Posts are written here. A draft that reaches site/ is a bug.
Every href and src is RELATIVE ("style.css", "posts/x.html", "../style.css"),
never root-absolute, because Pages serves this from a subfolder.

The render_* functions are also what the local preview at / calls, so the
preview and the export cannot disagree.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from markupsafe import Markup

from app import content, markdown, settings

CSS = """/* Public site styles. */
:root { color-scheme: light dark; }
body { font: 16px/1.6 system-ui, sans-serif; margin: 0 auto; max-width: 42rem; padding: 1rem; }
header a { font-weight: 700; text-decoration: none; }
main { margin-block: 2rem; }
article { overflow-wrap: anywhere; }
.date { margin-block: 0 1rem; opacity: 0.75; }
"""


def environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(settings.TEMPLATES)),
        autoescape=select_autoescape(["html"]),
    )


def _view(row) -> dict:
    """What a Visitor sees of a Post. The Author is deliberately not here."""
    return {"title": row["title"], "link": row["link"],
            "date": content.public_date(row["first_published_at"]),
            "body_html": Markup(markdown.render(row["body"]))}


def _render(template: str, depth: int, **context) -> str:
    up = "../" * depth
    return environment().get_template(template).render(
        title=settings.SITE_TITLE, css_path=f"{up}style.css",
        home_path=f"{up}index.html", **context)


def render_front(rows=None) -> str:
    posts = content.published_posts() if rows is None else rows
    return _render("public/home.html", 0, latest=_view(posts[0]) if posts else None,
                   past_href="posts/index.html")


def render_past(rows=None) -> str:
    posts = content.published_posts() if rows is None else rows
    return _render("public/past.html", 1, posts=[_view(row) for row in posts[1:]])


def render_post(link: str, rows=None) -> str | None:
    for row in (content.published_posts() if rows is None else rows):
        if row["link"] == link:
            return _render("public/post.html", 1, post=_view(row),
                           past_href="index.html")
    return None


def render_site(out: Path | None = None) -> Path:
    out = out or settings.SITE
    rows = content.published_posts()
    # Render everything before touching the folder, so a failure leaves the
    # previous site/ in place instead of an empty one.
    pages = {"index.html": render_front(rows), "posts/index.html": render_past(rows)}
    for row in rows:
        pages[f"posts/{row['link']}.html"] = render_post(row["link"], rows)
    if out.exists():
        shutil.rmtree(out)
    (out / "posts").mkdir(parents=True)
    (out / "style.css").write_text(CSS)
    for name, html in pages.items():
        (out / name).write_text(html)
    return out
