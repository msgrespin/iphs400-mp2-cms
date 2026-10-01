"""Console screens for Pages: list, edit, and (Admin only) create, status, delete.

Anyone signed in may list Pages, edit a Page's body, and preview. Creating,
deleting, and changing status go through accounts.require_admin, so an Editor
requesting them by direct URL gets the "no permission" screen.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import accounts, content, markdown
from app.templating import templates

# require_account comes first so an anonymous POST is sent to sign-in, not
# refused for a missing token. Admin-only routes check the Role before the token.
router = APIRouter(prefix="/admin/pages", dependencies=[Depends(accounts.require_account)])
csrf = [Depends(accounts.require_csrf)]
admin_only = [Depends(accounts.require_admin), *csrf]

LIST_URL = "/admin/pages"


def flash(request: Request, message: str) -> None:
    request.session["flash"] = message


def render(request: Request, template: str, account, status_code: int = 200, **context):
    return templates.TemplateResponse(
        request, template,
        {"title": "Pages", "home_path": "/admin", "account": account,
         "csrf_token": accounts.csrf_token(request),
         "flash": request.session.pop("flash", ""), **context},
        status_code=status_code)


def list_screen(request: Request, account, error: str = "", status_code: int = 200):
    return render(request, "admin/pages.html", account, status_code=status_code,
                  pages=content.list_pages(), error=error)


def found(page_id: int):
    page = content.get_page(page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="No such Page.")
    return page


def form_screen(request: Request, account, page, title: str, body: str,
                error: str = "", status_code: int = 200):
    return render(request, "admin/page_form.html", account, status_code=status_code,
                  page=page, form_title=title, form_body=body, error=error)


@router.get("", response_class=HTMLResponse)
def list_pages(request: Request, account=Depends(accounts.require_account)):
    return list_screen(request, account)


@router.get("/new", response_class=HTMLResponse, dependencies=[Depends(accounts.require_admin)])
def new_page(request: Request, account=Depends(accounts.require_account)):
    return form_screen(request, account, None, "", "")


@router.post("", dependencies=admin_only)
def create_page(request: Request, title: str = Form(""), body: str = Form(""),
                account=Depends(accounts.require_account)):
    try:
        content.create_page(title, body, account["id"])
    except content.EmptyTitle as problem:
        return form_screen(request, account, None, title, body, str(problem), 400)
    flash(request, f"Created Draft Page “{title.strip()}”.")
    return RedirectResponse(LIST_URL, status_code=303)


@router.post("/preview", response_class=HTMLResponse, dependencies=csrf)
def preview_page(request: Request, title: str = Form(""), body: str = Form(""),
                 account=Depends(accounts.require_account)):
    """Show the sanitized rendering of the form's text. Nothing is saved."""
    return render(request, "admin/post_preview.html", account, preview_title=title.strip(),
                  rendered=markdown.render(body), css_path="/style.css")


@router.get("/{page_id}/edit", response_class=HTMLResponse)
def edit_page(request: Request, page_id: int, account=Depends(accounts.require_account)):
    page = found(page_id)
    return form_screen(request, account, page, page["title"], page["body"])


@router.post("/{page_id}", dependencies=csrf)
def save_page(request: Request, page_id: int, title: str = Form(""), body: str = Form(""),
              account=Depends(accounts.require_account)):
    page = found(page_id)
    try:
        content.update_page(account, page_id, title, body)
    except content.EmptyTitle as problem:
        return form_screen(request, account, page, title, body, str(problem), 400)
    flash(request, f"Saved “{found(page_id)['title']}”.")
    return RedirectResponse(LIST_URL, status_code=303)


@router.post("/{page_id}/publish", dependencies=admin_only)
def publish_page(request: Request, page_id: int):
    page = found(page_id)
    content.set_page_status(page_id, "published")
    flash(request, f"Published “{page['title']}”. It reaches Visitors at the next Go live.")
    return RedirectResponse(LIST_URL, status_code=303)


@router.post("/{page_id}/unpublish", dependencies=admin_only)
def unpublish_page(request: Request, page_id: int, account=Depends(accounts.require_account)):
    page = found(page_id)
    try:
        content.set_page_status(page_id, "draft")
    except content.HomeProtected as problem:
        return list_screen(request, account, str(problem), 400)
    flash(request, f"Set “{page['title']}” back to Draft.")
    return RedirectResponse(LIST_URL, status_code=303)


@router.get("/{page_id}/delete", response_class=HTMLResponse,
            dependencies=[Depends(accounts.require_admin)])
def confirm_delete(request: Request, page_id: int, account=Depends(accounts.require_account)):
    page = found(page_id)
    if page["is_home"]:
        return list_screen(request, account, "Home cannot be deleted.", 400)
    return render(request, "admin/page_delete.html", account, page=page)


@router.post("/{page_id}/delete", dependencies=admin_only)
def delete_page(request: Request, page_id: int, account=Depends(accounts.require_account)):
    page = found(page_id)
    try:
        content.delete_page(page_id)
    except content.HomeProtected as problem:
        return list_screen(request, account, str(problem), 400)
    flash(request, f"Deleted “{page['title']}”.")
    return RedirectResponse(LIST_URL, status_code=303)
