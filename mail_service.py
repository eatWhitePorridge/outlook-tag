import re
import imaplib
import email as email_lib
from email.header import decode_header
import time
import requests

TOKEN_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
IMAP_HOST = "outlook.office365.com"
IMAP_PORT = 993

# token 缓存: {account_id: (access_token, expire_time, refresh_token)}
_token_cache = {}
# IMAP 连接缓存: {account_id: (imap_conn, last_used_time)}
_imap_cache = {}
_IMAP_TTL = 270  # 4.5 分钟后断开


def get_access_token(account):
    account_id = account["id"]
    now = time.time()
    if account_id in _token_cache:
        cached_token, expire_time, cached_refresh = _token_cache[account_id]
        if now < expire_time - 60:
            return cached_token, cached_refresh

    refresh_token = _token_cache[account_id][2] if account_id in _token_cache else account["refresh_token"]
    data = {
        "client_id": account["client_id"],
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    resp = requests.post(TOKEN_URL, data=data)
    if resp.status_code != 200:
        return None, None
    token_data = resp.json()
    access_token = token_data["access_token"]
    new_refresh_token = token_data.get("refresh_token", account["refresh_token"])
    expires_in = token_data.get("expires_in", 3600)
    _token_cache[account_id] = (access_token, now + expires_in, new_refresh_token)
    return access_token, new_refresh_token


def get_imap_connection(account):
    account_id = account["id"]
    now = time.time()

    if account_id in _imap_cache:
        imap, last_used = _imap_cache[account_id]
        if now - last_used < _IMAP_TTL:
            try:
                imap.noop()
                _imap_cache[account_id] = (imap, now)
                return imap, None
            except Exception:
                pass
        try:
            imap.logout()
        except Exception:
            pass
        del _imap_cache[account_id]

    access_token, new_refresh_token = get_access_token(account)
    if not access_token:
        return None, "Token 刷新失败，请检查凭据"

    try:
        imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        auth_string = f"user={account['email']}\x01auth=Bearer {access_token}\x01\x01"
        imap.authenticate("XOAUTH2", lambda x: auth_string.encode())
    except Exception as e:
        return None, f"IMAP 认证失败: {str(e)}"

    _imap_cache[account_id] = (imap, now)
    return imap, None


def decode_mime_header(header_value):
    if not header_value:
        return ""
    parts = decode_header(header_value)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return "".join(decoded)


def get_email_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace")
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
    return ""


def extract_codes(text):
    return list(set(re.findall(r"\b\d{4,8}\b", text)))


def fetch_messages(account, page=1, per_page=20, filter_to=None):
    imap, err = get_imap_connection(account)
    if err:
        return {"error": err}, None

    new_refresh_token = _token_cache.get(account["id"], (None, 0, account["refresh_token"]))[2]

    imap.select("INBOX")

    if filter_to:
        status, data = imap.uid("search", None, f'(TO "{filter_to}")')
    else:
        status, data = imap.uid("search", None, "ALL")
    if status != "OK":
        return {"error": "搜索邮件失败"}, None

    all_uids = data[0].split()
    total = len(all_uids)
    all_uids.reverse()

    start = (page - 1) * per_page
    end = start + per_page
    page_uids = all_uids[start:end]

    if not page_uids:
        return {"messages": [], "total": total, "page": page, "per_page": per_page, "total_pages": 0}, new_refresh_token

    # 批量 fetch: 一次请求拉取所有邮件的头部 + 正文前 2048 字节
    uid_set = b",".join(page_uids)
    status, msg_data = imap.uid("fetch", uid_set, "(UID BODY.PEEK[HEADER.FIELDS (Subject From Date)] BODY.PEEK[1]<0.2048>)")

    # 解析批量结果
    messages = []
    current_parts = []
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
                date_str = msg.get("Date", "")
                body_text = body_data.decode("utf-8", errors="replace") if body_data else ""
                codes = extract_codes(subject + " " + body_text)
                messages.append({
                    "uid": uid_str,
                    "subject": subject,
                    "from": sender,
                    "date": date_str,
                    "body_preview": body_text[:200],
                    "codes": codes,
                })
            current_parts = []

    messages.sort(key=lambda m: int(m["uid"]), reverse=True)

    return {
        "messages": messages,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    }, new_refresh_token


def fetch_single_message(account, uid):
    imap, err = get_imap_connection(account)
    if err:
        return {"error": err}, None

    new_refresh_token = _token_cache.get(account["id"], (None, 0, account["refresh_token"]))[2]

    imap.select("INBOX")
    status, msg_data = imap.uid("fetch", uid.encode(), "(RFC822)")
    if status != "OK":
        return {"error": "邮件不存在"}, None

    raw_email = msg_data[0][1]
    msg = email_lib.message_from_bytes(raw_email)

    subject = decode_mime_header(msg.get("Subject", ""))
    sender = decode_mime_header(msg.get("From", ""))
    to = decode_mime_header(msg.get("To", ""))
    date_str = msg.get("Date", "")

    html_body = ""
    text_body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            charset = part.get_content_charset() or "utf-8"
            decoded = payload.decode(charset, errors="replace")
            if ct == "text/html":
                html_body = decoded
            elif ct == "text/plain":
                text_body = decoded
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            decoded = payload.decode(charset, errors="replace")
            if msg.get_content_type() == "text/html":
                html_body = decoded
            else:
                text_body = decoded

    body = html_body or text_body
    codes = extract_codes(subject + " " + text_body + " " + html_body)

    return {
        "uid": uid,
        "subject": subject,
        "from": sender,
        "to": to,
        "date": date_str,
        "body": body,
        "is_html": bool(html_body),
        "codes": codes,
    }, new_refresh_token
