"""The shared Jinja environment."""
from fastapi import Request
from jinja2 import pass_context
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


@pass_context
def url_for(context, name: str, **path_params) -> str:
    """The path of a named route, e.g. "/admin/posts". Unlike Starlette's own url_for,
    this has no scheme or host, so links stay the same as when they were typed by hand."""
    return str(context["request"].app.url_path_for(name, **path_params))


templates.env.globals["url_for"] = url_for
templates.env.globals["eastern"] = content.eastern
