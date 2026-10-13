"""认证与错词本 HTTP 路由。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from server import config
from server.auth.captcha import issue_captcha
from server.auth.rate_limit import RateLimitExceeded, enforce_and_hit
from server.auth.repository import get_drill_state, save_drill_state
from server.auth.service import (
    AuthError,
    change_password,
    login_user,
    logout_user,
    register_user,
    request_password_reset,
    reset_password,
    resolve_session,
    verify_email_token,
)
from server.db import default_drill_payload, init_db

router = APIRouter()


class RegisterBody(BaseModel):
    email: str = Field(..., min_length=5, max_length=254)
    password: str = Field(..., min_length=8, max_length=128)
    captcha_id: str = Field(..., min_length=8, max_length=64)
    captcha_answer: str = Field(..., min_length=4, max_length=8)


class LoginBody(BaseModel):
    email: str = Field(..., min_length=5, max_length=254)
    password: str = Field(..., min_length=8, max_length=128)


class ForgotBody(BaseModel):
    email: str = Field(..., min_length=5, max_length=254)
    captcha_id: str = Field(..., min_length=8, max_length=64)
    captcha_answer: str = Field(..., min_length=4, max_length=8)


class ResetBody(BaseModel):
    token: str = Field(..., min_length=20, max_length=200)
    password: str = Field(..., min_length=8, max_length=128)


class ChangePasswordBody(BaseModel):
    current_password: str = Field(..., min_length=8, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _set_session_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        key=config.AUTH_SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=config.AUTH_SESSION_TTL_HOURS * 3600,
        secure=config.AUTH_COOKIE_SECURE,
        path=config.AUTH_COOKIE_PATH,
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=config.AUTH_SESSION_COOKIE_NAME,
        path=config.AUTH_COOKIE_PATH,
    )


def _session_id(request: Request) -> str:
    return request.cookies.get(config.AUTH_SESSION_COOKIE_NAME, "")


def require_user(request: Request) -> dict:
    init_db()
    user = resolve_session(_session_id(request))
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    return user


def optional_user(request: Request) -> dict | None:
    init_db()
    return resolve_session(_session_id(request))


@router.get("/api/auth/captcha")
def get_captcha(request: Request) -> JSONResponse:
    init_db()
    client_ip = _client_ip(request)
    try:
        enforce_and_hit(f"captcha:ip:{client_ip}", max_count=60, window_seconds=3600)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail=str(exc),
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    captcha_id, svg = issue_captcha(client_ip)
    return JSONResponse({"captcha_id": captcha_id, "svg": svg})


@router.post("/api/auth/register")
def post_register(body: RegisterBody, request: Request) -> dict:
    init_db()
    try:
        return register_user(
            email=body.email,
            password=body.password,
            captcha_id=body.captcha_id,
            captcha_answer=body.captcha_answer,
            client_ip=_client_ip(request),
        )
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/auth/verify-email", response_class=HTMLResponse)
def verify_email_page(token: str, request: Request) -> HTMLResponse:
    init_db()
    try:
        result = verify_email_token(token, client_ip=_client_ip(request))
        ok = True
        title = "验证成功"
        detail = f"邮箱 {result['email']} 已激活。"
    except AuthError as exc:
        ok = False
        title = "验证失败"
        detail = str(exc)
    color = "#15803d" if ok else "#b91c1c"
    p = config.AUTH_URL_PREFIX
    return HTMLResponse(
        f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{title} · SPHWords</title>
<link rel="stylesheet" href="{p}/assets/style.css"/></head>
<body>
<header class="site-header"><div class="inner"><a class="brand" href="{p}/index.html">SPH<span>Words</span></a></div></header>
<main class="wrap" style="padding:2rem 0">
  <h1 style="color:{color}">{title}</h1>
  <p>{detail}</p>
  <p><a href="{p}/login.html">前往登录</a> · <a href="{p}/register.html">注册页</a></p>
</main></body></html>"""
    )


@router.post("/api/auth/login")
def post_login(body: LoginBody, request: Request, response: Response) -> dict:
    init_db()
    try:
        result = login_user(
            email=body.email,
            password=body.password,
            client_ip=_client_ip(request),
        )
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _set_session_cookie(response, result["session_id"])
    return {"email": result["email"], "message": "登录成功"}


@router.post("/api/auth/logout")
def post_logout(request: Request, response: Response) -> dict:
    init_db()
    logout_user(_session_id(request))
    _clear_session_cookie(response)
    return {"message": "已退出登录"}


@router.get("/api/auth/me")
def get_me(user: dict | None = Depends(optional_user)) -> dict:
    if not user:
        return {"authenticated": False}
    return {"authenticated": True, "email": user["email"], "id": user["id"]}


@router.post("/api/auth/forgot-password")
def post_forgot(body: ForgotBody, request: Request) -> dict:
    init_db()
    try:
        return request_password_reset(
            email=body.email,
            captcha_id=body.captcha_id,
            captcha_answer=body.captcha_answer,
            client_ip=_client_ip(request),
        )
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/auth/reset-password")
def post_reset(body: ResetBody, request: Request) -> dict:
    init_db()
    try:
        return reset_password(
            token=body.token,
            password=body.password,
            client_ip=_client_ip(request),
        )
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/auth/change-password")
def post_change_password(
    body: ChangePasswordBody,
    request: Request,
    user: dict = Depends(require_user),
) -> dict:
    try:
        return change_password(
            user_id=int(user["id"]),
            current_password=body.current_password,
            new_password=body.new_password,
            client_ip=_client_ip(request),
        )
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/drill/lists")
def get_lists(user: dict = Depends(require_user)) -> dict[str, Any]:
    return get_drill_state(int(user["id"]))


@router.put("/api/drill/lists")
def put_lists(payload: dict[str, Any], user: dict = Depends(require_user)) -> dict[str, Any]:
    if not isinstance(payload.get("lists"), list):
        # allow bare wrap or full state
        if "lists" not in payload:
            raise HTTPException(status_code=400, detail="缺少 lists")
    # merge prefs defaults
    base = default_drill_payload()
    base.update(payload)
    if not isinstance(base.get("lists"), list) or not base["lists"]:
        raise HTTPException(status_code=400, detail="lists 无效")
    cleaned = []
    for item in base["lists"]:
        if not isinstance(item, dict):
            continue
        lid = str(item.get("id") or "").strip() or "default"
        name = str(item.get("name") or "未命名列表")[:40]
        ids = item.get("ids") if isinstance(item.get("ids"), list) else []
        cleaned.append({"id": lid, "name": name, "ids": [str(x) for x in ids]})
    if not cleaned:
        raise HTTPException(status_code=400, detail="lists 为空")
    base["lists"] = cleaned
    return save_drill_state(int(user["id"]), base)
