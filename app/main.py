"""The FastAPI application.

T00 (already done): the admin console answers at /admin and the public site
answers at /. That is the whole skeleton — it exists so you can prove the stack
runs before you build anything on it.

Add your routes in their own modules (app/routes/posts.py and so on) and include
them here. Keep this file small.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from starlette.middleware.sessions import SessionMiddleware

from app import accounts, content, publish, settings
from app.routes import accounts as accounts_routes, auth, console, pages, posts
from app.templating import templates


def create_app() -> FastAPI:
    accounts.init_db()
    content.init_db()
    app = FastAPI(title="IPHS 400 MP2 CMS")
    # max_age=None: a session cookie with no Expires/Max-Age, so it ends when the
    # browser closes.
    app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY,
                       session_cookie="session", max_age=None,
                       same_site="lax", https_only=False)
    app.include_router(auth.router)
    app.include_router(console.router)
    app.include_router(posts.router)
    app.include_router(pages.router)
    app.include_router(accounts_routes.router)

    @app.exception_handler(accounts.NoPermission)
    def no_permission(request: Request, exc: accounts.NoPermission):
        return templates.TemplateResponse(
            request, "admin/no_permission.html",
            {"title": "No permission", "home_path": "/admin"}, status_code=403)

    # The local preview of the public site: the same renderers the export uses,
    # at the same relative paths, so it shows Published content only.
    @app.get("/", response_class=HTMLResponse)
    def public_home():
        return publish.render_front()

    @app.get("/style.css")
    def public_css():
        return Response(publish.CSS, media_type="text/css")

    @app.get("/{link}.html", response_class=HTMLResponse)
    def public_page(link: str):
        page = publish.render_page(link)
        if page is None:
            raise HTTPException(status_code=404, detail="No such Page.")
        return page

    @app.get("/posts/index.html", response_class=HTMLResponse)
    def public_past():
        return publish.render_past()

    @app.get("/posts/{link}.html", response_class=HTMLResponse)
    def public_post(link: str):
        page = publish.render_post(link)
        if page is None:
            raise HTTPException(status_code=404, detail="No such Post.")
        return page

    # Your ticket work plugs in here, e.g.
    #   from app.routes import posts
    #   app.include_router(posts.router)
    return app


app = create_app()
