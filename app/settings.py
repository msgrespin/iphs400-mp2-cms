"""Configuration, read from the environment (never hard-code secrets)."""
from __future__ import annotations

import os
from pathlib import Path

from app import envfile

ROOT = Path(__file__).resolve().parents[1]
# .env fills in anything the real environment leaves unset. CMS_ENV_FILE
# points elsewhere (the tests use it to keep a developer's .env out).
envfile.load(os.environ.get("CMS_ENV_FILE", ROOT / ".env"))
TEMPLATES = ROOT / "templates"
SITE = ROOT / "site"

SECRET_KEY = os.environ.get("CMS_SECRET_KEY", "dev-only-not-for-production")
DATABASE_PATH = Path(os.environ.get("CMS_DATABASE", ROOT / "cms.db"))
SITE_TITLE = os.environ.get("CMS_SITE_TITLE", "My CMS")
# Set this to your Pages URL once you deploy, e.g.
# https://yourname.github.io/iphs400-mp2-cms/
BASE_PATH = os.environ.get("CMS_BASE_PATH", "")
