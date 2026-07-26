import threading
import time
from collections import deque

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.auth import clear_admin_session, require_admin, set_admin_session, verify_admin_password
from app.config import Settings, get_settings
from app.schemas import LoginBody

router = APIRouter(prefix="/api/auth", tags=["auth"])

# 管理密码是全库凭据的钥匙，而这个接口此前完全没有限流 ——
# 实测 80 次尝试 0.03 秒跑完，服务又在公网明文 HTTP 上。
_LOGIN_WINDOW = 300
_LOGIN_MAX = 10
_login_hits: dict[str, deque] = {}
_login_lock = threading.Lock()


def _check_login_rate(ip: str) -> None:
    now = time.time()
    with _login_lock:
        q = _login_hits.setdefault(ip, deque())
        while q and now - q[0] > _LOGIN_WINDOW:
            q.popleft()
        if len(q) >= _LOGIN_MAX:
            raise HTTPException(
                status_code=429,
                detail="登录尝试过于频繁，请稍后再试",
                headers={"Retry-After": str(int(_LOGIN_WINDOW - (now - q[0])) + 1)},
            )
        q.append(now)
        if len(_login_hits) > 5000:
            for k, dq in list(_login_hits.items()):
                if not dq or now - dq[-1] > _LOGIN_WINDOW:
                    _login_hits.pop(k, None)


@router.post("/login")
def login(
    body: LoginBody,
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
):
    _check_login_rate(request.client.host if request.client else "unknown")
    if not verify_admin_password(body.password, settings):
        return Response(content='{"detail":"密码错误"}', status_code=401, media_type="application/json")
    set_admin_session(response, settings)
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    clear_admin_session(response)
    return {"ok": True}


@router.get("/me")
def me(_: dict = Depends(require_admin)):
    return {"role": "admin"}
