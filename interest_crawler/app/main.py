from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

from . import db
from .models import CATEGORIES
from .services import aggregator


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = str(BASE_DIR / "app.db")

app = FastAPI()
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.on_event("startup")
async def startup() -> None:
    await run_in_threadpool(db.init_db, DB_PATH)


def _ensure_user_id(request: Request, response) -> str:
    uid = request.cookies.get("uid")
    if not uid:
        uid = uuid4().hex
        response.set_cookie(
            "uid",
            uid,
            max_age=60 * 60 * 24 * 365,
            samesite="lax",
            httponly=False,
        )
    return uid


async def _get_user_categories(user_id: str):
    def _load():
        conn = db.get_connection(DB_PATH)
        try:
            return db.get_user_prefs(conn, user_id)
        finally:
            conn.close()

    return await run_in_threadpool(_load)


async def _set_user_categories(user_id: str, categories):
    def _save():
        conn = db.get_connection(DB_PATH)
        try:
            db.set_user_prefs(conn, user_id, categories)
        finally:
            conn.close()

    await run_in_threadpool(_save)


async def _save_items(items):
    def _save():
        conn = db.get_connection(DB_PATH)
        try:
            db.upsert_feed_items(conn, items)
        finally:
            conn.close()

    await run_in_threadpool(_save)


async def _load_items_for_today(categories):
    def _load():
        conn = db.get_connection(DB_PATH)
        try:
            return db.get_items_for_categories_today(conn, categories, db.get_kst_now())
        finally:
            conn.close()

    return await run_in_threadpool(_load)


@app.get("/preferences", response_class=HTMLResponse)
async def preferences(request: Request):
    uid = request.cookies.get("uid")
    selected = []
    if uid:
        selected = await _get_user_categories(uid)
    context = {
        "request": request,
        "categories": CATEGORIES,
        "selected": set(selected),
    }
    response = templates.TemplateResponse("preferences.html", context)
    _ensure_user_id(request, response)
    return response


@app.post("/preferences")
async def save_preferences(request: Request):
    form = await request.form()
    selected = form.getlist("categories")
    response = RedirectResponse(url="/", status_code=303)
    uid = _ensure_user_id(request, response)
    await _set_user_categories(uid, selected)
    return response


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    uid = request.cookies.get("uid")
    if not uid:
        return RedirectResponse(url="/preferences", status_code=303)
    categories = await _get_user_categories(uid)
    if not categories:
        return RedirectResponse(url="/preferences", status_code=303)
    items = await _load_items_for_today(categories)
    response = templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "items": items,
            "categories": categories,
        },
    )
    _ensure_user_id(request, response)
    return response


@app.post("/refresh")
async def refresh(request: Request):
    uid = request.cookies.get("uid")
    if not uid:
        return RedirectResponse(url="/preferences", status_code=303)
    categories = await _get_user_categories(uid)
    if not categories:
        return RedirectResponse(url="/preferences", status_code=303)

    items = await aggregator.fetch_and_enrich(categories)
    await _save_items(items)

    response = RedirectResponse(url="/", status_code=303)
    _ensure_user_id(request, response)
    return response


@app.get("/api/items")
async def api_items(request: Request):
    uid = request.cookies.get("uid")
    if not uid:
        return JSONResponse({"items": []})
    categories = await _get_user_categories(uid)
    if not categories:
        return JSONResponse({"items": []})
    items = await _load_items_for_today(categories)
    return JSONResponse({"items": items})
