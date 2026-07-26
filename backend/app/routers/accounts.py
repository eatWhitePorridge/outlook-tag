import csv
import io
import re
import random
import string

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app import db
from app.auth import mask_secret, require_admin
from app.schemas import (
    AccountCreate,
    AccountUpdate,
    AliasCreate,
    BatchIdsBody,
    BatchImportBody,
)
from app.services.probe_job import probe_one_account, run_probe_batch

router = APIRouter(prefix="/api/accounts", tags=["accounts"])
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.I,
)


def parse_raw_line(raw: str) -> tuple[str, str, str, str]:
    parts = [p.strip() for p in raw.strip().split("----")]
    if len(parts) != 4:
        raise ValueError("格式错误，需要: 邮箱----密码----client_id----refresh_token")
    email_addr, password, field3, field4 = parts
    if UUID_RE.match(field3):
        client_id, refresh_token = field3, field4
    elif UUID_RE.match(field4):
        client_id, refresh_token = field4, field3
    else:
        client_id, refresh_token = field3, field4
    if not email_addr or not client_id or not refresh_token:
        raise ValueError("邮箱、client_id、refresh_token 不能为空")
    return email_addr, password, client_id, refresh_token


def _maybe_refresh(account_id: int, account: dict, new_refresh: str | None) -> None:
    if new_refresh and new_refresh != account.get("refresh_token"):
        db.update_account(account_id, refresh_token=new_refresh)


@router.get("/stats")
def stats(_: dict = Depends(require_admin)):
    return db.account_stats()


@router.post("/batch")
def batch_import(body: BatchImportBody, _: dict = Depends(require_admin)):
    lines = [ln.strip() for ln in body.lines.splitlines() if ln.strip()]
    results = []
    ok = 0
    for ln in lines:
        try:
            email_addr, password, client_id, refresh_token = parse_raw_line(ln)
            account_id = db.create_account(email_addr, password, client_id, refresh_token)
            results.append({"email": email_addr, "ok": True, "id": account_id})
            ok += 1
        except Exception as e:
            results.append({"email": ln.split("----")[0] if "----" in ln else ln[:40], "ok": False, "error": str(e)})
    db.add_ops_log("batch_import", f"{ok}/{len(lines)}", f"success={ok} total={len(lines)}")
    return {"ok": ok, "total": len(lines), "results": results}


@router.post("/probe-batch")
def probe_batch(
    limit: int = Query(40, ge=1, le=200),
    only_unknown: bool = False,
    _: dict = Depends(require_admin),
):
    cfg = db.get_settings_map(["probe_workers"])
    workers = int(cfg.get("probe_workers") or 6)
    return run_probe_batch(
        limit=limit,
        workers=workers,
        only_unknown=only_unknown,
        source="manual",
    )


@router.post("/batch-delete")
def batch_delete(body: BatchIdsBody, _: dict = Depends(require_admin)):
    existing = db.list_accounts_by_ids(body.ids)
    deleted = db.delete_accounts(body.ids)
    emails = ", ".join(a["email"] for a in existing[:5])
    suffix = "…" if len(existing) > 5 else ""
    db.add_ops_log("batch_delete", f"{deleted}", f"{emails}{suffix}")
    return {"deleted": deleted}


@router.post("/batch-probe")
def batch_probe(body: BatchIdsBody, _: dict = Depends(require_admin)):
    cfg = db.get_settings_map(["probe_workers"])
    workers = int(cfg.get("probe_workers") or 6)
    return run_probe_batch(
        limit=len(body.ids),
        workers=workers,
        source="manual-selected",
        ids=body.ids,
    )


@router.get("/export")
def export_accounts(
    confirm: int = Query(0, description="必须为 1，防止误触发"),
    ids: str | None = None,
    q: str | None = None,
    status: str | None = Query("all"),
    _: dict = Depends(require_admin),
):
    """
    导出明文凭据（密码 + refresh_token）为 CSV。

    这会把账号的完整控制权写进一个本地文件，因此：
    强制 confirm=1、强制记入 ops_log、响应 no-store 且不可缓存。
    """
    if confirm != 1:
        raise HTTPException(400, "导出需要 confirm=1")

    id_list: list[int] = []
    if ids:
        try:
            id_list = [int(x) for x in ids.split(",") if x.strip()]
        except ValueError:
            raise HTTPException(400, "ids 必须是逗号分隔的整数")

    rows = list(db.iter_accounts_for_export(q=q, status=status, ids=id_list or None))

    db.add_ops_log(
        "export_credentials",
        f"{len(rows)}",
        f"ids={len(id_list) or 'all'} q={q or ''} status={status or 'all'}",
    )

    def generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["email", "password", "client_id", "refresh_token", "note", "status"])
        for r in rows:
            writer.writerow([
                r["email"], r["password"], r["client_id"],
                r["refresh_token"], r["note"], r["status"],
            ])
            if buf.tell() > 32768:
                yield buf.getvalue()
                buf.seek(0)
                buf.truncate(0)
        if buf.tell():
            yield buf.getvalue()

    return StreamingResponse(
        generate(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="accounts-export.csv"',
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
        },
    )


@router.delete("/aliases/{alias_id}")
def delete_alias(alias_id: int, _: dict = Depends(require_admin)):
    db.delete_alias(alias_id)
    db.add_ops_log("delete_alias", str(alias_id))
    return {"ok": True}


@router.get("")
def list_accounts(
    q: str | None = None,
    status: str | None = Query("all"),
    page: int = 1,
    per_page: int = 50,
    _: dict = Depends(require_admin),
):
    return db.list_accounts(q=q, status=status, page=page, per_page=per_page)


@router.post("")
def create_account(body: AccountCreate, _: dict = Depends(require_admin)):
    try:
        if body.raw and body.raw.strip():
            email_addr, password, client_id, refresh_token = parse_raw_line(body.raw)
            note = body.note
        else:
            email_addr = body.email.strip()
            password = body.password
            client_id = body.client_id.strip()
            refresh_token = body.refresh_token.strip()
            note = body.note
            if not email_addr or not client_id or not refresh_token:
                raise ValueError("邮箱、client_id、refresh_token 不能为空")
    except ValueError as e:
        raise HTTPException(400, str(e))

    account_id = db.create_account(email_addr, password, client_id, refresh_token, note)
    db.add_ops_log("create_account", email_addr, f"id={account_id}")
    return {"id": account_id, "email": email_addr}


@router.get("/{account_id}")
def get_account(account_id: int, _: dict = Depends(require_admin)):
    account = db.get_account(account_id, secrets=True)
    if not account:
        raise HTTPException(404, "账号不存在")
    account["client_id_masked"] = mask_secret(account.pop("client_id", ""))
    account["refresh_token_masked"] = mask_secret(account.pop("refresh_token", ""))
    account["password"] = account.get("password") or ""
    return account


@router.get("/{account_id}/secrets")
def get_account_secrets(account_id: int, _: dict = Depends(require_admin)):
    account = db.get_account(account_id, secrets=True)
    if not account:
        raise HTTPException(404, "账号不存在")
    return {
        "id": account["id"],
        "email": account["email"],
        "password": account.get("password") or "",
        "client_id": account["client_id"],
        "refresh_token": account["refresh_token"],
        "note": account.get("note") or "",
    }


@router.put("/{account_id}")
def update_account(account_id: int, body: AccountUpdate, _: dict = Depends(require_admin)):
    if not db.get_account(account_id):
        raise HTTPException(404, "账号不存在")
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(400, "没有要更新的字段")
    db.update_account(account_id, **fields)
    db.add_ops_log("update_account", str(account_id), ",".join(fields.keys()))
    return {"ok": True}


@router.delete("/{account_id}")
def delete_account(account_id: int, _: dict = Depends(require_admin)):
    account = db.get_account(account_id)
    if not account:
        raise HTTPException(404, "账号不存在")
    db.delete_account(account_id)
    db.add_ops_log("delete_account", account["email"], f"id={account_id}")
    return {"ok": True}


@router.post("/{account_id}/probe")
def probe_one(account_id: int, _: dict = Depends(require_admin)):
    account = db.get_account(account_id)
    if not account:
        raise HTTPException(404, "账号不存在")
    result = probe_one_account(account_id)
    db.add_ops_log(
        "probe",
        account["email"],
        "ok" if result["ok"] else (result.get("error") or "")[:200],
    )
    return {
        "ok": result["ok"],
        "error": result.get("error", ""),
        "status": "ok" if result["ok"] else "error",
    }


@router.get("/{account_id}/aliases")
def list_aliases(account_id: int, _: dict = Depends(require_admin)):
    if not db.get_account(account_id):
        raise HTTPException(404, "账号不存在")
    return db.list_aliases(account_id)


@router.post("/{account_id}/aliases")
def create_alias(account_id: int, body: AliasCreate, _: dict = Depends(require_admin)):
    account = db.get_account(account_id)
    if not account:
        raise HTTPException(404, "账号不存在")
    tag = body.tag.strip() or "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    local, domain = account["email"].split("@", 1)
    alias = f"{local}+{tag}@{domain}"
    try:
        alias_id = db.create_alias(account_id, alias, tag)
    except Exception:
        raise HTTPException(400, "别名已存在")
    db.add_ops_log("create_alias", alias, f"account={account_id}")
    return {"id": alias_id, "alias": alias, "tag": tag}
