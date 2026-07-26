import hashlib
import hmac
import secrets
import time
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import Settings, get_settings

ADMIN_COOKIE = "mail_admin"
PUBLIC_HEADER = "X-Public-Token"
API_KEY_HEADER = "X-API-Key"
API_KEY_PREFIX = "mk_"


def _serializer(settings: Settings) -> URLSafeTimedSerializer:
    if not settings.secret_key:
        raise HTTPException(status_code=500, detail="SECRET_KEY 未配置")
    return URLSafeTimedSerializer(settings.secret_key, salt="mail-session")


def verify_admin_password(password: str, settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    if not settings.admin_password:
        raise HTTPException(status_code=500, detail="ADMIN_PASSWORD 未配置")
    # 必须先 encode：compare_digest 对含非 ASCII 的 str 直接抛 TypeError，
    # 中文密码会让登录接口无论对错都 500
    return hmac.compare_digest(password.encode("utf-8"), settings.admin_password.encode("utf-8"))


def set_admin_session(response: Response, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    token = _serializer(settings).dumps({"role": "admin", "n": secrets.token_hex(8)})
    response.set_cookie(
        ADMIN_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.session_ttl,
        path="/",
    )


def clear_admin_session(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        ADMIN_COOKIE,
        path="/",
        secure=settings.cookie_secure,
        samesite="lax",
    )


def require_admin(
    mail_admin: Annotated[str | None, Cookie(alias=ADMIN_COOKIE)] = None,
    settings: Settings = Depends(get_settings),
) -> dict:
    if not mail_admin:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        data = _serializer(settings).loads(mail_admin, max_age=settings.session_ttl)
    except SignatureExpired:
        raise HTTPException(status_code=401, detail="登录已过期")
    except BadSignature:
        raise HTTPException(status_code=401, detail="无效会话")
    if data.get("role") != "admin":
        raise HTTPException(status_code=401, detail="无效会话")
    return data


def issue_public_token(account_id: int, filter_to: str, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    return _serializer(settings).dumps(
        {
            "role": "public",
            "account_id": account_id,
            "filter_to": filter_to,
            "n": secrets.token_hex(6),
        }
    )


def parse_public_token(token: str, settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    try:
        data = _serializer(settings).loads(token, max_age=settings.public_token_ttl)
    except SignatureExpired:
        raise HTTPException(status_code=401, detail="访问已过期，请重新查询")
    except BadSignature:
        raise HTTPException(status_code=401, detail="无效访问令牌")
    if data.get("role") != "public":
        raise HTTPException(status_code=401, detail="无效访问令牌")
    return data


def require_public(
    x_public_token: Annotated[str | None, Header(alias=PUBLIC_HEADER)] = None,
    settings: Settings = Depends(get_settings),
) -> dict:
    if not x_public_token:
        raise HTTPException(status_code=401, detail="缺少访问令牌")
    return parse_public_token(x_public_token, settings)


def require_admin_or_public_account(
    account_id: int,
    mail_admin: Annotated[str | None, Cookie(alias=ADMIN_COOKIE)] = None,
    x_public_token: Annotated[str | None, Header(alias=PUBLIC_HEADER)] = None,
    settings: Settings = Depends(get_settings),
) -> dict:
    if mail_admin:
        try:
            data = _serializer(settings).loads(mail_admin, max_age=settings.session_ttl)
            if data.get("role") == "admin":
                return {"role": "admin", "account_id": account_id, "filter_to": None}
        except (SignatureExpired, BadSignature):
            pass
    if x_public_token:
        data = parse_public_token(x_public_token, settings)
        if int(data["account_id"]) != int(account_id):
            raise HTTPException(status_code=403, detail="无权访问该邮箱")
        return data
    raise HTTPException(status_code=401, detail="未授权")


def generate_api_key() -> tuple[str, str, str]:
    """返回 (明文, sha256, 展示用前缀)。明文只在创建响应里出现一次，不入库。"""
    plain = API_KEY_PREFIX + secrets.token_urlsafe(32)
    return plain, hash_api_key(plain), plain[:10]


def hash_api_key(plain: str) -> str:
    return hashlib.sha256(plain.encode()).hexdigest()


def require_api_key(
    x_api_key: Annotated[str | None, Header(alias=API_KEY_HEADER)] = None,
) -> dict:
    """
    只从请求头读 Key，刻意不支持 ?key= 查询参数
    —— 查询串会落进 nginx / uvicorn 的访问日志。
    """
    from app import db  # 延迟导入，避免与 db -> config 的循环

    if not x_api_key:
        raise HTTPException(status_code=401, detail="缺少 API Key（请求头 X-API-Key）")

    row = db.get_api_key_by_hash(hash_api_key(x_api_key.strip()))
    # 即使查不到也走一次比较，避免用响应时间区分「不存在」与「已停用」
    if not row or not hmac.compare_digest(row["key_hash"], hash_api_key(x_api_key.strip())):
        raise HTTPException(status_code=401, detail="无效的 API Key")
    if not row["enabled"]:
        raise HTTPException(status_code=401, detail="该 API Key 已停用")
    return {"id": row["id"], "name": row["name"]}


def mask_secret(value: str, keep: int = 6) -> str:
    if not value:
        return ""
    if len(value) <= keep * 2:
        return "*" * len(value)
    return f"{value[:keep]}…{value[-keep:]}"


def short_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:12]
