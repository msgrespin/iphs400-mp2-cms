"""The shared Jinja environment."""
from fastapi import Request
from fastapi.templating import Jinja2Templates

from app import accounts, content, settings


def console_account(request: Request) -> dict:
    """The signed-in Account, so every console screen can show the same navigation."""
    account_id = request.session.get("account_id") if "session" in request.scope else None
    account = accounts.get_account(account_id) if account_id else None
    # The navigation's sign-out form needs a token even on screens that pass none.
    if account is None:
        return {"console_account": None}
    return {"console_account": account, "csrf_token": accounts.csrf_token(request)}


templates = Jinja2Templates(directory=str(settings.TEMPLATES),
                            context_processors=[console_account])
templates.env.globals["eastern"] = content.eastern
