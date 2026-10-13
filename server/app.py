"""SPHWords FastAPI entry: static site + auth/drill API."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from server.auth.routes import router as auth_router
from server.db import init_db

ROOT = Path(__file__).resolve().parent.parent

app = FastAPI(title="SPHWords", docs_url="/api/docs", redoc_url=None)
app.include_router(auth_router)


@app.on_event("startup")
def _startup() -> None:
    init_db()


def _file(name: str) -> FileResponse:
    path = ROOT / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path)


@app.get("/")
def root_index() -> FileResponse:
    return _file("index.html")


@app.get("/index.html")
def page_index() -> FileResponse:
    return _file("index.html")


@app.get("/notes.html")
def page_notes() -> FileResponse:
    return _file("notes.html")


@app.get("/drill.html")
def page_drill() -> FileResponse:
    return _file("drill.html")


@app.get("/compare.html")
def page_compare() -> FileResponse:
    return _file("compare.html")


@app.get("/login.html")
def page_login() -> FileResponse:
    return _file("login.html")


@app.get("/register.html")
def page_register() -> FileResponse:
    return _file("register.html")


@app.get("/forgot.html")
def page_forgot() -> FileResponse:
    return _file("forgot.html")


@app.get("/reset.html")
def page_reset() -> FileResponse:
    return _file("reset.html")


@app.get("/account.html")
def page_account() -> FileResponse:
    return _file("account.html")


@app.get("/manifest.webmanifest")
def page_manifest() -> FileResponse:
    return _file("manifest.webmanifest")


@app.get("/sw.js")
def page_sw() -> FileResponse:
    return _file("sw.js")


app.mount("/assets", StaticFiles(directory=str(ROOT / "assets")), name="assets")
app.mount("/chapter", StaticFiles(directory=str(ROOT / "chapter")), name="chapter")
