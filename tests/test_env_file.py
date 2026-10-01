"""The app loads .env itself; real environment variables win over it."""
import os
import subprocess
import sys
from pathlib import Path

from app import envfile

ROOT = Path(__file__).resolve().parents[1]


def run(code, env_file, **env):
    full = {k: v for k, v in os.environ.items() if k != "CMS_SITE_TITLE"}
    full.update(CMS_ENV_FILE=str(env_file), **env)
    return subprocess.run([sys.executable, "-c", code], env=full, cwd=ROOT,
                          capture_output=True, text=True)


def test_parse_handles_quotes_comments_blanks_and_empty_values():
    text = '# c\n\nA="two words"\nB=plain\nC=\nexport D=\'x\'\n'
    assert envfile.parse(text) == {"A": "two words", "B": "plain", "C": "", "D": "x"}


def test_settings_reads_the_site_title_from_dot_env(tmp_path):
    f = tmp_path / ".env"
    f.write_text('CMS_SITE_TITLE="AWM at Kenyon"\n')
    r = run("from app import settings; print(settings.SITE_TITLE)", f)
    assert r.stdout.strip() == "AWM at Kenyon", r.stderr


def test_real_environment_wins_over_dot_env(tmp_path):
    f = tmp_path / ".env"
    f.write_text("CMS_SITE_TITLE=From file\n")
    r = run("from app import settings; print(settings.SITE_TITLE)", f,
            CMS_SITE_TITLE="From shell")
    assert r.stdout.strip() == "From shell", r.stderr


def test_missing_dot_env_falls_back_to_the_default(tmp_path):
    r = run("from app import settings; print(settings.SITE_TITLE)", tmp_path / "nope")
    assert r.stdout.strip() == "My CMS", r.stderr


def test_seed_demo_gets_its_passwords_from_dot_env(tmp_path):
    f = tmp_path / ".env"
    f.write_text("CMS_ADMIN_PASSWORD=a-pw\nCMS_EDITOR_PASSWORD=e-pw\n")
    env = {k: v for k, v in os.environ.items() if not k.startswith("CMS_")}
    env.update(CMS_ENV_FILE=str(f), CMS_DATABASE=str(tmp_path / "s.db"))
    r = subprocess.run([sys.executable, str(ROOT / "scripts/seed_demo.py")],
                       env=env, cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
