"""Admin pages sit at different depths, so a bare `style.css` link would 404."""
import re
from urllib.parse import urljoin

from tests.conftest import csrf_token


def test_every_admin_page_links_a_stylesheet_that_resolves_to_slash_style_css(client_as):
    admin = client_as("admin")
    admin.post("/admin/posts", data={"title": "Styled", "body": "Hello",
                                     "csrf_token": csrf_token(admin, "/admin/posts/new")})
    paths = ["/admin/content", "/admin/accounts", "/admin/posts/1/edit"]
    for path in paths:
        html = admin.get(path).text
        href = re.search(r'<link rel="stylesheet" href="([^"]+)"', html)
        assert href, f"{path} should link a stylesheet"
        assert urljoin(f"http://testserver{path}", href.group(1)) == "http://testserver/style.css", path
