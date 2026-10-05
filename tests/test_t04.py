"""T04: Pages make up the site: Home, About, Join & Snacks."""
import re

import pytest

from app import settings
from app.publish import render_site
from tests.conftest import csrf_token
from tests.test_t01 import rows, run_seed
from tests.test_t02 import act, create, newest_id
from tests.test_t03 import XSS_BODY, read_all, write

PAGES = "/admin/pages"


@pytest.fixture(autouse=True)
def site_title(monkeypatch):
    monkeypatch.setattr(settings, "SITE_TITLE", "AWM at Kenyon")


def export(tmp_path):
    return render_site(tmp_path / "site")


def page_ids(c):
    return [int(i) for i in re.findall(r"/admin/pages/(\d+)/edit", c.get(PAGES).text)]


def page_id_titled(c, title):
    """The id of the Page whose row in the list names this title."""
    for page_id in page_ids(c):
        if title in c.get(f"{PAGES}/{page_id}/edit").text:
            return page_id
    raise AssertionError(f"no Page titled {title!r}")


def new_page(c, title="Meetings", body="Body text."):
    token = csrf_token(c, f"{PAGES}/new")
    response = c.post(PAGES, data={"title": title, "body": body, "csrf_token": token},
                      follow_redirects=False)
    assert response.status_code in (302, 303), response.text
    return max(page_ids(c))


def post_page(c, path, form_path=None, **fields):
    token = csrf_token(c, form_path or PAGES)
    return c.post(path, data={**fields, "csrf_token": token}, follow_redirects=False)


def edit_page(c, page_id, **fields):
    return post_page(c, f"{PAGES}/{page_id}", f"{PAGES}/{page_id}/edit", **fields)


def publish_page(c, page_id):
    return post_page(c, f"{PAGES}/{page_id}/publish", f"{PAGES}/{page_id}/edit")


def unpublish_page(c, page_id):
    return post_page(c, f"{PAGES}/{page_id}/unpublish", f"{PAGES}/{page_id}/edit")


def delete_page(c, page_id):
    return post_page(c, f"{PAGES}/{page_id}/delete", f"{PAGES}/{page_id}/edit")


def home_id(c):
    return page_id_titled(c, "Home")


def nav_links(html):
    nav = re.search(r"<nav.*?</nav>", html, re.DOTALL)
    assert nav, "every public page needs a <nav>"
    return re.findall(r'href="([^"]+)"', nav.group(0))


# --- seed script -----------------------------------------------------------

def test_seed_creates_the_three_pages_in_order_and_twice_makes_no_duplicates(tmp_path):
    db = tmp_path / "seed.db"
    assert run_seed(db).returncode == 0
    assert run_seed(db).returncode == 0
    found = rows(db, "select title, status from pages order by created_at, id")
    assert found == [("Home", "published"), ("About", "published"),
                     ("Join & Snacks", "published")]


def test_home_exists_and_is_listed_without_the_seed_script(client_as):
    page = client_as("editor").get(PAGES).text
    assert "Home" in page and len(page_ids(client_as("editor"))) == 1


def test_export_without_the_seed_script_still_writes_home(tmp_path):
    out = export(tmp_path)
    assert (out / "index.html").exists()
    assert nav_links((out / "index.html").read_text()) == ["index.html"]


# --- the exported site -------------------------------------------------------

def test_export_writes_one_file_per_published_page_named_by_its_link(client_as, tmp_path):
    c = client_as("admin")
    about = new_page(c, "About")
    publish_page(c, about)
    new_page(c, "Join & Snacks")  # stays Draft
    out = export(tmp_path)
    assert sorted(p.name for p in out.glob("*.html")) == ["about.html", "index.html"]


def test_every_exported_file_has_the_same_navigation(client_as, tmp_path):
    c = client_as("admin")
    for title in ("About", "Join & Snacks"):
        publish_page(c, new_page(c, title))
    write(client_as("editor"), "Study Hall tonight")
    out = export(tmp_path)
    files = {n: t for n, t in read_all(out).items() if n.endswith(".html")}
    assert {"index.html", "about.html", "join-snacks.html", "posts/index.html"} <= set(files)
    for name, text in files.items():
        up = "../" if name.startswith("posts/") else ""
        assert nav_links(text) == [f"{up}index.html", f"{up}about.html",
                                   f"{up}join-snacks.html"], name
    assert all("Past posts" not in re.search(r"<nav.*?</nav>", t, re.DOTALL).group(0)
               for t in files.values())


def test_navigation_follows_creation_order_not_title_order(client_as, tmp_path):
    c = client_as("admin")
    for title in ("Zebra", "Apple"):
        publish_page(c, new_page(c, title))
    assert nav_links(read_all(export(tmp_path))["index.html"]) == [
        "index.html", "zebra.html", "apple.html"]


def test_a_draft_page_has_no_file_and_is_not_in_the_navigation(client_as, tmp_path):
    c = client_as("admin")
    new_page(c, "Secret page", body="Hidden words")
    out = export(tmp_path)
    assert not (out / "secret-page.html").exists()
    for name, text in read_all(out).items():
        assert "Secret page" not in text and "Hidden words" not in text, name


def test_unpublishing_a_page_removes_it_from_the_next_export(client_as, tmp_path):
    c = client_as("admin")
    about = new_page(c, "About")
    publish_page(c, about)
    assert (export(tmp_path) / "about.html").exists()
    unpublish_page(c, about)
    out = export(tmp_path)
    assert not (out / "about.html").exists()
    assert "about.html" not in read_all(out)["index.html"]


def test_exported_home_shows_its_body_above_the_latest_post(client_as, tmp_path):
    write(client_as("editor"), "Latest news", body="Latest words")
    html = read_all(export(tmp_path))["index.html"]
    assert "Hayes 311" in html and "Latest words" in html
    assert html.index("Hayes 311") < html.index("Latest news")


def test_changing_the_room_in_home_replaces_it_everywhere_in_the_export(client_as, tmp_path):
    c = client_as("admin")
    write(client_as("editor"), "Weekly", body="See you there.")
    assert "Hayes 311" in read_all(export(tmp_path))["index.html"]
    edit_page(c, home_id(c), title="Home", body="Study Hall is Mondays, 8-10pm in Olin 101.")
    files = read_all(export(tmp_path))
    assert "Olin 101" in files["index.html"]
    assert not any("Hayes 311" in text for text in files.values())


def test_page_body_with_script_and_onerror_is_harmless_in_export_and_preview(
        client_as, tmp_path):
    c = client_as("admin")
    about = new_page(c, "About", body=XSS_BODY)
    publish_page(c, about)
    for name, text in read_all(export(tmp_path)).items():
        assert "<script" not in text.lower() and "onerror" not in text.lower(), name
    token = csrf_token(c, f"{PAGES}/new")
    preview = c.post(f"{PAGES}/preview",
                     data={"title": "About", "body": XSS_BODY, "csrf_token": token}).text
    assert "<script" not in preview.lower() and "onerror" not in preview.lower()
    local = c.get("/about.html").text
    assert "<script" not in local.lower() and "onerror" not in local.lower()


def test_no_exported_page_uses_root_absolute_paths_and_nav_points_at_real_files(
        client_as, tmp_path):
    c = client_as("admin")
    for title in ("About", "Join & Snacks"):
        publish_page(c, new_page(c, title))
    write(client_as("editor"), "One")
    out = export(tmp_path)
    for name, text in read_all(out).items():
        if name.endswith(".html"):
            assert 'href="/' not in text and 'src="/' not in text, name
            base = (out / name).parent
            for href in nav_links(text):
                assert (base / href).resolve().is_file(), (name, href)


def test_local_preview_serves_published_pages_and_hides_drafts(client, client_as):
    c = client_as("admin")
    about = new_page(c, "About", body="About words")
    new_page(c, "Secret page")
    assert client.get("/about.html").status_code == 404
    publish_page(c, about)
    assert "About words" in client.get("/about.html").text
    assert client.get("/secret-page.html").status_code == 404
    assert "about.html" in client.get("/").text


# --- Admin: create, rename, status, delete --------------------------------------

def test_admin_creates_a_page_sets_it_to_published_and_back_to_draft(client_as, tmp_path):
    c = client_as("admin")
    page_id = new_page(c, "Meetings", body="Meeting words")
    assert "Draft" in c.get(PAGES).text
    assert "Meeting words" not in "".join(read_all(export(tmp_path)).values())
    assert publish_page(c, page_id).status_code in (302, 303)
    assert "Meeting words" in read_all(export(tmp_path))["meetings.html"]
    assert unpublish_page(c, page_id).status_code in (302, 303)
    assert "meetings.html" not in read_all(export(tmp_path))


def test_admin_changes_a_pages_title_and_its_link_stays_put(client_as, tmp_path):
    c = client_as("admin")
    page_id = new_page(c, "Meetings")
    publish_page(c, page_id)
    edit_page(c, page_id, title="Study Halls", body="New body")
    files = read_all(export(tmp_path))
    assert "meetings.html" in files and "Study Halls" in files["meetings.html"]
    assert "Study Halls" in files["index.html"]


def test_admin_deletes_a_page_only_after_a_confirmation_screen(client_as, tmp_path):
    c = client_as("admin")
    page_id = new_page(c, "Temporary")
    publish_page(c, page_id)
    confirm = c.get(f"{PAGES}/{page_id}/delete")
    assert confirm.status_code == 200 and "Are you sure" in confirm.text
    assert page_id in page_ids(c)
    assert delete_page(c, page_id).status_code in (302, 303)
    assert page_id not in page_ids(c)
    assert "temporary.html" not in read_all(export(tmp_path))


def test_every_action_shows_a_message(client_as):
    c = client_as("admin")
    created = c.post(PAGES, data={"title": "Meetings", "body": "b",
                                  "csrf_token": csrf_token(c, f"{PAGES}/new")})
    assert "Created" in created.text and "Meetings" in created.text
    page_id = max(page_ids(c))
    published = post_page(c, f"{PAGES}/{page_id}/publish", f"{PAGES}/{page_id}/edit")
    assert "Published" in c.get(published.headers["location"]).text
    saved = edit_page(c, page_id, title="Meetings", body="changed")
    assert "Saved" in c.get(saved.headers["location"]).text
    deleted = delete_page(c, page_id)
    assert "Deleted" in c.get(deleted.headers["location"]).text


def test_a_page_needs_a_title(client_as):
    c = client_as("admin")
    response = c.post(PAGES, data={"title": "  ", "body": "b",
                                   "csrf_token": csrf_token(c, f"{PAGES}/new")})
    assert response.status_code == 400 and "needs a title" in response.text
    assert len(page_ids(c)) == 1


# --- Links -----------------------------------------------------------------

def test_two_pages_with_the_same_title_get_different_links(client_as, tmp_path):
    c = client_as("admin")
    for _ in range(2):
        publish_page(c, new_page(c, "Meetings"))
    names = sorted(p.name for p in export(tmp_path).glob("*.html"))
    assert names == ["index.html", "meetings-2.html", "meetings.html"]


def test_a_page_titled_index_cannot_overwrite_home(client_as, tmp_path):
    c = client_as("admin")
    publish_page(c, new_page(c, "Index", body="Not the front page"))
    out = export(tmp_path)
    assert "Not the front page" not in (out / "index.html").read_text()
    assert "Not the front page" in (out / "index-2.html").read_text()


def test_the_page_form_has_no_field_for_a_link(client_as):
    c = client_as("admin")
    page_id = new_page(c, "Meetings")
    for path in (f"{PAGES}/new", f"{PAGES}/{page_id}/edit"):
        form = c.get(path).text.lower()
        assert 'name="link"' not in form and 'name="slug"' not in form


def test_a_link_typed_into_the_request_is_ignored(client_as, tmp_path):
    c = client_as("admin")
    token = csrf_token(c, f"{PAGES}/new")
    c.post(PAGES, data={"title": "Meetings", "body": "b", "link": "evil", "slug": "evil",
                        "csrf_token": token})
    publish_page(c, max(page_ids(c)))
    assert (export(tmp_path) / "meetings.html").exists()
    assert not (export(tmp_path) / "evil.html").exists()
