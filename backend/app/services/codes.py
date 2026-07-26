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


def _candidates(email: str) -> list[str]:
    """
    查询串里的 `+` 会被解码成空格，而这个接口的主力用法正是 `name+tag@`。
    脚本写 `?email=name+tag@x.com` 时服务端收到的是 `name tag@x.com`，
    与其让所有调用方都记得写 %2B，不如在这里兜住。
    邮箱本地部分不允许出现未转义空格，所以这个还原是安全的。
    """
    addr = (email or "").strip()
    if not addr:
        return []
    out = [addr]
    if " " in addr:
        out.append(addr.replace(" ", "+"))
    return out


def resolve_target(email: str) -> tuple[dict[str, Any] | None, str]:
    """
    邮箱或 +tag 别名 -> (账号, filter_to)。
    解析顺序与 routers/mail.py 的 lookup 保持一致。
    """
    for addr in _candidates(email):
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


def fetch_recent(email: str) -> tuple[list[dict[str, Any]] | None, str | None, str]:
    """取最近 SCAN_LIMIT 封（带 8 秒缓存）。返回 (消息列表, 错误, 解析出的真实地址)。"""
    account, filter_to = resolve_target(email)
    if not account:
        return None, "邮箱不存在", ""

    key = (int(account["id"]), filter_to)
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[1] < RESULT_TTL:
            return hit[0]["messages"], None, filter_to

    full = db.get_account(int(account["id"]), secrets=True)
    if not full:
        return None, "邮箱不存在", ""

    result, new_refresh = mail_service.fetch_messages(
        full, page=1, per_page=SCAN_LIMIT, filter_to=filter_to
    )
    if new_refresh and new_refresh != full.get("refresh_token"):
        db.update_account(int(account["id"]), refresh_token=new_refresh)
    if "error" in result:
        return None, result["error"], filter_to

    messages = result.get("messages", [])
    with _lock:
        _cache[key] = ({"messages": messages}, now)
        if len(_cache) > 500:
            for k, (_, ts) in list(_cache.items()):
                if now - ts > RESULT_TTL:
                    _cache.pop(k, None)
            while len(_cache) > 500:
                _cache.pop(min(_cache, key=lambda k: _cache[k][1]), None)
    return messages, None, filter_to


def latest_code(email: str, within_minutes: int | None = None) -> tuple[dict[str, Any] | None, str | None]:
    """
    返回最近一封带验证码的邮件。
    within_minutes 用于避免脚本拿到上一轮流程留下的旧码。
    """
    messages, err, resolved = fetch_recent(email)
    if err:
        return None, err

    for m in messages or []:
        if not m.get("codes"):
            continue
        age = _age_seconds(m.get("date", ""))
        if within_minutes is not None:
            # Date 头由发件人完全控制。解析不出年龄时必须按"不满足"处理，
            # 否则去掉 Date 头就能绕过这个时间窗 —— 而它的用途正是防止取到旧码。
            if age is None or age > within_minutes * 60:
                # 列表按 UID 新到旧排序，后面只会更旧
                break
        return {
            # 回显解析后的真实地址，便于调用方确认 + 号被正确还原。
            # 复用 fetch_recent 已解析的结果，不再查一次库。
            "email": resolved or email,
            "code": m["codes"][0],
            "codes": m["codes"],
            "subject": m.get("subject", ""),
            "from": m.get("from", ""),
            "date": m.get("date", ""),
            "uid": m.get("uid"),
            "age_seconds": age,
        }, None
    return None, None
