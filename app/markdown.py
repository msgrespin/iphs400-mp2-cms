"""Markdown to sanitized HTML, in one place.

The editor Preview, the local public preview, and the export all call
render(), so nothing can be shown unsanitized. Raw HTML typed into a body is
stripped by the allowlist, images are not on it, and only absolute http(s) and
mailto links survive (a root-absolute link would break the relative-paths rule).
"""
from __future__ import annotations

import nh3
from markdown_it import MarkdownIt

ALLOWED_TAGS = {"p", "br", "strong", "em", "a", "ul", "ol", "li", "blockquote", "code",
                "pre", "h2", "h3", "h4", "hr"}
ALLOWED_SCHEMES = {"http", "https", "mailto"}

_parser = MarkdownIt("commonmark", {"html": True}).disable("image")


def render(body: str) -> str:
    return nh3.clean(
        _parser.render(body),
        tags=ALLOWED_TAGS,
        attributes={"a": {"href"}},
        url_schemes=ALLOWED_SCHEMES,
        url_relative="deny",
    )
