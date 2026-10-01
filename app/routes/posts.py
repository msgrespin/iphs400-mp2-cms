"""Console screens for Posts: list, write, edit, publish, delete."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import accounts, content
from app.templating import templates

# require_account comes first so an anonymous POST is sent to sign-in, not
# refused for a missing token.
router = APIRouter(prefix="/admin/posts", dependencies=[Depends(accounts.require_account)])
csrf = [Depends(accounts.require_csrf)]

LIST_URL = "/admin/posts"


def flash(request: Request, message: str) -> None:
    request.session["flash"] = message


def render(request: Request, template: str, status_code: int = 200, **context):
    return templates.TemplateResponse(
        request, template,
        {"title": "Posts", "home_path": "/admin",
         "csrf_token": accounts.csrf_token(request),
         "flash": request.session.pop("flash", ""), **context},
        status_code=status_code)


def found(post_id: int):
    post = content.get_post(post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="No such Post.")
    return post


def form_error(request: Request, template: str, post, title: str, body: str):
    return render(request, template, status_code=400, post=post, form_title=title,
                  form_body=body, error="A Post needs a title.")


@router.get("", response_class=HTMLResponse)
def list_posts(request: Request):
    return render(request, "admin/posts.html", posts=content.list_posts())


@router.get("/new", response_class=HTMLResponse)
def new_post(request: Request):
    return render(request, "admin/post_form.html", post=None, form_title="",
                  form_body="", error="")


@router.post("", dependencies=csrf)
def create_post(request: Request, title: str = Form(""), body: str = Form(""),
                account=Depends(accounts.require_account)):
    try:
        content.create_post(title, body, account["id"])
    except content.EmptyTitle:
        return form_error(request, "admin/post_form.html", None, title, body)
    flash(request, f"Created Draft “{title.strip()}”.")
    return RedirectResponse(LIST_URL, status_code=303)


@router.get("/{post_id}/edit", response_class=HTMLResponse)
def edit_post(request: Request, post_id: int):
    post = found(post_id)
    return render(request, "admin/post_form.html", post=post, form_title=post["title"],
                  form_body=post["body"], error="")


@router.post("/{post_id}", dependencies=csrf)
def save_post(request: Request, post_id: int, title: str = Form(""), body: str = Form("")):
    post = found(post_id)
    try:
        content.update_post(post_id, title, body)
    except content.EmptyTitle:
        return form_error(request, "admin/post_form.html", post, title, body)
    flash(request, f"Saved “{title.strip()}”.")
    return RedirectResponse(LIST_URL, status_code=303)


@router.post("/{post_id}/publish", dependencies=csrf)
def publish_post(request: Request, post_id: int):
    post = found(post_id)
    content.set_status(post_id, "published")
    flash(request, f"Published “{post['title']}”. It reaches Visitors at the next Go live.")
    return RedirectResponse(LIST_URL, status_code=303)


@router.post("/{post_id}/unpublish", dependencies=csrf)
def unpublish_post(request: Request, post_id: int):
    post = found(post_id)
    content.set_status(post_id, "draft")
    flash(request, f"Set “{post['title']}” back to Draft.")
    return RedirectResponse(LIST_URL, status_code=303)


@router.get("/{post_id}/delete", response_class=HTMLResponse)
def confirm_delete(request: Request, post_id: int):
    return render(request, "admin/post_delete.html", post=found(post_id))


@router.post("/{post_id}/delete", dependencies=csrf)
def delete_post(request: Request, post_id: int):
    post = found(post_id)
    content.delete_post(post_id)
    flash(request, f"Deleted “{post['title']}”.")
    return RedirectResponse(LIST_URL, status_code=303)
