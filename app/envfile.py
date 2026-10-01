"""Load KEY=VALUE pairs from a .env file into os.environ.

Real environment variables always win: a name that is already set is left
alone. No dependency; the format is the small subset .env.example uses.
"""
from __future__ import annotations

import os
from pathlib import Path


def parse(text: str) -> dict[str, str]:
    values = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def load(path: Path | str) -> None:
    try:
        text = Path(path).read_text()
    except OSError:
        return
    for key, value in parse(text).items():
        os.environ.setdefault(key, value)
