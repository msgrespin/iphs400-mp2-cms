"""The FastAPI application.

T00 (already done): the admin console answers at /admin and the public site
answers at /. That is the whole skeleton — it exists so you can prove the stack
runs before you build anything on it.

Add your routes in their own modules (app/routes/posts.py and so on) and include
them here. Keep this file small.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from starlette.middleware.sessions import SessionMiddleware

from app import accounts, settings
from app.routes import auth
from app.templating import templates


def create_app() -> FastAPI:
    accounts.init_db()
    app = FastAPI(title="IPHS 400 MP2 CMS")
    # max_age=None: a session cookie with no Expires/Max-Age, so it ends when the
    # browser closes.
    app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY,
                       session_cookie="session", max_age=None,
                       same_site="lax", https_only=False)
    app.include_router(auth.router)

    @app.get("/")
    def public_home(request: Request):
        return templates.TemplateResponse(
            request, "public/home.html",
            {"title": settings.SITE_TITLE, "items": []},
        )

    # Your ticket work plugs in here, e.g.
    #   from app.routes import posts
    #   app.include_router(posts.router)
    return app


app = create_app()
