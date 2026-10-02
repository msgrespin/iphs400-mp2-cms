"""T05: Console dashboard and content list."""
import re

import pytest

from app import content
from tests.conftest import csrf_token
from tests.test_t02 import act, at, create, newest_id
from tests.test_t04 import new_page, publish_page


def run_seed():
    """The demo Pages and Posts, made in this test's own database."""
    content.seed_demo_pages()
    content.seed_demo_posts()


DASHBOARD = "/admin"
CONTENT = "/admin/content"


def counts(c):
    """The three dashboard numbers, read from the screen an Officer sees."""
    html = c.get(DASHBOARD).text

    def number(label):
        match = re.search(rf"{label}\D*?(\d+)", html)
        assert match, f"the dashboard should show a count for {label!r}"
        return int(match.group(1))

    return (number("Draft Posts"), number("Published Posts"), number("Pages"))


def rows_of(html):
    """Each content-list row as its text, in the order shown."""
    body = re.search(r"<tbody>(.*?)</tbody>", html, re.DOTALL)
    assert body, "the content list should be a table"
    return [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", row)).strip()
            for row in re.findall(r"<tr>.*?</tr>", body.group(1), re.DOTALL)]


def titles(html):
    return re.findall(r'<a href="/admin/(?:posts|pages)/\d+/edit">([^<]*)</a>', html)


@pytest.fixture
def seeded(client_as):
    """An Editor with a Published Post, a Draft Post, and the three Pages."""
    run_seed()
    return client_as("editor")


# --- dashboard ------------------------------------------------------------

def test_dashboard_shows_counts_of_draft_posts_published_posts_and_pages(client_as):
    run_seed()
    c = client_as("editor")
    drafts, published, pages = counts(c)
    assert (drafts, published, pages) == (1, 1, 3)


def test_counts_follow_a_post_created_published_unpublished_and_deleted(client_as):
    run_seed()
    c = client_as("editor")
    before = counts(c)

    create(c, title="Counting Post")
    post_id = newest_id(c)
    assert counts(c) == (before[0] + 1, before[1], before[2])

    act(c, post_id, "publish")
    assert counts(c) == (before[0], before[1] + 1, before[2])

    act(c, post_id, "unpublish")
    assert counts(c) == (before[0] + 1, before[1], before[2])

    token = csrf_token(c, f"/admin/posts/{post_id}/delete")
    c.post(f"/admin/posts/{post_id}/delete", data={"csrf_token": token})
    assert counts(c) == before


def test_pages_count_grows_with_a_new_page_whether_draft_or_published(client_as):
    c = client_as("admin")
    before = counts(c)[2]
    new_page(c, title="Meetings")
    assert counts(c)[2] == before + 1


@pytest.mark.parametrize("role", ["admin", "editor"])
@pytest.mark.parametrize("path", [DASHBOARD, CONTENT])
def test_editor_and_admin_can_open_dashboard_and_content_list(client_as, role, path):
    assert client_as(role).get(path).status_code == 200


@pytest.mark.parametrize("path", [DASHBOARD, CONTENT, f"{CONTENT}?status=draft"])
def test_anonymous_dashboard_and_content_list_redirect_to_sign_in(client, path):
    response = client.get(path, follow_redirects=False)
    assert response.status_code in (302, 303)
    assert response.headers["location"] == "/login"


# --- content list ---------------------------------------------------------

def test_content_list_shows_posts_and_pages_together_with_their_details(seeded):
    html = seeded.get(CONTENT).text
    shown = rows_of(html)
    assert len(shown) == 5
    assert any("Study Hall tonight" in r and "Post" in r and "Published" in r
               and "Social Chair" in r for r in shown)
    assert any("Snack request form is open" in r and "Draft" in r for r in shown)
    assert any("About" in r and "Page" in r and "Co-VP" in r for r in shown)
    assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", shown[0]), "last-updated time"


def test_each_row_links_to_that_items_editor(seeded):
    html = seeded.get(CONTENT).text
    for kind in ("posts", "pages"):
        links = re.findall(rf'href="(/admin/{kind}/\d+/edit)"', html)
        assert links, f"expected {kind} rows to link to their editors"
        assert seeded.get(links[0]).status_code == 200


def test_list_is_most_recently_updated_first(client_as, monkeypatch):
    run_seed()
    c = client_as("editor")
    monkeypatch.setattr(content, "now", at("2030-01-01T12:00:00"))
    create(c, title="Zebra newest")
    assert titles(c.get(CONTENT).text)[0] == "Zebra newest"
    # Editing an older Post moves it to the top.
    old = [i for i in re.findall(r"/admin/posts/(\d+)/edit", c.get("/admin/posts").text)
           if int(i) != newest_id(c)][0]
    monkeypatch.setattr(content, "now", at("2030-01-02T12:00:00"))
    token = csrf_token(c, f"/admin/posts/{old}/edit")
    c.post(f"/admin/posts/{old}", data={"title": "Edited later", "body": "x",
                                         "csrf_token": token})
    assert titles(c.get(CONTENT).text)[0] == "Edited later"


def test_filter_by_status(seeded):
    drafts = rows_of(seeded.get(f"{CONTENT}?status=draft").text)
    assert drafts and all("Draft" in r for r in drafts)
    published = rows_of(seeded.get(f"{CONTENT}?status=published").text)
    assert published and all("Published" in r for r in published)
    assert len(drafts) + len(published) == 5


def test_filter_by_type(seeded):
    posts = rows_of(seeded.get(f"{CONTENT}?type=post").text)
    assert len(posts) == 2 and all(" Post " in f" {r} " for r in posts)
    pages = rows_of(seeded.get(f"{CONTENT}?type=page").text)
    assert len(pages) == 3


def test_filters_combine(seeded):
    rows = rows_of(seeded.get(f"{CONTENT}?status=draft&type=post").text)
    assert len(rows) == 1 and "Snack request form is open" in rows[0]
    rows = rows_of(seeded.get(f"{CONTENT}?status=published&type=page").text)
    assert len(rows) == 3


def test_a_filter_that_matches_nothing_says_so_with_200(seeded):
    response = seeded.get(f"{CONTENT}?status=draft&type=page")
    assert response.status_code == 200
    assert "nothing here" in response.text.lower()
    assert "<tbody>" not in response.text


def test_unknown_filter_values_are_ignored(seeded):
    response = seeded.get(f"{CONTENT}?status=bogus&type=nonsense")
    assert response.status_code == 200
    assert len(rows_of(response.text)) == 5


def test_script_in_a_title_is_shown_as_text_in_the_list(client_as):
    c = client_as("editor")
    create(c, title="<script>alert(1)</script>")
    html = c.get(CONTENT).text
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_publishing_a_page_shows_up_in_the_filtered_list(client_as):
    c = client_as("admin")
    new_page(c, title="Meetings")
    assert any("Meetings" in r for r in rows_of(c.get(f"{CONTENT}?status=draft").text))
    page_id = int(re.search(r'/admin/pages/(\d+)/edit">Meetings',
                            c.get(CONTENT).text).group(1))
    publish_page(c, page_id)
    assert any("Meetings" in r for r in rows_of(c.get(f"{CONTENT}?status=published").text))


# --- navigation on every console screen -----------------------------------

def console_nav(html):
    nav = re.search(r"<nav.*?</nav>", html, re.DOTALL)
    assert nav, "every console screen needs a <nav>"
    return nav.group(0)


def assert_has_console_nav(html, position):
    nav = console_nav(html)
    for href in ("/admin", CONTENT, "/admin/posts/new"):
        assert f'href="{href}"' in nav, f"nav should link to {href}"
    assert "/logout" in nav and "Sign out" in nav
    assert position in nav


def test_every_console_screen_has_the_same_navigation_and_viewport_tag(client_as):
    run_seed()
    c = client_as("editor")
    post_id = newest_id(c)
    page_id = int(re.search(r"/admin/pages/(\d+)/edit", c.get("/admin/pages").text).group(1))
    screens = [DASHBOARD, CONTENT, "/admin/posts", "/admin/posts/new",
               f"/admin/posts/{post_id}/edit", f"/admin/posts/{post_id}/delete",
               "/admin/pages", f"/admin/pages/{page_id}/edit"]
    for path in screens:
        response = c.get(path)
        assert response.status_code == 200, path
        assert_has_console_nav(response.text, "Social Chair")
        assert 'name="viewport"' in response.text and "width=device-width" in response.text


def test_admin_only_screens_and_confirmations_have_the_navigation(client_as):
    run_seed()
    c = client_as("admin")
    new_page(c, title="Meetings")
    page_id = int(re.search(r'/admin/pages/(\d+)/edit">Meetings',
                            c.get(CONTENT).text).group(1))
    for path in ("/admin/pages/new", f"/admin/pages/{page_id}/delete"):
        response = c.get(path)
        assert response.status_code == 200, path
        assert_has_console_nav(response.text, "Co-VP")


def test_no_permission_and_preview_screens_have_the_navigation(client_as):
    c = client_as("editor")
    refused = c.get("/admin/pages/new")
    assert refused.status_code == 403
    assert_has_console_nav(refused.text, "Social Chair")

    token = csrf_token(c, "/admin/posts/new")
    preview = c.post("/admin/posts/preview",
                     data={"title": "T", "body": "hi", "csrf_token": token})
    assert_has_console_nav(preview.text, "Social Chair")


def test_sign_in_screen_has_no_console_navigation(client):
    html = client.get("/login").text
    assert "/admin/content" not in html


def test_signing_out_from_the_navigation_works(client_as):
    c = client_as("admin")
    html = c.get(DASHBOARD).text
    token = re.search(r'name="csrf_token"\s+value="([^"]+)"', console_nav(html)).group(1)
    response = c.post("/logout", data={"csrf_token": token}, follow_redirects=False)
    assert response.status_code in (302, 303)
    assert c.get(DASHBOARD, follow_redirects=False).status_code in (302, 303)


def test_the_local_public_preview_has_no_console_navigation(client_as):
    run_seed()
    c = client_as("admin")
    assert "/admin" not in c.get("/").text


def test_sign_out_from_the_no_permission_screen_works(client_as):
    c = client_as("editor")
    refused = c.get("/admin/pages/new")
    token = re.search(r'name="csrf_token"\s+value="([^"]+)"', console_nav(refused.text)).group(1)
    assert c.post("/logout", data={"csrf_token": token},
                  follow_redirects=False).status_code in (302, 303)
