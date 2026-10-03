"""Render the public site into site/ as plain HTML.

Only PUBLISHED Posts and Pages are written here. A draft that reaches site/ is a bug.
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
nav ul { display: flex; flex-wrap: wrap; gap: 0.25rem 1rem; list-style: none; margin: 0.5rem 0 0; padding: 0; }
main { margin-block: 2rem; }
article { overflow-wrap: anywhere; }
nav form { display: inline; margin: 0; }
.table-wrap { overflow-x: auto; }
td, th { overflow-wrap: break-word; text-align: left; padding: 0.25rem 0.5rem; }
.date { margin-block: 0 1rem; opacity: 0.75; }
textarea { box-sizing: border-box; max-width: 100%; width: 100%; }
main p { overflow-wrap: anywhere; }
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


def _file_name(page) -> str:
    """Home is the site root; every other Page is named by its Link."""
    return "index.html" if page["is_home"] else f"{page['link']}.html"


def _render(template: str, depth: int, pages, **context) -> str:
    """Render a public page. Every one gets the same navigation, with paths that
    climb `depth` folders to reach the Pages."""
    up = "../" * depth
    nav = [{"title": page["title"], "href": f"{up}{_file_name(page)}"} for page in pages]
    return environment().get_template(template).render(
        title=settings.SITE_TITLE, css_path=f"{up}style.css",
        home_path=f"{up}index.html", nav=nav, **context)


def _page_view(page) -> dict:
    return {"title": page["title"], "body_html": Markup(markdown.render(page["body"]))}


def render_front(rows=None, pages=None) -> str:
    posts = content.published_posts() if rows is None else rows
    pages = content.published_pages() if pages is None else pages
    return _render("public/home.html", 0, pages,
                   home=_page_view(content.home_page()),
                   latest=_view(posts[0]) if posts else None,
                   past_href="posts/index.html")


def render_page(link: str, pages=None, rows=None) -> str | None:
    pages = content.published_pages() if pages is None else pages
    for page in pages:
        if page["link"] == link:
            if page["is_home"]:
                return render_front(rows, pages)
            return _render("public/page.html", 0, pages, page=_page_view(page))
    return None


def render_past(rows=None, pages=None) -> str:
    posts = content.published_posts() if rows is None else rows
    pages = content.published_pages() if pages is None else pages
    return _render("public/past.html", 1, pages, posts=[_view(row) for row in posts[1:]])


def render_post(link: str, rows=None, pages=None) -> str | None:
    pages = content.published_pages() if pages is None else pages
    for row in (content.published_posts() if rows is None else rows):
        if row["link"] == link:
            return _render("public/post.html", 1, pages, post=_view(row),
                           past_href="index.html")
    return None


def render_site(out: Path | None = None) -> Path:
    out = out or settings.SITE
    rows = content.published_posts()
    nav_pages = content.published_pages()
    # Render everything before touching the folder, so a failure leaves the
    # previous site/ in place instead of an empty one.
    files = {"index.html": render_front(rows, nav_pages),
             "posts/index.html": render_past(rows, nav_pages)}
    for page in nav_pages:
        if not page["is_home"]:
            files[_file_name(page)] = render_page(page["link"], nav_pages, rows)
    for row in rows:
        files[f"posts/{row['link']}.html"] = render_post(row["link"], rows, nav_pages)
    if out.exists():
        shutil.rmtree(out)
    (out / "posts").mkdir(parents=True)
    (out / "style.css").write_text(CSS)
    for name, html in files.items():
        (out / name).write_text(html)
    return out
