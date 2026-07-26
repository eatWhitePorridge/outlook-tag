"""
给自动化脚本用的取码服务。

与管理端读信的区别在于：这里会被脚本高频轮询，每次都打真实 IMAP 的话
Outlook 侧很快会限流甚至风控账号。所以只扫最近若干封，并对结果做短缓存。
"""

import threading
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

from app import db
from app.services import mail as mail_service

# 结果缓存：脚本填完表单后往往每秒问一次，这层让 IMAP 侧最多每 8 秒被打一次
RESULT_TTL = 8
# 取码只需看最近几封，不必走完整分页
SCAN_LIMIT = 10

_cache: dict[tuple[int, str], tuple[dict[str, Any], float]] = {}
_lock = threading.Lock()


def resolve_target(email: str) -> tuple[dict[str, Any] | None, str]:
    """
    邮箱或 +tag 别名 -> (账号, filter_to)。
    解析顺序与 routers/mail.py 的 lookup 保持一致。
    """
    addr = (email or "").strip()
    if not addr:
        return None, ""
    account = db.get_account_by_email(addr)
    if account:
        return account, addr
    account = db.get_account_by_alias(addr)
    if account:
        # 别名边界：必须把 filter_to 带下去，
        # 否则会读到同一账号下其他别名的验证码
        return account, addr
    return None, ""


def _age_seconds(date_str: str) -> int | None:
    if not date_str:
        return None
    try:
        dt = parsedate_to_datetime(date_str)
    except (TypeError, ValueError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0, int((datetime.now(timezone.utc) - dt).total_seconds()))


def fetch_recent(email: str) -> tuple[list[dict[str, Any]] | None, str | None]:
    """取最近 SCAN_LIMIT 封（带 8 秒缓存）。返回 (消息列表, 错误)。"""
    account, filter_to = resolve_target(email)
    if not account:
        return None, "邮箱不存在"

    key = (int(account["id"]), filter_to)
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[1] < RESULT_TTL:
            return hit[0]["messages"], None

    full = db.get_account(int(account["id"]), secrets=True)
    if not full:
        return None, "邮箱不存在"

    result, new_refresh = mail_service.fetch_messages(
        full, page=1, per_page=SCAN_LIMIT, filter_to=filter_to
    )
    if new_refresh and new_refresh != full.get("refresh_token"):
        db.update_account(int(account["id"]), refresh_token=new_refresh)
    if "error" in result:
        return None, result["error"]

    messages = result.get("messages", [])
    with _lock:
        _cache[key] = ({"messages": messages}, now)
        if len(_cache) > 500:
            for k, (_, ts) in list(_cache.items()):
                if now - ts > RESULT_TTL:
                    _cache.pop(k, None)
    return messages, None


def latest_code(email: str, within_minutes: int | None = None) -> tuple[dict[str, Any] | None, str | None]:
    """
    返回最近一封带验证码的邮件。
    within_minutes 用于避免脚本拿到上一轮流程留下的旧码。
    """
    messages, err = fetch_recent(email)
    if err:
        return None, err

    for m in messages or []:
        if not m.get("codes"):
            continue
        age = _age_seconds(m.get("date", ""))
        if within_minutes is not None and age is not None and age > within_minutes * 60:
            # 列表按新到旧排序，第一封带码的都超时了，后面只会更旧
            break
        return {
            "email": email,
            "code": m["codes"][0],
            "codes": m["codes"],
            "subject": m.get("subject", ""),
            "from": m.get("from", ""),
            "date": m.get("date", ""),
            "uid": m.get("uid"),
            "age_seconds": age,
        }, None
    return None, None
