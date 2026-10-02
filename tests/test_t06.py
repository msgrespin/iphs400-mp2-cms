"""T06: Co-VPs manage Accounts."""
import re
import sqlite3

from fastapi.testclient import TestClient

from app import settings
from app.main import create_app
from tests.conftest import DEMO_USERS, csrf_token
from tests.test_t01 import sign_in

LIST = "/admin/accounts"
EDITOR = DEMO_USERS["editor"]
NEW = {"display_name": "Webmaster", "email": "webmaster@example.test",
       "role": "editor", "password": "brand-new-pw-1"}


def db_rows(sql, *args):
    with sqlite3.connect(settings.DATABASE_PATH) as conn:
        return conn.execute(sql, args).fetchall()


def account_id(email):
    return db_rows("select id from accounts where email = ?", email)[0][0]


def post(c, path, token_from=LIST, **data):
    return c.post(path, data={"csrf_token": csrf_token(c, token_from), **data},
                  follow_redirects=False)


def create(c, **overrides):
    return post(c, LIST, **{**NEW, **overrides})


def sign_in_fresh(email, password):
    c = TestClient(create_app())
    return c, sign_in(c, email=email, password=password)


def only_admin_id():
    return account_id("admin@example.test")


# --- the Accounts screen ---------------------------------------------------

def test_admin_sees_every_account_with_position_email_role_and_status(client_as):
    from app import accounts

    accounts.set_active("treasurer@example.test", False)
    page = client_as("admin").get(LIST)
    assert page.status_code == 200
    for position, email in [("Co-VP", "admin@example.test"),
                            ("Social Chair", "editor@example.test"),
                            ("Co-President", "copresident@example.test"),
                            ("Treasurer", "treasurer@example.test")]:
        assert position in page.text and email in page.text
    assert page.text.lower().count("deactivated") >= 1
    assert "Admin" in page.text and "Editor" in page.text


def test_accounts_screen_has_no_delete_control(client_as):
    page = client_as("admin").get(LIST).text.lower()
    assert "delete" not in page
    assert "remove" not in page


def test_every_accounts_form_carries_a_csrf_token(client_as):
    page = client_as("admin").get(LIST).text
    forms = re.findall(r"<form.*?</form>", page, re.S)
    assert len(forms) >= 5
    for form in forms:
        assert 'name="csrf_token"' in form


def test_admin_sees_the_accounts_link_and_editor_does_not(client_as):
    assert LIST in client_as("admin").get("/admin").text
    assert LIST not in client_as("editor").get("/admin").text


# --- creating ---------------------------------------------------------------

def test_admin_creates_an_account_that_can_sign_in_with_an_argon2_hash(client_as):
    response = create(client_as("admin"))
    assert response.status_code == 303
    stored = db_rows("select password_hash, display_name, role from accounts"
                     " where email = ?", NEW["email"])
    assert stored and stored[0][0].startswith("$argon2")
    assert stored[0][1:] == ("Webmaster", "editor")
    c, signed_in = sign_in_fresh(NEW["email"], NEW["password"])
    assert signed_in.status_code == 303
    assert "Webmaster" in c.get("/admin").text


def test_a_duplicate_email_is_refused_with_a_message_and_creates_nothing(client_as):
    admin = client_as("admin")
    response = create(admin, email="EDITOR@example.test")
    assert response.status_code == 400
    assert "already" in response.text.lower()
    assert db_rows("select count(*) from accounts") == [(4,)]


def test_a_bad_role_or_blank_field_creates_nothing(client_as):
    admin = client_as("admin")
    assert create(admin, role="superuser").status_code == 400
    assert create(admin, password="").status_code == 400
    assert create(admin, display_name="  ").status_code == 400
    assert create(admin, email="").status_code == 400
    assert db_rows("select count(*) from accounts") == [(4,)]


def test_the_response_after_creating_shows_a_message_and_never_the_password(client_as):
    admin = client_as("admin")
    response = create(admin)
    assert NEW["password"] not in response.text
    page = admin.get(LIST)
    assert "Webmaster" in page.text
    assert 'role="status"' in page.text
    assert NEW["password"] not in page.text


# --- changing Role ------------------------------------------------------------

def test_role_change_applies_on_the_next_request(client_as):
    admin = client_as("admin")
    editor = client_as("editor")
    assert editor.get(LIST).status_code == 403
    response = post(admin, f"{LIST}/{account_id(EDITOR['email'])}/role", role="admin")
    assert response.status_code == 303
    assert editor.get(LIST).status_code == 200  # same session, next request
    post(admin, f"{LIST}/{account_id(EDITOR['email'])}/role", role="editor")
    assert editor.get(LIST).status_code == 403


def test_a_bad_role_value_changes_nothing(client_as):
    admin = client_as("admin")
    response = post(admin, f"{LIST}/{account_id(EDITOR['email'])}/role", role="root")
    assert response.status_code == 400
    assert db_rows("select role from accounts where email = ?", EDITOR["email"]) == [("editor",)]


# --- setting a password ---------------------------------------------------------

def test_set_password_replaces_the_old_one_and_never_echoes_it(client_as):
    admin = client_as("admin")
    response = post(admin, f"{LIST}/{account_id(EDITOR['email'])}/password",
                    password="handover-pw-2027")
    assert response.status_code == 303
    assert "handover-pw-2027" not in response.text
    assert "handover-pw-2027" not in admin.get(LIST).text
    assert sign_in_fresh(EDITOR["email"], EDITOR["password"])[1].status_code == 401
    assert sign_in_fresh(EDITOR["email"], "handover-pw-2027")[1].status_code == 303
    stored = db_rows("select password_hash from accounts where email = ?", EDITOR["email"])
    assert stored[0][0].startswith("$argon2")


def test_a_blank_password_is_refused_and_the_old_one_still_works(client_as):
    admin = client_as("admin")
    response = post(admin, f"{LIST}/{account_id(EDITOR['email'])}/password", password="")
    assert response.status_code == 400
    assert sign_in_fresh(EDITOR["email"], EDITOR["password"])[1].status_code == 303


# --- deactivating and reactivating ----------------------------------------------------

def test_deactivated_account_cannot_sign_in_and_gets_the_generic_message(client_as):
    post(client_as("admin"), f"{LIST}/{account_id(EDITOR['email'])}/deactivate")
    c, response = sign_in_fresh(EDITOR["email"], EDITOR["password"])
    assert response.status_code == 401
    _, wrong = sign_in_fresh(EDITOR["email"], "not-the-password")
    strip = lambda html: re.sub(r'name="csrf_token"\s+value="[^"]+"', "", html)
    assert strip(wrong.text) == strip(response.text)
    assert "wrong email or password" in response.text.lower()


def test_an_already_signed_in_session_is_sent_to_sign_in_after_deactivation(client_as):
    editor = client_as("editor")
    assert editor.get("/admin").status_code == 200
    post(client_as("admin"), f"{LIST}/{account_id(EDITOR['email'])}/deactivate")
    response = editor.get("/admin", follow_redirects=False)
    assert response.status_code in (302, 303)
    assert response.headers["location"] == "/login"


def test_deactivating_deletes_nothing(client_as):
    before = db_rows("select id, email, display_name, role from accounts"
                     " where email = ?", EDITOR["email"])
    admin = client_as("admin")
    post(admin, f"{LIST}/{account_id(EDITOR['email'])}/deactivate")
    after = db_rows("select id, email, display_name, role from accounts"
                    " where email = ?", EDITOR["email"])
    assert after == before
    page = admin.get(LIST).text
    assert "Social Chair" in page and EDITOR["email"] in page
    assert "deactivated" in page.lower()


def test_reactivating_lets_the_account_sign_in_again(client_as):
    admin = client_as("admin")
    post(admin, f"{LIST}/{account_id(EDITOR['email'])}/deactivate")
    response = post(admin, f"{LIST}/{account_id(EDITOR['email'])}/reactivate")
    assert response.status_code == 303
    assert sign_in_fresh(EDITOR["email"], EDITOR["password"])[1].status_code == 303


def test_a_deactivated_accounts_published_post_is_still_in_the_export(
        client_as, tmp_path, monkeypatch):
    from app.cli import main

    editor = client_as("editor")
    post(editor, "/admin/posts", token_from="/admin/posts/new", title="Study Hall tonight",
         body="8pm in Hayes 311.")
    post_id = db_rows("select id from posts")[0][0]
    post(editor, f"/admin/posts/{post_id}/publish", token_from="/admin/posts")
    post(client_as("admin"), f"{LIST}/{account_id(EDITOR['email'])}/deactivate")
    assert db_rows("select active from accounts where email = ?", EDITOR["email"]) == [(0,)]

    monkeypatch.setattr(settings, "SITE", tmp_path / "site")
    assert main(["publish"]) == 0
    files = {f.name: f.read_text() for f in (tmp_path / "site" / "posts").glob("*.html")}
    posts = {name: html for name, html in files.items() if name != "index.html"}
    assert len(posts) == 1
    assert "8pm in Hayes 311." in next(iter(posts.values()))
    assert "Study Hall tonight" in (tmp_path / "site" / "index.html").read_text()


# --- the last active Admin -------------------------------------------------------------

def test_the_last_active_admin_cannot_be_deactivated(client_as):
    admin = client_as("admin")
    response = post(admin, f"{LIST}/{only_admin_id()}/deactivate")
    assert response.status_code == 400
    assert "last" in response.text.lower()
    assert db_rows("select role, active from accounts where email = 'admin@example.test'") == [("admin", 1)]
    assert admin.get(LIST).status_code == 200


def test_the_last_active_admin_cannot_be_changed_to_editor(client_as):
    admin = client_as("admin")
    response = post(admin, f"{LIST}/{only_admin_id()}/role", role="editor")
    assert response.status_code == 400
    assert "last" in response.text.lower()
    assert db_rows("select role, active from accounts where email = 'admin@example.test'") == [("admin", 1)]


def test_with_two_admins_either_can_be_demoted_or_deactivated(client_as):
    admin = client_as("admin")
    post(admin, f"{LIST}/{account_id(EDITOR['email'])}/role", role="admin")
    assert post(admin, f"{LIST}/{only_admin_id()}/role", role="editor").status_code == 303
    # now the Social Chair is the only active Admin again
    other = account_id(EDITOR["email"])
    assert post(client_as_second(), f"{LIST}/{other}/deactivate").status_code == 400


def client_as_second():
    c, _ = sign_in_fresh(EDITOR["email"], EDITOR["password"])
    return c


def test_a_deactivated_admin_does_not_count_as_active(client_as):
    admin = client_as("admin")
    post(admin, f"{LIST}/{account_id(EDITOR['email'])}/role", role="admin")
    post(admin, f"{LIST}/{account_id(EDITOR['email'])}/deactivate")
    response = post(admin, f"{LIST}/{only_admin_id()}/deactivate")
    assert response.status_code == 400


# --- every action shows a message --------------------------------------------------------

def status_message(html):
    found = re.search(r'<p role="status">(.*?)</p>', html, re.S)
    return found.group(1) if found else None


def alert_message(html):
    found = re.search(r'<p role="alert">(.*?)</p>', html, re.S)
    return found.group(1) if found else None


def editor_url(action):
    return f"{LIST}/{account_id(EDITOR['email'])}/{action}"


def test_each_successful_action_is_followed_by_a_success_message(client_as):
    admin = client_as("admin")
    actions = [
        (LIST, NEW, "Webmaster"),
        (editor_url("role"), {"role": "admin"}, "Social Chair"),
        (editor_url("password"), {"password": "handover-pw-2027"}, "Social Chair"),
        (editor_url("deactivate"), {}, "Social Chair"),
        (editor_url("reactivate"), {}, "Social Chair"),
    ]
    for path, data, name in actions:
        response = post(admin, path, **data)
        assert response.status_code == 303, path
        page = admin.get(LIST).text
        message = status_message(page)
        assert message and name in message, (path, message)
        assert alert_message(page) is None, path
        assert "handover-pw-2027" not in page and NEW["password"] not in page
        assert status_message(admin.get(LIST).text) is None  # shown once, then cleared


def test_each_refused_action_shows_an_error_message(client_as):
    admin = client_as("admin")
    admin_id = only_admin_id()
    refused = [
        (LIST, {**NEW, "email": EDITOR["email"]}, 400),                 # duplicate email
        (f"{LIST}/{admin_id}/role", {"role": "editor"}, 400),           # last Admin
        (editor_url("password"), {"password": ""}, 400),                # blank password
        (f"{LIST}/{admin_id}/deactivate", {}, 400),                     # last Admin
        (f"{LIST}/9999/reactivate", {}, 404),                           # unknown Account
    ]
    for path, data, status in refused:
        response = post(admin, path, **data)
        assert response.status_code == status, path
        message = alert_message(response.text)
        assert message and message.strip(), path
        assert status_message(response.text) is None, path


# --- who may reach it ---------------------------------------------------------------------

ADMIN_ACTIONS = [
    ("get", LIST), ("post", LIST), ("post", f"{LIST}/1/role"),
    ("post", f"{LIST}/1/password"), ("post", f"{LIST}/1/deactivate"),
    ("post", f"{LIST}/1/reactivate"),
]


def test_an_editor_gets_403_on_every_accounts_url_and_nothing_changes(client_as):
    editor = client_as("editor")
    token = csrf_token(editor, "/admin")
    snapshot = db_rows("select * from accounts order by id")
    for method, path in ADMIN_ACTIONS:
        response = (editor.get(path) if method == "get" else
                    editor.post(path, data={"csrf_token": token, **NEW}))
        assert response.status_code == 403, (method, path)
        assert "permission" in response.text.lower()
    assert db_rows("select * from accounts order by id") == snapshot


def test_an_anonymous_request_to_accounts_redirects_to_sign_in(client):
    for method, path in ADMIN_ACTIONS:
        response = (client.get(path, follow_redirects=False) if method == "get" else
                    client.post(path, data=NEW, follow_redirects=False))
        assert response.status_code in (302, 303), (method, path)
        assert response.headers["location"] == "/login"


def test_accounts_actions_are_rejected_without_a_csrf_token(client_as):
    admin = client_as("admin")
    editor_id = account_id(EDITOR["email"])
    snapshot = db_rows("select * from accounts order by id")
    for path, data in [(LIST, NEW), (f"{LIST}/{editor_id}/role", {"role": "admin"}),
                       (f"{LIST}/{editor_id}/password", {"password": "x-new-pw"}),
                       (f"{LIST}/{editor_id}/deactivate", {}),
                       (f"{LIST}/{editor_id}/reactivate", {})]:
        for token in (None, "forged"):
            payload = dict(data) if token is None else {**data, "csrf_token": token}
            assert admin.post(path, data=payload).status_code == 403, path
    assert db_rows("select * from accounts order by id") == snapshot


def test_an_unknown_account_id_is_a_404(client_as):
    admin = client_as("admin")
    assert post(admin, f"{LIST}/9999/deactivate").status_code == 404


# --- code-review fixes ---------------------------------------------------------------------

def test_the_last_admin_check_runs_while_holding_the_write_lock(client_as, monkeypatch):
    """Two Admins demoting each other at once must not both pass the check.

    At the moment the guard counts the other Admins, a competing write from a second
    connection must be refused because the first already holds the write lock.
    """
    from app import accounts

    admin = client_as("admin")
    post(admin, f"{LIST}/{account_id(EDITOR['email'])}/role", role="admin")  # two Admins
    real_count = accounts._other_active_admins
    competing = []

    def count_then_try_a_competing_write(conn, account_id):
        rival = sqlite3.connect(settings.DATABASE_PATH, timeout=0)
        try:
            rival.execute("update accounts set role = 'editor' where email = ?",
                          (EDITOR["email"],))
            rival.commit()
            competing.append("write succeeded")
        except sqlite3.OperationalError:
            competing.append("write blocked")
        finally:
            rival.close()
        return real_count(conn, account_id)

    monkeypatch.setattr(accounts, "_other_active_admins", count_then_try_a_competing_write)
    post(admin, f"{LIST}/{account_id(EDITOR['email'])}/deactivate")  # allowed: Co-VP remains
    post(admin, f"{LIST}/{only_admin_id()}/role", role="editor")      # refused: last Admin
    assert competing == ["write blocked", "write blocked"]


def test_two_creates_racing_on_one_email_give_a_400_not_a_500(client_as, monkeypatch):
    from app import accounts

    class RivalCreatesFirst:
        """Hashing happens after the duplicate check, so a rival insert lands in between."""

        def __init__(self, real):
            self.real = real

        def hash(self, password):
            with sqlite3.connect(settings.DATABASE_PATH) as rival:
                rival.execute("insert into accounts (email, display_name, password_hash, role)"
                              " values (?, 'Rival', 'x', 'editor')", (NEW["email"],))
            return self.real.hash(password)

    admin = client_as("admin")
    monkeypatch.setattr(accounts, "_hasher", RivalCreatesFirst(accounts._hasher))
    response = create(admin)
    assert response.status_code == 400
    assert "already" in response.text.lower()
    assert db_rows("select display_name from accounts where email = ?", NEW["email"]) == [("Rival",)]


def test_an_account_id_too_big_for_the_database_is_a_404_on_every_action(client_as):
    admin = client_as("admin")
    huge = 99999999999999999999
    for action, data in [("role", {"role": "editor"}), ("password", {"password": "new-pw-1"}),
                         ("deactivate", {}), ("reactivate", {})]:
        response = post(admin, f"{LIST}/{huge}/{action}", **data)
        assert response.status_code == 404, action
        assert "no such account" in response.text.lower()
