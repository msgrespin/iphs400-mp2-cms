"""T01: Officers sign in and out with a Position's Account."""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import DEMO_USERS, csrf_token

ROOT = Path(__file__).resolve().parents[1]
ADMIN = DEMO_USERS["admin"]


def read_env_example() -> dict[str, str]:
    values = {}
    for line in (ROOT / ".env.example").read_text().splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def run_seed(db_path, env_overrides=None, drop=()):
    env = {**os.environ, **read_env_example(), "CMS_DATABASE": str(db_path),
           "CMS_ENV_FILE": os.devnull}
    env.update(env_overrides or {})
    for name in drop:
        env.pop(name, None)
    return subprocess.run([sys.executable, str(ROOT / "scripts/seed_demo.py")],
                          env=env, capture_output=True, text=True, cwd=ROOT)


def rows(db_path, sql):
    with sqlite3.connect(db_path) as conn:
        return conn.execute(sql).fetchall()


def sign_in(c, email=ADMIN["email"], password=ADMIN["password"], token=None):
    return c.post("/login", data={"email": email, "password": password,
                                  "csrf_token": csrf_token(c) if token is None else token},
                  follow_redirects=False)


# --- seed script ---------------------------------------------------------

def test_env_example_has_demo_password_variables():
    text = (ROOT / ".env.example").read_text()
    assert "CMS_ADMIN_PASSWORD" in text and "CMS_EDITOR_PASSWORD" in text


def test_seed_creates_the_four_accounts(tmp_path):
    db = tmp_path / "seed.db"
    result = run_seed(db)
    assert result.returncode == 0, result.stderr
    got = rows(db, "select email, display_name, role from accounts order by email")
    assert got == [
        ("admin@example.test", "Co-VP", "admin"),
        ("copresident@example.test", "Co-President", "editor"),
        ("editor@example.test", "Social Chair", "editor"),
        ("treasurer@example.test", "Treasurer", "editor"),
    ]


def test_seed_twice_leaves_four_accounts(tmp_path):
    db = tmp_path / "seed.db"
    assert run_seed(db).returncode == 0
    assert run_seed(db).returncode == 0
    assert rows(db, "select count(*) from accounts") == [(4,)]


def test_seed_without_a_password_variable_fails_and_creates_nothing(tmp_path):
    for missing in ("CMS_ADMIN_PASSWORD", "CMS_EDITOR_PASSWORD"):
        db = tmp_path / f"{missing}.db"
        result = run_seed(db, drop=(missing,))
        assert result.returncode != 0
        assert not db.exists() or rows(db, "select count(*) from accounts") == [(0,)]


def test_passwords_are_stored_as_argon2_hashes(tmp_path):
    db = tmp_path / "seed.db"
    env = read_env_example()
    assert run_seed(db).returncode == 0
    hashes = [r[0] for r in rows(db, "select password_hash from accounts")]
    assert hashes and all(h.startswith("$argon2") for h in hashes)
    raw = db.read_bytes()
    assert env["CMS_ADMIN_PASSWORD"].encode() not in raw
    assert env["CMS_EDITOR_PASSWORD"].encode() not in raw


# --- sign in -------------------------------------------------------------

def test_correct_password_signs_in_and_shows_the_position(client):
    response = sign_in(client)
    assert response.status_code in (302, 303)
    assert response.headers["location"] == "/admin"
    page = client.get("/admin")
    assert page.status_code == 200
    assert "Co-VP" in page.text


def test_wrong_password_and_unknown_email_give_the_same_message(client):
    wrong = sign_in(client, password="nope")
    unknown = sign_in(client, email="nobody@example.test")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.text == unknown.text
    assert "wrong email or password" in wrong.text.lower()
    assert client.get("/admin", follow_redirects=False).status_code in (302, 303)


def test_anonymous_admin_redirects_to_sign_in_with_no_console_content(client):
    response = client.get("/admin", follow_redirects=False)
    assert response.status_code in (302, 303)
    assert response.headers["location"] == "/login"
    assert "hello admin" not in response.text.lower()


def test_sign_out_is_a_post_that_ends_the_session(client):
    sign_in(client)
    assert client.get("/logout").status_code == 405
    token = csrf_token(client, "/admin")
    response = client.post("/logout", data={"csrf_token": token},
                           follow_redirects=False)
    assert response.status_code in (302, 303)
    assert client.get("/admin", follow_redirects=False).status_code in (302, 303)


def test_forms_carry_csrf_tokens(client):
    assert 'name="csrf_token"' in client.get("/login").text
    sign_in(client)
    page = client.get("/admin").text
    assert 'action="/logout"' in page and 'name="csrf_token"' in page


def test_sign_in_without_a_valid_token_is_rejected(client):
    client.get("/login")
    for token in ("", "forged"):
        response = sign_in(client, token=token)
        assert response.status_code == 403
    assert client.get("/admin", follow_redirects=False).status_code in (302, 303)


def test_sign_out_without_a_valid_token_changes_nothing(client):
    sign_in(client)
    for token in ("", "forged"):
        assert client.post("/logout", data={"csrf_token": token}).status_code == 403
    assert client.get("/admin").status_code == 200


def test_session_cookie_has_no_expiry(client):
    response = sign_in(client)
    cookies = response.headers.get_list("set-cookie")
    assert cookies
    for cookie in cookies:
        assert "expires" not in cookie.lower()
        assert "max-age" not in cookie.lower()


def test_deactivated_account_cannot_sign_in(client):
    from app import accounts

    accounts.set_active("editor@example.test", False)
    response = sign_in(client, email="editor@example.test",
                       password=DEMO_USERS["editor"]["password"])
    assert response.status_code == 401


def test_client_as_returns_signed_in_clients(client_as):
    assert "Co-VP" in client_as("admin").get("/admin").text
    assert "Social Chair" in client_as("editor").get("/admin").text
