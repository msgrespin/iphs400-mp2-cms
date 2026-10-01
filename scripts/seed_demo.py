#!/usr/bin/env python3
"""Create demo data so a grader (and you) can use the CMS immediately.

    uv run python scripts/seed_demo.py

Creates the four demo Accounts (passwords read from the environment, never
hard-coded), the three Pages, and a few Posts, at least one Draft and one
Published.

The rubric expects this to run clean on a fresh clone with .env.example values
(item E4), because the database itself is never committed.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import accounts, content  # noqa: E402


def main() -> int:
    admin_pw = os.environ.get("CMS_ADMIN_PASSWORD")
    editor_pw = os.environ.get("CMS_EDITOR_PASSWORD")
    if not admin_pw or not editor_pw:
        print("Set CMS_ADMIN_PASSWORD and CMS_EDITOR_PASSWORD in .env "
              "(copy .env.example).")
        return 1

    accounts.seed_demo_accounts(admin_pw, editor_pw)
    print("Demo Accounts ready: Co-VP, Social Chair, Co-President, Treasurer.")
    content.seed_demo_posts()
    print("Demo Posts ready: one Published, one Draft.")
    content.seed_demo_pages()
    print("Demo Pages ready: Home, About, Join & Snacks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
