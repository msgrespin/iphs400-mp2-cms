"""Console dashboard and the one content list of Posts and Pages."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app import accounts, content
from app.templating import templates

router = APIRouter(prefix="/admin", dependencies=[Depends(accounts.require_account)])


def render(request: Request, template: str, title: str, **context):
    return templates.TemplateResponse(
        request, template,
        {"title": title, "home_path": "/admin",
         "csrf_token": accounts.csrf_token(request),
         "flash": request.session.pop("flash", ""), **context})


@router.get("", response_class=HTMLResponse)
def dashboard(request: Request):
    return render(request, "admin/dashboard.html", "Dashboard", counts=content.counts())


@router.get("/content", response_class=HTMLResponse)
def content_list(request: Request, status: str = "", type: str = ""):
    status = status if status in ("draft", "published") else ""
    kind = type if type in ("post", "page") else ""
    return render(request, "admin/content.html", "Content",
                  items=content.list_items(status or None, kind or None),
                  status=status, kind=kind)
