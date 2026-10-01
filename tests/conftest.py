"""Shared test fixtures.

`client` gives you the app. `client_as(role)` gives you a client that is logged
in as a seeded Account of that role, with CSRF protection in place:

    def test_editor_cannot_manage_users(client_as):
        assert client_as("editor").get("/admin/users").status_code in (302, 403)

Every test runs against its own temporary database, seeded with the demo
Accounts below.
"""
from __future__ import annotations

import os
import re

import pytest
from fastapi.testclient import TestClient

# Keep a developer's real .env out of the tests; must run before app.settings loads.
os.environ.setdefault("CMS_ENV_FILE", os.devnull)

from app import settings  # noqa: E402
from app.main import create_app

# Matches scripts/seed_demo.py. Passwords come from the environment there; in
# tests they are fixed and meaningless.
DEMO_USERS = {
    "admin": {"email": "admin@example.test", "password": "test-admin-pw"},
    "editor": {"email": "editor@example.test", "password": "test-editor-pw"},
}


def csrf_token(client: TestClient, path: str = "/login") -> str:
    """Fetch a page and return the CSRF token from its form."""
    html = client.get(path).text
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    assert match, f"No CSRF token found on {path}"
    return match.group(1)


@pytest.fixture(autouse=True)
def temp_database(tmp_path, monkeypatch):
    """Give each test its own database, seeded with the demo Accounts."""
    from argon2 import PasswordHasher

    from app import accounts

    # Cheap argon2 settings keep the suite fast; hashes are still real argon2.
    monkeypatch.setattr(accounts, "_hasher",
                        PasswordHasher(time_cost=1, memory_cost=8, parallelism=1))
    monkeypatch.setattr(accounts, "_DUMMY_HASH", accounts._hasher.hash("x"))
    monkeypatch.setattr(settings, "DATABASE_PATH", tmp_path / "test.db")
    accounts.init_db()
    accounts.seed_demo_accounts(DEMO_USERS["admin"]["password"],
                                DEMO_USERS["editor"]["password"])


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture
def client_as():
    """Return a factory: client_as("editor") -> a logged-in TestClient."""

    def _login(role: str) -> TestClient:
        user = DEMO_USERS[role]
        c = TestClient(create_app())
        response = c.post("/login", data={"email": user["email"],
                                          "password": user["password"],
                                          "csrf_token": csrf_token(c)},
                          follow_redirects=False)
        assert response.status_code in (302, 303), (
            f"Login as {role} failed with {response.status_code}")
        return c

    return _login
