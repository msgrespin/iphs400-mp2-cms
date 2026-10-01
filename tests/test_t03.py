"""T03: Published Posts reach the public site."""
import re

import pytest

from app import content, settings
from app.publish import render_site
from tests.conftest import csrf_token
from tests.test_t02 import act, at, create, newest_id

XSS_BODY = ('<script>window.__xss=1</script>\n\n'
            '<img src=x onerror="window.__xss=2">')


@pytest.fixture(autouse=True)
def site_title(monkeypatch):
    monkeypatch.setattr(settings, "SITE_TITLE", "AWM at Kenyon")


def write(c, title, body="Hayes 311, 8pm.", publish=True, when=None, monkeypatch=None):
    """Create a Post through the console, optionally Published at a frozen time."""
    if when and monkeypatch:
        monkeypatch.setattr(content, "now", at(when))
    create(c, title=title, body=body)
    post_id = newest_id(c)
    if publish:
        act(c, post_id, "publish")
    return post_id


def export(tmp_path):
    return render_site(tmp_path / "site")


def read_all(out):
    return {p.relative_to(out).as_posix(): p.read_text()
            for p in out.rglob("*") if p.is_file()}


def post_files(out):
    return sorted(p.name for p in (out / "posts").glob("*.html") if p.name != "index.html")


# --- the exported folder --------------------------------------------------

def test_export_writes_front_page_post_pages_past_posts_and_stylesheet(
        client_as, tmp_path, monkeypatch):
    c = client_as("editor")
    write(c, "First", when="2026-10-05T12:00:00", monkeypatch=monkeypatch)
    write(c, "Second", when="2026-10-12T12:00:00", monkeypatch=monkeypatch)
    out = export(tmp_path)
    assert (out / "index.html").exists() and (out / "style.css").exists()
    assert (out / "posts" / "index.html").exists()
    assert post_files(out) == ["2026-10-05-first.html", "2026-10-12-second.html"]


def test_cms_publish_command_exits_zero_and_writes_the_folder(tmp_path, monkeypatch):
    from app.cli import main

    monkeypatch.setattr(settings, "SITE", tmp_path / "site")
    assert main(["publish"]) == 0
    assert (tmp_path / "site" / "index.html").exists()


def test_front_page_shows_the_latest_post_in_full(client_as, tmp_path, monkeypatch):
    c = client_as("editor")
    write(c, "Old news", body="Old body", when="2026-10-05T12:00:00", monkeypatch=monkeypatch)
    write(c, "New news", body="New **body**", when="2026-10-12T12:00:00",
          monkeypatch=monkeypatch)
    html = read_all(export(tmp_path))["index.html"]
    assert "New news" in html and "<strong>body</strong>" in html
    assert "Old body" not in html


def test_latest_is_by_first_published_time_not_creation(client_as, tmp_path, monkeypatch):
    c = client_as("editor")
    early = write(c, "Written first", publish=False, when="2026-10-01T12:00:00",
                  monkeypatch=monkeypatch)
    write(c, "Written second", when="2026-10-05T12:00:00", monkeypatch=monkeypatch)
    monkeypatch.setattr(content, "now", at("2026-10-12T12:00:00"))
    act(c, early, "publish")
    html = read_all(export(tmp_path))["index.html"]
    assert "Written first" in html and "Written second" not in html.split("Past posts")[0]


def test_front_page_without_posts_says_nothing_published_yet(tmp_path):
    html = read_all(export(tmp_path))["index.html"]
    assert "nothing published yet" in html.lower()


def test_past_posts_lists_older_posts_newest_first_without_the_latest(
        client_as, tmp_path, monkeypatch):
    c = client_as("editor")
    for title, when in [("Alpha", "2026-10-05T12:00:00"), ("Bravo", "2026-10-12T12:00:00"),
                        ("Charlie", "2026-10-19T12:00:00")]:
        write(c, title, when=when, monkeypatch=monkeypatch)
    files = read_all(export(tmp_path))
    past = files["posts/index.html"]
    assert "Charlie" not in past
    assert past.index("Bravo") < past.index("Alpha")
    assert 'href="2026-10-12-bravo.html"' in past
    assert 'href="2026-10-05-alpha.html"' in past
    assert 'href="posts/index.html"' in files["index.html"]


def test_drafts_appear_nowhere_in_the_export_or_the_preview(client_as, client, tmp_path):
    c = client_as("editor")
    write(c, "Secret plans", body="Hidden words", publish=False)
    write(c, "Open news", body="Open words")
    out = export(tmp_path)
    link = "secret-plans"
    for name, text in read_all(out).items():
        assert "Secret plans" not in text and "Hidden words" not in text, name
        assert link not in text, name
    assert not any(link in name for name in read_all(out))
    for path in ("/", "/posts/index.html"):
        page = client.get(path).text
        assert "Secret plans" not in page and "Hidden words" not in page
        assert link not in page


def test_deleted_or_unpublished_post_is_gone_from_the_next_export(client_as, tmp_path):
    c = client_as("editor")
    unpublished = write(c, "Pulled")
    deleted = write(c, "Removed")
    assert len(post_files(export(tmp_path))) == 2
    act(c, unpublished, "unpublish")
    token = csrf_token(c, f"/admin/posts/{deleted}/delete")
    c.post(f"/admin/posts/{deleted}/delete", data={"csrf_token": token})
    out = export(tmp_path)
    assert post_files(out) == []
    assert "Pulled" not in "".join(read_all(out).values())
    assert "Removed" not in "".join(read_all(out).values())


# --- dates, authors, paths ------------------------------------------------

def test_post_shows_first_published_date_with_weekday_in_eastern(
        client_as, tmp_path, monkeypatch):
    c = client_as("editor")
    # 9pm Eastern on Monday Oct 5 is 01:00 UTC on Tuesday Oct 6.
    write(c, "Late one", when="2026-10-06T01:00:00", monkeypatch=monkeypatch)
    files = read_all(export(tmp_path))
    assert "Monday, October 5, 2026" in files["posts/2026-10-05-late-one.html"]
    assert "Monday, October 5, 2026" in files["index.html"]
    assert "Tuesday" not in files["index.html"]


def test_date_does_not_move_when_a_post_is_edited_or_republished(
        client_as, tmp_path, monkeypatch):
    c = client_as("editor")
    post_id = write(c, "Steady", when="2026-10-05T12:00:00", monkeypatch=monkeypatch)
    monkeypatch.setattr(content, "now", at("2026-10-20T12:00:00"))
    act(c, post_id, "unpublish")
    act(c, post_id, "publish")
    html = read_all(export(tmp_path))["index.html"]
    assert "Monday, October 5, 2026" in html


def test_no_author_or_position_name_in_any_exported_file(client_as, tmp_path):
    write(client_as("editor"), "By someone")
    write(client_as("admin"), "By the admin")
    for name, text in read_all(export(tmp_path)).items():
        assert "Social Chair" not in text and "Co-VP" not in text, name


def test_exported_html_is_relative_and_post_pages_find_the_stylesheet(client_as, tmp_path):
    write(client_as("editor"), "One")
    write(client_as("editor"), "Two")
    out = export(tmp_path)
    for name, text in read_all(out).items():
        if name.endswith(".html"):
            assert 'href="/' not in text and 'src="/' not in text, name
    post_page = (out / "posts" / post_files(out)[0]).read_text()
    assert 'href="../style.css"' in post_page
    assert (out / "posts" / "../style.css").exists()
    assert 'href="../index.html"' in post_page


def test_a_root_absolute_link_in_a_body_is_not_exported(client_as, tmp_path):
    write(client_as("editor"), "Sneaky", body="[go](/admin) and [form](https://forms.example/x)")
    html = read_all(export(tmp_path))["index.html"]
    assert 'href="/' not in html
    assert 'href="https://forms.example/x"' in html


# --- one Markdown renderer ------------------------------------------------

def test_script_and_onerror_are_harmless_in_the_export(client_as, tmp_path):
    write(client_as("editor"), "Hostile", body=XSS_BODY)
    for name, text in read_all(export(tmp_path)).items():
        assert "<script" not in text.lower() and "onerror" not in text.lower(), name


def test_script_and_onerror_are_harmless_in_the_editor_preview(client_as):
    c = client_as("editor")
    token = csrf_token(c, "/admin/posts/new")
    page = c.post("/admin/posts/preview",
                  data={"title": "Hostile", "body": XSS_BODY, "csrf_token": token}).text
    assert "<script" not in page.lower() and "onerror" not in page.lower()


def test_bold_and_links_render_and_javascript_links_do_not(client_as, tmp_path):
    body = "**bold** [good](https://example.org/a) [evil](javascript:alert(1))"
    write(client_as("editor"), "Marked up", body=body)
    html = read_all(export(tmp_path))["index.html"]
    assert "<strong>bold</strong>" in html
    assert '<a href="https://example.org/a"' in html
    assert not re.search(r'href="\s*javascript:', html, re.IGNORECASE)


def test_rendered_bodies_contain_no_images(client_as, tmp_path):
    write(client_as("editor"), "Pictures", body="![cat](https://example.org/cat.png)")
    for name, text in read_all(export(tmp_path)).items():
        assert "<img" not in text.lower(), name


# --- the editor's Preview -------------------------------------------------

def preview(c, **fields):
    token = csrf_token(c, "/admin/posts/new")
    return c.post("/admin/posts/preview", data={**fields, "csrf_token": token})


def test_preview_shows_unsaved_text_for_a_draft_and_a_published_post(client_as):
    c = client_as("editor")
    draft = write(c, "Draft one", publish=False)
    live = write(c, "Live one")
    for post_id in (draft, live):
        page = preview(c, title="Unsaved title", body="Unsaved **words**").text
        assert "Unsaved title" in page and "<strong>words</strong>" in page
        assert "Unsaved" not in c.get(f"/admin/posts/{post_id}/edit").text.split("<form")[0]
    assert "Unsaved title" not in c.get("/admin/posts").text


def test_editor_form_offers_a_preview_button(client_as):
    page = client_as("editor").get("/admin/posts/new").text
    assert 'formaction="/admin/posts/preview"' in page


def test_preview_needs_sign_in_and_a_csrf_token(client, client_as):
    anonymous = client.post("/admin/posts/preview", data={"title": "x", "body": "y"},
                            follow_redirects=False)
    assert anonymous.status_code in (302, 303)
    refused = client_as("editor").post("/admin/posts/preview",
                                       data={"title": "x", "body": "y"})
    assert refused.status_code in (400, 403)


# --- local preview and site title -----------------------------------------

def test_local_preview_matches_the_export_and_shows_the_site_title(
        client, client_as, tmp_path):
    write(client_as("editor"), "Shown", body="Shown **body**")
    page = client.get("/").text
    assert "AWM at Kenyon" in page and "Shown" in page
    assert "<strong>body</strong>" in page
    assert "AWM at Kenyon" in read_all(export(tmp_path))["index.html"]
    assert client.get("/style.css").status_code == 200


def test_local_preview_serves_post_pages_and_past_posts(client, client_as, monkeypatch):
    c = client_as("editor")
    write(c, "Older", when="2026-10-05T12:00:00", monkeypatch=monkeypatch)
    write(c, "Newer", when="2026-10-12T12:00:00", monkeypatch=monkeypatch)
    assert "Older" in client.get("/posts/index.html").text
    assert "Older" in client.get("/posts/2026-10-05-older.html").text
    assert client.get("/posts/no-such-post.html").status_code == 404


def test_env_example_sets_the_site_title():
    text = (settings.ROOT / ".env.example").read_text()
    # Quoted, because a .env parser rejects an unquoted value with spaces.
    assert re.search(r'^CMS_SITE_TITLE="AWM at Kenyon"$', text, re.MULTILINE)


def test_preview_page_links_the_public_stylesheet_and_the_console(client_as):
    page = preview(client_as("editor"), title="T", body="b").text
    assert 'href="/style.css"' in page and 'href="/admin"' in page
