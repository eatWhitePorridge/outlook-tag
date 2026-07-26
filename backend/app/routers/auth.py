from fastapi import APIRouter, Depends, Response

from app.auth import clear_admin_session, require_admin, set_admin_session, verify_admin_password
from app.config import Settings, get_settings
from app.schemas import LoginBody

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginBody, response: Response, settings: Settings = Depends(get_settings)):
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
