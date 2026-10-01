"""Sign-in, sign-out, and the console front door."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import accounts, settings
from app.templating import templates

router = APIRouter()

WRONG_LOGIN = "Wrong email or password."


def login_page(request: Request, error: str = "", status_code: int = 200):
    return templates.TemplateResponse(
        request, "admin/login.html",
        {"title": settings.SITE_TITLE, "home_path": "/", "error": error,
         "csrf_token": accounts.csrf_token(request)},
        status_code=status_code)


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return login_page(request)


@router.post("/login", dependencies=[Depends(accounts.require_csrf)])
def login(request: Request, email: str = Form(""), password: str = Form("")):
    account = accounts.authenticate(email, password)
    if account is None:
        return login_page(request, WRONG_LOGIN, status_code=401)
    accounts.sign_in(request, account)
    return RedirectResponse("/admin", status_code=303)


@router.post("/logout", dependencies=[Depends(accounts.require_csrf)])
def logout(request: Request):
    accounts.sign_out(request)
    return RedirectResponse("/login", status_code=303)


@router.get("/admin", response_class=HTMLResponse)
def admin_home(request: Request, account=Depends(accounts.require_account)):
    return templates.TemplateResponse(
        request, "admin/hello.html",
        {"title": "Admin", "home_path": "/admin", "account": account,
         "csrf_token": accounts.csrf_token(request)})
