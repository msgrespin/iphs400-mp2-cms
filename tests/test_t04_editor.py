"""T04 (continued): Pages, Editor permissions, CSRF, and Author."""
import re

import pytest

from app import settings
from tests.conftest import csrf_token
from tests.test_t01 import rows, run_seed
from tests.test_t02 import create
from tests.test_t03 import read_all
from tests.test_t04 import (  # noqa: F401  (site_title is autouse)
    PAGES,
    edit_page,
    export,
    home_id,
    new_page,
    page_ids,
    publish_page,
    site_title,
)


# --- Editor ------------------------------------------------------------------

def test_editor_changes_the_body_of_an_existing_page(client_as, tmp_path):
    c = client_as("editor")
    response = edit_page(c, home_id(c), body="Study Hall is Mondays in Olin 101.")
    assert response.status_code in (302, 303)
    assert "Olin 101" in read_all(export(tmp_path))["index.html"]


def test_editor_cannot_change_a_pages_title_or_status_through_the_edit_request(
        client_as, tmp_path):
    admin = client_as("admin")
    about = new_page(admin, "About", body="Old")
    publish_page(admin, about)
    c = client_as("editor")
    response = edit_page(c, about, title="Hijacked", status="draft", body="New body")
    assert response.status_code in (302, 303)
    files = read_all(export(tmp_path))
    assert "New body" in files["about.html"]
    assert "Hijacked" not in "".join(files.values())
    assert "about.html" in files  # still Published
    page = admin.get(f"{PAGES}/{about}/edit").text
    assert 'value="About"' in page


@pytest.mark.parametrize("method,path,form", [
    ("get", f"{PAGES}/new", None),
    ("post", PAGES, {"title": "Sneaky", "body": "b"}),
    ("post", f"{PAGES}/{{id}}/publish", {}),
    ("post", f"{PAGES}/{{id}}/unpublish", {}),
    ("get", f"{PAGES}/{{id}}/delete", None),
    ("post", f"{PAGES}/{{id}}/delete", {}),
])
def test_editor_requesting_an_admin_action_by_direct_url_gets_403_and_nothing_changes(
        client_as, method, path, form):
    admin = client_as("admin")
    about = new_page(admin, "About")
    publish_page(admin, about)
    admin.get(PAGES)  # shows the one-time "Published" message, so the next view is stable
    before = admin.get(PAGES).text
    c = client_as("editor")
    path = path.replace("{id}", str(about))
    if method == "get":
        response = c.get(path)
    else:
        response = c.post(path, data={**form, "csrf_token": csrf_token(c, f"{PAGES}/{about}/edit")})
    assert response.status_code == 403
    assert "no permission" in response.text.lower()
    assert admin.get(PAGES).text == before


def test_editor_screens_have_no_create_or_delete_control_and_admin_screens_do(client_as):
    admin = client_as("admin")
    about = new_page(admin, "About")
    screens = [PAGES, f"{PAGES}/{about}/edit"]
    for path in screens:
        text = client_as("editor").get(path).text
        assert f"{PAGES}/new" not in text and "/delete" not in text, path
        assert "/publish" not in text and "/unpublish" not in text, path
    assert f"{PAGES}/new" in admin.get(PAGES).text
    assert f"{PAGES}/{about}/delete" in admin.get(PAGES).text
    assert f"{PAGES}/{about}/delete" in admin.get(f"{PAGES}/{about}/edit").text


# --- Home is protected ----------------------------------------------------------

@pytest.mark.parametrize("role", ["admin", "editor"])
def test_home_cannot_be_deleted_or_set_to_draft(client_as, tmp_path, role):
    c = client_as(role)
    home = home_id(c)
    for action in ("delete", "unpublish"):
        response = c.post(f"{PAGES}/{home}/{action}",
                          data={"csrf_token": csrf_token(c, f"{PAGES}/{home}/edit")},
                          follow_redirects=False)
        assert response.status_code in (400, 403)
    assert home in page_ids(c)
    assert (export(tmp_path) / "index.html").exists()


def test_admin_is_told_why_home_cannot_be_deleted_or_set_to_draft(client_as):
    c = client_as("admin")
    home = home_id(c)
    for path in (f"{PAGES}/{home}/delete", f"{PAGES}/{home}/unpublish"):
        response = c.post(path, data={"csrf_token": csrf_token(c, f"{PAGES}/{home}/edit")})
        assert response.status_code == 400 and "Home" in response.text
        assert "cannot" in response.text.lower()
    assert "Are you sure" not in c.get(f"{PAGES}/{home}/delete").text


def test_admin_screens_offer_no_delete_or_draft_control_for_home(client_as):
    c = client_as("admin")
    home = home_id(c)
    assert f"{PAGES}/{home}/delete" not in c.get(PAGES).text
    assert f"{PAGES}/{home}/unpublish" not in c.get(f"{PAGES}/{home}/edit").text


# --- CSRF, sign-in, 404 -----------------------------------------------------------

def test_every_page_form_carries_a_csrf_token_and_is_rejected_without_one(client_as):
    c = client_as("admin")
    about = new_page(c, "About")
    for path in (f"{PAGES}/new", f"{PAGES}/{about}/edit", f"{PAGES}/{about}/delete",
                 PAGES):
        assert 'name="csrf_token"' in c.get(path).text, path
    for path, form in [(PAGES, {"title": "x", "body": "y"}),
                       (f"{PAGES}/{about}", {"title": "x", "body": "y"}),
                       (f"{PAGES}/{about}/publish", {}),
                       (f"{PAGES}/{about}/unpublish", {}),
                       (f"{PAGES}/{about}/delete", {}),
                       (f"{PAGES}/preview", {"title": "x", "body": "y"})]:
        assert c.post(path, data=form, follow_redirects=False).status_code in (400, 403), path
    assert about in page_ids(c)


def test_editor_save_without_a_token_is_rejected(client_as):
    c = client_as("editor")
    response = c.post(f"{PAGES}/{home_id(c)}", data={"body": "x"}, follow_redirects=False)
    assert response.status_code in (400, 403)


@pytest.mark.parametrize("method,path", [
    ("get", PAGES), ("get", f"{PAGES}/new"), ("get", f"{PAGES}/1/edit"),
    ("get", f"{PAGES}/1/delete"), ("post", PAGES), ("post", f"{PAGES}/1"),
    ("post", f"{PAGES}/1/publish"), ("post", f"{PAGES}/1/unpublish"),
    ("post", f"{PAGES}/1/delete"), ("post", f"{PAGES}/preview"),
])
def test_anonymous_requests_to_any_page_screen_redirect_to_sign_in(client, method, path):
    response = getattr(client, method)(path, follow_redirects=False)
    assert response.status_code in (302, 303)
    assert response.headers["location"] == "/login"


def test_a_missing_page_is_a_404(client_as):
    c = client_as("admin")
    assert c.get(f"{PAGES}/9999/edit").status_code == 404
    assert c.get(f"{PAGES}/9999/delete").status_code == 404
    token = csrf_token(c, f"{PAGES}/{home_id(c)}/edit")
    assert c.post(f"{PAGES}/9999", data={"title": "x", "body": "y", "csrf_token": token}
                  ).status_code == 404


def test_the_console_front_door_links_to_pages(client_as):
    assert PAGES in client_as("editor").get("/admin").text


# --- Author -------------------------------------------------------------------

def author_cell(c, title):
    """The Author column text in the list row for this Page."""
    row = re.search(rf"<tr>(?:(?!</tr>).)*{re.escape(title)}.*?</tr>",
                    c.get(PAGES).text, re.DOTALL).group(0)
    return re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)[2].strip()


def test_the_pages_list_shows_the_position_that_created_each_page(client_as):
    new_page(client_as("admin"), "Meetings")
    editor_list = client_as("editor")
    assert author_cell(editor_list, "Meetings") == "Co-VP"


def test_the_edit_screen_shows_the_author(client_as):
    c = client_as("admin")
    page_id = new_page(c, "Meetings")
    assert "Author: Co-VP" in c.get(f"{PAGES}/{page_id}/edit").text


def test_editing_a_page_does_not_change_its_author(client_as):
    page_id = new_page(client_as("admin"), "Meetings")
    edit_page(client_as("editor"), page_id, body="Changed by an Editor")
    assert author_cell(client_as("admin"), "Meetings") == "Co-VP"


def test_seed_gives_the_three_pages_the_co_vp_as_author(tmp_path):
    db = tmp_path / "seed.db"
    assert run_seed(db).returncode == 0
    authors = rows(db, "select title, display_name from pages"
                       " join accounts on accounts.id = pages.author_id order by pages.id")
    assert authors == [("Home", "Co-VP"), ("About", "Co-VP"), ("Join & Snacks", "Co-VP")]


def test_home_made_before_any_account_exists_has_no_author_and_still_lists(client_as):
    assert author_cell(client_as("admin"), "Home") in ("", "—")


def test_no_author_or_position_name_appears_in_any_exported_page(client_as, tmp_path):
    c = client_as("editor")
    new_page(client_as("admin"), "About", body="Who we are")
    publish_page(client_as("admin"), max(page_ids(c)))
    for name, text in read_all(export(tmp_path)).items():
        assert "Social Chair" not in text and "Co-VP" not in text, name


def test_an_existing_database_without_the_author_column_is_upgraded(tmp_path, monkeypatch):
    import sqlite3

    from app import content

    old = tmp_path / "old.db"
    with sqlite3.connect(old) as conn:
        conn.execute("create table pages (id integer primary key, title text not null,"
                     " link text not null unique, body text not null default '',"
                     " status text not null default 'draft', is_home integer not null"
                     " default 0, created_at text not null, updated_at text not null,"
                     " first_published_at text)")
        conn.execute("insert into pages (title, link, body, status, is_home, created_at,"
                     " updated_at) values ('Home', 'index', 'kept', 'published', 1, 'a', 'b')")
    monkeypatch.setattr(settings, "DATABASE_PATH", old)
    content.init_db()
    content.init_db()  # twice: the upgrade must be repeatable
    home = content.home_page()
    assert home["body"] == "kept" and home["author_id"] is None
