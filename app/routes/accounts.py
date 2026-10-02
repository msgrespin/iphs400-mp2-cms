"""The Accounts screen (Admin only): list, create, change Role, set password,
deactivate and reactivate. There is no delete: Accounts are deactivated so their
Posts stay on the site.

Every route here is Admin only, so an Editor requesting any of them by direct URL
gets the "no permission" screen. The Role check runs before the CSRF check.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import accounts
from app.templating import templates

router = APIRouter(prefix="/admin/accounts",
                   dependencies=[Depends(accounts.require_account),
                                 Depends(accounts.require_admin)])
csrf = [Depends(accounts.require_csrf)]

LIST_URL = "/admin/accounts"


def flash(request: Request, message: str) -> None:
    request.session["flash"] = message


def list_screen(request: Request, error: str = "", status_code: int = 200, form=None):
    return templates.TemplateResponse(
        request, "admin/accounts.html",
        {"title": "Accounts", "home_path": "/admin", "accounts": accounts.list_accounts(),
         "csrf_token": accounts.csrf_token(request),
         "flash": request.session.pop("flash", ""), "error": error,
         "form": form or {}},
        status_code=status_code)


def act(request: Request, action, success: str):
    """Run one Accounts action; flash and redirect on success, show the reason if refused."""
    try:
        account = action()
    except accounts.NotFound as problem:
        return list_screen(request, str(problem), 404)
    except accounts.AccountProblem as problem:
        return list_screen(request, str(problem), 400)
    flash(request, success.format(name=account["display_name"]))
    return RedirectResponse(LIST_URL, status_code=303)


@router.get("", response_class=HTMLResponse, name="accounts_list")
def list_accounts(request: Request):
    return list_screen(request)


@router.post("", dependencies=csrf)
def create_account(request: Request, display_name: str = Form(""), email: str = Form(""),
                   role: str = Form(""), password: str = Form("")):
    try:
        accounts.create_account(email, display_name, password, role)
    except accounts.AccountProblem as problem:
        # The password is never sent back to the browser.
        return list_screen(request, str(problem), 400,
                           form={"display_name": display_name, "email": email, "role": role})
    flash(request, f"Created the {display_name.strip()} Account.")
    return RedirectResponse(LIST_URL, status_code=303)


@router.post("/{account_id}/role", dependencies=csrf)
def change_role(request: Request, account_id: int, role: str = Form("")):
    return act(request, lambda: accounts.set_role(account_id, role),
               f"Changed the {{name}} Account to {role.capitalize()}.")


@router.post("/{account_id}/password", dependencies=csrf)
def change_password(request: Request, account_id: int, password: str = Form("")):
    return act(request, lambda: accounts.set_password(account_id, password),
               "Set a new password for the {name} Account.")


@router.post("/{account_id}/deactivate", dependencies=csrf)
def deactivate(request: Request, account_id: int):
    return act(request, lambda: accounts.deactivate(account_id),
               "Deactivated the {name} Account. It can no longer sign in.")


@router.post("/{account_id}/reactivate", dependencies=csrf)
def reactivate(request: Request, account_id: int):
    return act(request, lambda: accounts.reactivate(account_id),
               "Reactivated the {name} Account. It can sign in again.")
