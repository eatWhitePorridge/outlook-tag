import email as email_lib
import imaplib
import re
import threading
import time
from email.header import decode_header
from typing import Any

import requests

TOKEN_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
IMAP_HOST = "outlook.office365.com"
IMAP_PORT = 993
IMAP_TTL = 270

_token_cache: dict[int, tuple[str, float, str]] = {}
_imap_cache: dict[int, tuple[imaplib.IMAP4_SSL, float]] = {}
_lock = threading.Lock()


def get_access_token(account: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    account_id = account["id"]
    now = time.time()
    with _lock:
        if account_id in _token_cache:
            cached_token, expire_time, cached_refresh = _token_cache[account_id]
            if now < expire_time - 60:
                return cached_token, cached_refresh, None

    refresh_token = (
        _token_cache[account_id][2]
        if account_id in _token_cache
        else account["refresh_token"]
    )
    data = {
        "client_id": account["client_id"],
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": "https://outlook.office.com/IMAP.AccessAsUser.All offline_access",
    }
    try:
        resp = requests.post(TOKEN_URL, data=data, timeout=20)
    except requests.RequestException as e:
        return None, None, f"token_request_failed: {e}"
    if resp.status_code != 200:
        return None, None, f"token_invalid: {resp.status_code}"
    token_data = resp.json()
    access_token = token_data["access_token"]
    new_refresh = token_data.get("refresh_token", account["refresh_token"])
    expires_in = token_data.get("expires_in", 3600)
    with _lock:
        _token_cache[account_id] = (access_token, now + expires_in, new_refresh)
    return access_token, new_refresh, None


def get_imap_connection(account: dict[str, Any]) -> tuple[imaplib.IMAP4_SSL | None, str | None, str | None]:
    account_id = account["id"]
    now = time.time()

    with _lock:
        cached = _imap_cache.get(account_id)
    if cached:
        imap, last_used = cached
        if now - last_used < IMAP_TTL:
            try:
                imap.noop()
                with _lock:
                    _imap_cache[account_id] = (imap, now)
                return imap, None, None
            except Exception:
                pass
        try:
            imap.logout()
        except Exception:
            pass
        with _lock:
            _imap_cache.pop(account_id, None)

    access_token, new_refresh, err = get_access_token(account)
    if not access_token:
        return None, None, err or "token_invalid"

    try:
        imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, timeout=30)
        auth_string = f"user={account['email']}\x01auth=Bearer {access_token}\x01\x01"
        imap.authenticate("XOAUTH2", lambda x: auth_string.encode())
    except Exception as e:
        return None, new_refresh, f"imap_auth: {e}"

    with _lock:
        _imap_cache[account_id] = (imap, now)
    return imap, new_refresh, None


def decode_mime_header(header_value: str | None) -> str:
    if not header_value:
        return ""
    parts = decode_header(header_value)
    decoded: list[str] = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return "".join(decoded)


def extract_codes(text: str) -> list[str]:
    if not text:
        return []
    preferred = re.findall(
        r"(?:验证码|校验码|code|otp|pin)[^\d]{0,12}(\d{4,8})",
        text,
        flags=re.I,
    )
    if preferred:
        return list(dict.fromkeys(preferred))
    return list(dict.fromkeys(re.findall(r"\b\d{4,8}\b", text)))


def _strip_html(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    return re.sub(r"[ \t]+\n", "\n", re.sub(r"[ \t]{2,}", " ", text)).strip()


def _decode_part(part) -> str:
    payload = part.get_payload(decode=True)
    if not payload:
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def _extract_bodies(msg) -> tuple[str, str]:
    """Prefer multipart/alternative: take best html + plain parts."""
    html_body = ""
    text_body = ""

    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            if part.get_content_disposition() == "attachment":
                continue
            ct = part.get_content_type()
            decoded = _decode_part(part)
            if not decoded:
                continue
            if ct == "text/html" and (not html_body or len(decoded) > len(html_body)):
                html_body = decoded
            elif ct == "text/plain" and (not text_body or len(decoded) > len(text_body)):
                text_body = decoded
    else:
        decoded = _decode_part(msg)
        if msg.get_content_type() == "text/html":
            html_body = decoded
        else:
            text_body = decoded

    return html_body, text_body


def _new_refresh(account: dict[str, Any]) -> str | None:
    entry = _token_cache.get(account["id"])
    return entry[2] if entry else None


def probe_account(account: dict[str, Any]) -> dict[str, Any]:
    imap, new_refresh, err = get_imap_connection(account)
    if err or not imap:
        return {"ok": False, "error": err or "unknown", "refresh_token": new_refresh}
    try:
        status, _ = imap.select("INBOX", readonly=True)
        if status != "OK":
            return {"ok": False, "error": "select_failed", "refresh_token": new_refresh}
        return {"ok": True, "error": "", "refresh_token": new_refresh}
    except Exception as e:
        return {"ok": False, "error": f"probe_failed: {e}", "refresh_token": new_refresh}


def fetch_messages(
    account: dict[str, Any],
    page: int = 1,
    per_page: int = 20,
    filter_to: str | None = None,
    codes_only: bool = False,
) -> tuple[dict[str, Any], str | None]:
    imap, new_refresh, err = get_imap_connection(account)
    if err or not imap:
        return {"error": err or "连接失败", "code": "imap_error"}, None

    new_refresh = new_refresh or _new_refresh(account)
    try:
        imap.select("INBOX", readonly=True)
        if filter_to:
            if "+" in filter_to:
                tag_part = filter_to.split("+", 1)[1].split("@")[0]
                status, data = imap.uid("search", None, f'(HEADER To "{tag_part}")')
            else:
                status, data = imap.uid("search", None, f'(HEADER To "{filter_to}")')
        else:
            status, data = imap.uid("search", None, "ALL")
        if status != "OK":
            return {"error": "搜索邮件失败", "code": "search_failed"}, new_refresh

        all_uids = data[0].split()
        total = len(all_uids)
        all_uids.reverse()
        page = max(1, page)
        per_page = min(max(1, per_page), 50)
        start = (page - 1) * per_page
        end = start + per_page
        page_uids = all_uids[start:end]
        if not page_uids:
            return {
                "messages": [],
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": 0,
            }, new_refresh

        uid_set = b",".join(page_uids)
        status, msg_data = imap.uid(
            "fetch",
            uid_set,
            "(UID BODY.PEEK[HEADER.FIELDS (Subject From Date To)] BODY.PEEK[1]<0.2048>)",
        )
        if status != "OK":
            return {"error": "拉取邮件失败", "code": "fetch_failed"}, new_refresh

        messages: list[dict[str, Any]] = []
        current_parts: list[tuple] = []
        for item in msg_data:
            if isinstance(item, tuple):
                current_parts.append(item)
            elif item == b")" and current_parts:
                uid_str = None
                header_data = b""
                body_data = b""
                for part in current_parts:
                    desc = part[0].decode("utf-8", errors="replace") if isinstance(part[0], bytes) else ""
                    if "HEADER.FIELDS" in desc:
                        header_data = part[1]
                    elif "BODY[1]" in desc:
                        body_data = part[1]
                    uid_match = re.search(r"UID (\d+)", desc)
                    if uid_match:
                        uid_str = uid_match.group(1)
                if uid_str:
                    msg = email_lib.message_from_bytes(header_data)
                    subject = decode_mime_header(msg.get("Subject", ""))
                    sender = decode_mime_header(msg.get("From", ""))
                    to = decode_mime_header(msg.get("To", ""))
                    date_str = msg.get("Date", "")
                    body_text = body_data.decode("utf-8", errors="replace") if body_data else ""
                    codes = extract_codes(subject + " " + body_text)
                    if codes_only and not codes:
                        current_parts = []
                        continue
                    messages.append(
                        {
                            "uid": uid_str,
                            "subject": subject,
                            "from": sender,
                            "to": to,
                            "date": date_str,
                            "body_preview": body_text[:200],
                            "codes": codes,
                        }
                    )
                current_parts = []

        messages.sort(key=lambda m: int(m["uid"]), reverse=True)
        return {
            "messages": messages,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page,
        }, new_refresh
    except Exception as e:
        return {"error": str(e), "code": "fetch_error"}, new_refresh


def fetch_single_message(account: dict[str, Any], uid: str) -> tuple[dict[str, Any], str | None]:
    imap, new_refresh, err = get_imap_connection(account)
    if err or not imap:
        return {"error": err or "连接失败", "code": "imap_error"}, None

    new_refresh = new_refresh or _new_refresh(account)
    try:
        imap.select("INBOX", readonly=True)
        status, msg_data = imap.uid("fetch", uid.encode(), "(RFC822)")
        if status != "OK" or not msg_data or not msg_data[0]:
            return {"error": "邮件不存在", "code": "not_found"}, new_refresh

        raw_email = msg_data[0][1]
        msg = email_lib.message_from_bytes(raw_email)
        subject = decode_mime_header(msg.get("Subject", ""))
        sender = decode_mime_header(msg.get("From", ""))
        to = decode_mime_header(msg.get("To", ""))
        date_str = msg.get("Date", "")

        html_body, text_body = _extract_bodies(msg)
        body = html_body or text_body
        codes = extract_codes(subject + " " + text_body + " " + _strip_html(html_body))
        return {
            "uid": uid,
            "subject": subject,
            "from": sender,
            "to": to,
            "date": date_str,
            "body": body,
            "text_body": text_body,
            "is_html": bool(html_body),
            "codes": codes,
        }, new_refresh
    except Exception as e:
        return {"error": str(e), "code": "fetch_error"}, new_refresh
