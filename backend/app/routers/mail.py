from fastapi import APIRouter, Depends, HTTPException, Query

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
    access: dict = Depends(require_admin_or_public_account),
):
    account = _load_secrets(account_id)
    effective_filter = filter_to
    if access.get("role") == "public":
        effective_filter = access.get("filter_to") or filter_to
    result, new_refresh = mail_service.fetch_messages(
        account,
        page=page,
        per_page=per_page,
        filter_to=effective_filter,
        codes_only=codes_only,
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


@router.get("/ops")
def ops_log(page: int = 1, per_page: int = 50, _: dict = Depends(require_admin)):
    return db.list_ops_log(page=page, per_page=per_page)
