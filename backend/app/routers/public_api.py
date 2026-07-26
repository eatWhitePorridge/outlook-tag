"""给外部脚本用的取码接口，API Key 鉴权。"""

import threading
import time
from collections import deque

from fastapi import APIRouter, Depends, HTTPException, Query

from app import db
from app.auth import require_api_key
from app.services import codes as code_service

router = APIRouter(prefix="/api/v1", tags=["public-api"])

# 每 Key 限流：脚本轮询是常态，没有这层会把 Outlook 打到限流。
# 单进程部署（内置调度器本来就要求单实例），内存计数即可。
RATE_LIMIT = 60
RATE_WINDOW = 60
_hits: dict[int, deque] = {}
_lock = threading.Lock()


def _check_rate(key_id: int) -> None:
    now = time.time()
    with _lock:
        q = _hits.setdefault(key_id, deque())
        while q and now - q[0] > RATE_WINDOW:
            q.popleft()
        if len(q) >= RATE_LIMIT:
            retry = int(RATE_WINDOW - (now - q[0])) + 1
            raise HTTPException(
                status_code=429,
                detail=f"请求过于频繁，每分钟上限 {RATE_LIMIT} 次",
                headers={"Retry-After": str(retry)},
            )
        q.append(now)


@router.get("/code")
def get_code(
    email: str = Query(..., description="邮箱地址或 +tag 别名"),
    within_minutes: int | None = Query(
        None, ge=1, le=1440, description="只认这个时间窗内到达的邮件，避免拿到旧码"
    ),
    key: dict = Depends(require_api_key),
):
    _check_rate(key["id"])
    db.touch_api_key(key["id"], email)

    result, err = code_service.latest_code(email, within_minutes=within_minutes)
    if err:
        raise HTTPException(404 if err == "邮箱不存在" else 502, err)
    if not result:
        raise HTTPException(404, "未找到验证码")
    return result


@router.get("/messages")
def get_messages(
    email: str = Query(..., description="邮箱地址或 +tag 别名"),
    limit: int = Query(10, ge=1, le=10),
    key: dict = Depends(require_api_key),
):
    """原始列表，脚本需要自己判定时用。"""
    _check_rate(key["id"])
    db.touch_api_key(key["id"], email)

    messages, err, resolved = code_service.fetch_recent(email)
    if err:
        raise HTTPException(404 if err == "邮箱不存在" else 502, err)
    return {"email": resolved or email, "messages": (messages or [])[:limit]}
