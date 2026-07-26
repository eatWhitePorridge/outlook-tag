"""API Key 管理，仅管理端可用。"""

from fastapi import APIRouter, Depends, HTTPException

from app import db
from app.auth import generate_api_key, require_admin
from app.schemas import ApiKeyCreate, ApiKeyUpdate

router = APIRouter(prefix="/api/api-keys", tags=["api-keys"])


@router.get("")
def list_keys(_: dict = Depends(require_admin)):
    return db.list_api_keys()


@router.post("")
def create_key(body: ApiKeyCreate, _: dict = Depends(require_admin)):
    """明文 Key 只在这个响应里出现一次，数据库只存 sha256。"""
    plain, key_hash, prefix = generate_api_key()
    key_id = db.create_api_key(body.name.strip(), key_hash, prefix)
    db.add_ops_log("create_api_key", body.name.strip(), f"id={key_id} prefix={prefix}")
    return {"id": key_id, "name": body.name.strip(), "prefix": prefix, "key": plain}


@router.patch("/{key_id}")
def update_key(key_id: int, body: ApiKeyUpdate, _: dict = Depends(require_admin)):
    row = db.get_api_key(key_id)
    if not row:
        raise HTTPException(404, "Key 不存在")
    db.set_api_key_enabled(key_id, body.enabled)
    db.add_ops_log(
        "update_api_key", row["name"], f"id={key_id} enabled={int(body.enabled)}"
    )
    return {"ok": True}


@router.delete("/{key_id}")
def delete_key(key_id: int, _: dict = Depends(require_admin)):
    row = db.get_api_key(key_id)
    if not row:
        raise HTTPException(404, "Key 不存在")
    db.delete_api_key(key_id)
    db.add_ops_log("delete_api_key", row["name"], f"id={key_id}")
    return {"ok": True}
