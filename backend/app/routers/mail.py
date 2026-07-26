from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response

from app import db, ratelimit
from app.auth import issue_public_token, require_admin, require_admin_or_public_account
from app.schemas import LookupBody
from app.services import mail as mail_service

router = APIRouter(prefix="/api", tags=["mail"])


def _load_secrets(account_id: int) -> dict:
    account = db.get_account(account_id, secrets=True)
    if not account:
        raise HTTPException(404, "账号不存在")
    return account


def _persist_refresh(account_id: int, account: dict, new_refresh: str | None) -> None:
    if new_refresh and new_refresh != account.get("refresh_token"):
        db.update_account(account_id, refresh_token=new_refresh)


def _guard_alias(access: dict, headers: dict) -> None:
    """
    public token 绑定的是 {account_id, filter_to}。按 UID 直接取信时，
    account_id 相符不代表这封信属于该别名 —— UID 是小整数，可以直接枚举。
    这里比对收件地址，把别名边界补上。
    """
    if access.get("role") != "public":
        return
    needle = (access.get("filter_to") or "").strip().lower()
    if not needle:
        return
    haystack = " ".join(
        str(headers.get(k) or "") for k in ("to", "cc", "bcc", "delivered_to", "subject")
    ).lower()
    if needle in haystack:
        return
    # Outlook 有时把别名写成不含 + 号的形式，退一步只比对 tag 片段
    if "+" in needle:
        tag = needle.split("+", 1)[1].split("@")[0]
        if tag and tag in haystack:
            return
    raise HTTPException(403, "该邮件不属于此别名")


@router.post("/lookup")
def lookup(body: LookupBody, request: Request):
    # 未鉴权接口，且存在即 200 / 不存在即 404 —— 是个可枚举的 oracle。
    # 限流不能消除这个性质，但能把批量枚举的成本抬上去。
    ratelimit.check(
        "lookup",
        ratelimit.client_ip(request),
        limit=30,
        window=60,
        detail="查询过于频繁，请稍后再试",
    )
    email_addr = body.email.strip()
    if not email_addr:
        raise HTTPException(400, "请输入邮箱地址")
    account = db.get_account_by_email(email_addr)
    filter_to = email_addr
    if not account:
        account = db.get_account_by_alias(email_addr)
        if not account:
            raise HTTPException(404, "邮箱不存在")
        filter_to = email_addr
    token = issue_public_token(account["id"], filter_to)
    return {
        "id": account["id"],
        "display": email_addr,
        "filter_to": filter_to,
        "token": token,
    }


@router.get("/accounts/{account_id}/messages")
def list_messages(
    account_id: int,
    page: int = 1,
    per_page: int = 20,
    filter_to: str | None = None,
    codes_only: bool = False,
    search: str | None = None,
    search_field: str = Query("subject", pattern="^(subject|from|text)$"),
    access: dict = Depends(require_admin_or_public_account),
):
    account = _load_secrets(account_id)
    # public token 携带的 filter_to 是硬边界：search 只能在其之上收窄，不能替代它
    effective_filter = filter_to
    if access.get("role") == "public":
        effective_filter = access.get("filter_to") or filter_to
    result, new_refresh = mail_service.fetch_messages(
        account,
        page=page,
        per_page=per_page,
        filter_to=effective_filter,
        codes_only=codes_only,
        search=search,
        search_field=search_field,
    )
    _persist_refresh(account_id, account, new_refresh)
    if "error" in result:
        raise HTTPException(500, result["error"])
    return result


@router.get("/accounts/{account_id}/messages/{uid}")
def message_detail(
    account_id: int,
    uid: str = Path(pattern=r"^\d+$"),
    access: dict = Depends(require_admin_or_public_account),
):
    account = _load_secrets(account_id)
    result, new_refresh = mail_service.fetch_single_message(account, uid)
    _persist_refresh(account_id, account, new_refresh)
    if "error" in result:
        code = 404 if result.get("code") == "not_found" else 500
        raise HTTPException(code, result["error"])
    _guard_alias(access, result)
    return result


@router.get("/accounts/{account_id}/messages/{uid}/attachments/{index}")
def download_attachment(
    account_id: int,
    index: int,
    uid: str = Path(pattern=r"^\d+$"),
    access: dict = Depends(require_admin_or_public_account),
):
    """附件下载。走与读信同一套鉴权，并同样校验别名边界。"""
    account = _load_secrets(account_id)
    if access.get("role") == "public":
        # 附件属于哪封信，只能先取回这封信的头部再判断
        meta, _ = mail_service.fetch_single_message(account, uid)
        if "error" in meta:
            raise HTTPException(404, "邮件不存在")
        _guard_alias(access, meta)
    att, err = mail_service.fetch_attachment(account, uid, index)
    if err or not att:
        raise HTTPException(404 if err == "附件不存在" else 500, err or "附件读取失败")
    filename = quote(att["filename"])
    return Response(
        content=att["data"],
        media_type=att["content_type"] or "application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
            "Cache-Control": "no-store",
        },
    )


@router.get("/ops")
def ops_log(
    page: int = 1,
    per_page: int = 50,
    action: str | None = None,
    _: dict = Depends(require_admin),
):
    return db.list_ops_log(page=page, per_page=per_page, action=action)
