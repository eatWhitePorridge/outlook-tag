from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app import db
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


@router.post("/lookup")
def lookup(body: LookupBody):
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
    uid: str,
    access: dict = Depends(require_admin_or_public_account),
):
    account = _load_secrets(account_id)
    result, new_refresh = mail_service.fetch_single_message(account, uid)
    _persist_refresh(account_id, account, new_refresh)
    if "error" in result:
        code = 404 if result.get("code") == "not_found" else 500
        raise HTTPException(code, result["error"])
    return result


@router.get("/accounts/{account_id}/messages/{uid}/attachments/{index}")
def download_attachment(
    account_id: int,
    uid: str,
    index: int,
    access: dict = Depends(require_admin_or_public_account),
):
    """附件下载。走与读信同一套鉴权，public token 同样只能取到自己账号的邮件。"""
    account = _load_secrets(account_id)
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
