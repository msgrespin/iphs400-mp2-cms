"""T02: Editors write, publish, and delete Posts."""
import re
from datetime import datetime, timezone

import pytest

from app import content
from tests.conftest import csrf_token
from tests.test_t01 import rows, run_seed

LIST = "/admin/posts"


def at(iso: str):
    """Freeze the Posts clock at a UTC time, e.g. at("2026-10-05T23:30:00")."""
    when = datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)
    return lambda: when


def create(c, title="Study Hall tonight", body="Hayes 311, 8pm.", token=None):
    if token is None:
        token = csrf_token(c, f"{LIST}/new")
    return c.post(LIST, data={"title": title, "body": body, "csrf_token": token},
                  follow_redirects=False)


def post_ids(c):
    return [int(i) for i in re.findall(r"/admin/posts/(\d+)/edit", c.get(LIST).text)]


def newest_id(c):
    return max(post_ids(c))


def edit(c, post_id, **fields):
    token = csrf_token(c, f"{LIST}/{post_id}/edit")
    return c.post(f"{LIST}/{post_id}", data={**fields, "csrf_token": token},
                  follow_redirects=False)


def act(c, post_id, action):
    token = csrf_token(c, f"{LIST}/{post_id}/edit")
    return c.post(f"{LIST}/{post_id}/{action}", data={"csrf_token": token},
                  follow_redirects=False)


def link_of(c, post_id):
    page = c.get(f"{LIST}/{post_id}/edit").text
    match = re.search(r"<code[^>]*>([^<]+)</code>", page)
    assert match, "the edit screen should show the Post's Link"
    return match.group(1)


# --- create, list, Author -------------------------------------------------

def test_new_post_is_saved_as_a_draft_and_listed_with_its_author(client_as):
    c = client_as("editor")
    response = create(c, title="Study Hall tonight")
    assert response.status_code in (302, 303)
    page = c.get(LIST).text
    assert "Study Hall tonight" in page
    assert "Draft" in page
    assert "Social Chair" in page


def test_editing_changes_updated_time_but_not_author_or_created_time(client_as, monkeypatch):
    editor = client_as("editor")
    monkeypatch.setattr(content, "now", at("2026-10-05T18:00:00"))  # 2:00 pm Eastern
    create(editor)
    post_id = newest_id(editor)
    monkeypatch.setattr(content, "now", at("2026-10-06T18:00:00"))
    admin = client_as("admin")
    assert edit(admin, post_id, title="Study Hall tonight", body="Moved to Hayes 312"
                ).status_code in (302, 303)
    page = admin.get(f"{LIST}/{post_id}/edit").text
    assert "Created 2026-10-05 14:00" in page
    assert "Updated 2026-10-06 14:00" in page
    assert "Social Chair" in admin.get(LIST).text
    assert "Co-VP" not in admin.get(LIST).text.split("<main")[1]


# --- Published / Draft ----------------------------------------------------

def test_publish_and_unpublish_change_the_status(client_as):
    c = client_as("editor")
    create(c)
    post_id = newest_id(c)
    assert act(c, post_id, "publish").status_code in (302, 303)
    assert "Published" in c.get(LIST).text
    assert act(c, post_id, "unpublish").status_code in (302, 303)
    listing = c.get(LIST).text
    assert "Draft" in listing and "Published" not in listing


def test_first_published_time_is_set_once(client_as, monkeypatch):
    c = client_as("editor")
    monkeypatch.setattr(content, "now", at("2026-10-05T18:00:00"))
    create(c)
    post_id = newest_id(c)
    assert "First published" not in c.get(f"{LIST}/{post_id}/edit").text
    act(c, post_id, "publish")
    monkeypatch.setattr(content, "now", at("2026-10-12T18:00:00"))
    act(c, post_id, "unpublish")
    act(c, post_id, "publish")
    assert "First published 2026-10-05 14:00" in c.get(f"{LIST}/{post_id}/edit").text


# --- Links ----------------------------------------------------------------

def test_link_is_made_from_the_eastern_date_and_the_title(client_as, monkeypatch):
    c = client_as("editor")
    # 02:00 UTC on the 6th is still the evening of the 5th in Eastern time.
    monkeypatch.setattr(content, "now", at("2026-10-06T02:00:00"))
    create(c, title="Study Hall Tonight!")
    assert link_of(c, newest_id(c)) == "2026-10-05-study-hall-tonight"


def test_post_form_has_no_link_field(client_as):
    c = client_as("editor")
    for path in (f"{LIST}/new",):
        fields = re.findall(r'<(?:input|textarea|select)[^>]*name="([^"]+)"',
                            c.get(path).text)
        assert not [f for f in fields if "link" in f.lower() or "slug" in f.lower()]
    create(c)
    fields = re.findall(r'<(?:input|textarea|select)[^>]*name="([^"]+)"',
                        c.get(f"{LIST}/{newest_id(c)}/edit").text)
    assert not [f for f in fields if "link" in f.lower() or "slug" in f.lower()]


def test_same_title_on_the_same_day_gets_a_different_link(client_as, monkeypatch):
    c = client_as("editor")
    monkeypatch.setattr(content, "now", at("2026-10-05T18:00:00"))
    create(c, title="Study Hall tonight")
    first = newest_id(c)
    create(c, title="Study Hall tonight")
    second = newest_id(c)
    assert first != second
    assert link_of(c, first) != link_of(c, second)


def test_changing_the_title_does_not_change_the_link(client_as):
    c = client_as("editor")
    create(c, title="Study Hall tonight")
    post_id = newest_id(c)
    before = link_of(c, post_id)
    edit(c, post_id, title="A completely different title", body="x")
    assert link_of(c, post_id) == before
    act(c, post_id, "publish")
    edit(c, post_id, title="Yet another title", body="x")
    assert link_of(c, post_id) == before


# --- any Editor can edit and delete any Post ------------------------------

def test_another_position_can_edit_and_delete_a_post(client_as):
    social = client_as("editor")
    create(social, title="Written by the Social Chair")
    post_id = newest_id(social)
    admin = client_as("admin")  # a different Position's Account
    assert edit(admin, post_id, title="Fixed by someone else", body="ok"
                ).status_code in (302, 303)
    assert "Fixed by someone else" in admin.get(LIST).text
    token = csrf_token(admin, f"{LIST}/{post_id}/delete")
    assert admin.post(f"{LIST}/{post_id}/delete", data={"csrf_token": token},
                      follow_redirects=False).status_code in (302, 303)
    assert post_id not in post_ids(admin)


# --- deleting -------------------------------------------------------------

def test_get_never_deletes_and_shows_a_confirmation_screen(client_as):
    c = client_as("editor")
    create(c, title="Keep me")
    post_id = newest_id(c)
    page = c.get(f"{LIST}/{post_id}/delete")
    assert page.status_code == 200
    assert "Are you sure" in page.text
    assert "Keep me" in page.text
    assert 'name="csrf_token"' in page.text
    assert post_id in post_ids(c)


def test_confirmed_post_deletes_permanently(client_as):
    c = client_as("editor")
    create(c, title="Delete me")
    post_id = newest_id(c)
    token = csrf_token(c, f"{LIST}/{post_id}/delete")
    c.post(f"{LIST}/{post_id}/delete", data={"csrf_token": token})
    assert "Delete me" not in c.get(LIST).text
    assert c.get(f"{LIST}/{post_id}/edit").status_code == 404


# --- validation, messages -------------------------------------------------

@pytest.mark.parametrize("title", ["", "   "])
def test_empty_title_is_refused_and_nothing_is_saved(client_as, title):
    c = client_as("editor")
    response = create(c, title=title, body="Some body text")
    assert response.status_code == 400
    assert "title" in response.text.lower() and 'role="alert"' in response.text
    assert "Some body text" in response.text  # the Officer's text is not lost
    assert post_ids(c) == []


def test_editing_to_an_empty_title_is_refused_and_changes_nothing(client_as):
    c = client_as("editor")
    create(c, title="Original title")
    post_id = newest_id(c)
    assert edit(c, post_id, title="", body="x").status_code == 400
    assert "Original title" in c.get(LIST).text


def test_each_action_shows_a_message_saying_what_happened(client_as):
    c = client_as("editor")
    page = c.post(LIST, data={"title": "Msg post", "body": "b",
                              "csrf_token": csrf_token(c, f"{LIST}/new")},
                  follow_redirects=True).text
    assert "Created" in page and "Msg post" in page
    post_id = newest_id(c)
    token = csrf_token(c, f"{LIST}/{post_id}/edit")
    seen = {}
    seen["edit"] = c.post(f"{LIST}/{post_id}", follow_redirects=True,
                          data={"title": "Msg post", "body": "c", "csrf_token": token}).text
    seen["publish"] = c.post(f"{LIST}/{post_id}/publish", follow_redirects=True,
                             data={"csrf_token": token}).text
    seen["unpublish"] = c.post(f"{LIST}/{post_id}/unpublish", follow_redirects=True,
                               data={"csrf_token": token}).text
    seen["delete"] = c.post(f"{LIST}/{post_id}/delete", follow_redirects=True,
                            data={"csrf_token": token}).text
    assert "Saved" in seen["edit"]
    assert "Published" in seen["publish"] and "Msg post" in seen["publish"]
    assert "Draft" in seen["unpublish"] and "Msg post" in seen["unpublish"]
    assert "Deleted" in seen["delete"] and "Msg post" in seen["delete"]


def test_a_message_is_shown_once(client_as):
    c = client_as("editor")
    create(c, title="Once")
    assert "Created" in c.get(LIST).text
    assert "Created" not in c.get(LIST).text


# --- CSRF, anonymous, escaping --------------------------------------------

def test_posts_without_a_valid_csrf_token_change_nothing(client_as):
    c = client_as("editor")
    create(c, title="Stays put")
    post_id = newest_id(c)
    for token in ("", "forged"):
        assert create(c, title="Sneaky", token=token).status_code == 403
        assert c.post(f"{LIST}/{post_id}", data={"title": "Changed", "body": "x",
                                                 "csrf_token": token}).status_code == 403
        for action in ("publish", "unpublish", "delete"):
            assert c.post(f"{LIST}/{post_id}/{action}",
                          data={"csrf_token": token}).status_code == 403
    page = c.get(LIST).text
    assert "Stays put" in page and "Sneaky" not in page and "Changed" not in page
    assert "Draft" in page


def test_every_post_form_carries_a_csrf_token(client_as):
    c = client_as("editor")
    create(c)
    post_id = newest_id(c)
    for path in (f"{LIST}/new", f"{LIST}/{post_id}/edit", f"{LIST}/{post_id}/delete"):
        page = c.get(path).text
        assert page.count("<form") == page.count('name="csrf_token"') >= 1, path


def test_anonymous_requests_redirect_to_sign_in(client, client_as):
    c = client_as("editor")
    create(c)
    post_id = newest_id(c)
    for path in (LIST, f"{LIST}/new", f"{LIST}/{post_id}/edit",
                 f"{LIST}/{post_id}/delete"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code in (302, 303), path
        assert response.headers["location"] == "/login"
    for path in (LIST, f"{LIST}/{post_id}", f"{LIST}/{post_id}/publish",
                 f"{LIST}/{post_id}/unpublish", f"{LIST}/{post_id}/delete"):
        response = client.post(path, data={}, follow_redirects=False)
        assert response.status_code in (302, 303), path
        assert response.headers["location"] == "/login"
    assert "Draft" in c.get(LIST).text


def test_a_script_in_a_title_is_shown_as_text(client_as):
    c = client_as("editor")
    create(c, title="<script>alert(1)</script>")
    post_id = newest_id(c)
    for path in (LIST, f"{LIST}/{post_id}/edit", f"{LIST}/{post_id}/delete"):
        page = c.get(path).text
        assert "<script>alert(1)</script>" not in page, path
        assert "&lt;script&gt;" in page, path
    assert "<script>" not in act(c, post_id, "publish").text


# --- seed script ----------------------------------------------------------

def test_seed_creates_a_published_and_a_draft_post_and_exits_zero(tmp_path):
    db = tmp_path / "seed.db"
    assert run_seed(db).returncode == 0
    statuses = {r[0] for r in rows(db, "select status from posts")}
    assert {"published", "draft"} <= statuses


def test_seed_twice_does_not_duplicate_posts(tmp_path):
    db = tmp_path / "seed.db"
    run_seed(db)
    count = rows(db, "select count(*) from posts")
    assert run_seed(db).returncode == 0
    assert rows(db, "select count(*) from posts") == count

