from fastapi import APIRouter, Depends, Request, Response

from app import ratelimit
from app.auth import clear_admin_session, require_admin, set_admin_session, verify_admin_password
from app.config import Settings, get_settings
from app.schemas import LoginBody

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(
    body: LoginBody,
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
):
    # 管理密码是全库凭据的钥匙，而这个接口此前完全没有限流 ——
    # 实测 80 次尝试 0.03 秒跑完，服务又在公网明文 HTTP 上。
    ip = ratelimit.client_ip(request)
    ratelimit.check("login", ip, limit=10, window=300, detail="登录尝试过于频繁，请稍后再试")
    if not verify_admin_password(body.password, settings):
        return Response(content='{"detail":"密码错误"}', status_code=401, media_type="application/json")
    # 登录成功就清掉该 IP 的失败计数，正常使用不会被自己卡住
    ratelimit.forget("login", ip)
    set_admin_session(response, settings)
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    clear_admin_session(response)
    return {"ok": True}


@router.get("/me")
def me(_: dict = Depends(require_admin)):
    return {"role": "admin"}
