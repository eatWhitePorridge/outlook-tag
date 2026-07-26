import email as email_lib
import imaplib
import logging
import re
import threading
import time
from contextlib import contextmanager
from email.header import decode_header
from typing import Any

import requests

log = logging.getLogger(__name__)

TOKEN_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
IMAP_HOST = "outlook.office365.com"
IMAP_PORT = 993
IMAP_TTL = 270

_token_cache: dict[int, tuple[str, float, str]] = {}
_imap_cache: dict[int, tuple[imaplib.IMAP4_SSL, float]] = {}
_lock = threading.Lock()

# 每账号一把锁。imaplib 不是线程安全的，而后台调度器线程与 HTTP 请求线程
# 会从 _imap_cache 拿到同一个连接对象 —— 两边同时发命令会让标签响应错配，
# 轻则 abort，重则把一个请求的邮件正文返回给另一个请求。
_account_locks: dict[int, threading.Lock] = {}

# UID 搜索结果缓存：翻页时不必每次重跑 IMAP SEARCH
_search_cache: dict[tuple[int, str], tuple[list[bytes], float]] = {}
SEARCH_TTL = 60
# codes_only 需要拉正文才能判断，扫描量必须封顶，否则大信箱会拖死请求
CODES_SCAN_CAP = 600
# 列表页每封邮件抓取的字节数：要足够穿过 HTML 的 <head>/CSS 找到验证码，
# 又不能大到把带附件的邮件整封拉下来
PREVIEW_BYTES = 24576


def _account_lock(account_id: int) -> threading.Lock:
    with _lock:
        lk = _account_locks.get(account_id)
        if lk is None:
            lk = threading.Lock()
            _account_locks[account_id] = lk
        return lk


@contextmanager
def imap_session(account: dict[str, Any]):
    """
    独占该账号的 IMAP 连接，直到整段命令序列（select + search + fetch）结束。

    只锁缓存字典是不够的 —— 必须锁住连接的整个使用期间，
    否则两个线程仍会在同一个 socket 上交错发命令。
    """
    with _account_lock(account["id"]):
        yield get_imap_connection(account)


def get_access_token(account: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    """调用方必须已持有该账号的锁 —— 否则两个线程会拿同一个
    refresh_token 各刷一次，而微软的 refresh token 是一次性轮换的，
    后一次会让前一次作废，账号直接报废。"""
    account_id = account["id"]
    now = time.time()
    with _lock:
        cached = _token_cache.get(account_id)
    if cached:
        cached_token, expire_time, cached_refresh = cached
        if now < expire_time - 60:
            return cached_token, cached_refresh, None

    refresh_token = cached[2] if cached else account["refresh_token"]
    data = {
        "client_id": account["client_id"],
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": "https://outlook.office.com/IMAP.AccessAsUser.All offline_access",
    }
    try:
        resp = requests.post(TOKEN_URL, data=data, timeout=20)
        if resp.status_code != 200:
            return None, None, f"token_invalid: {resp.status_code}"
        # resp.json() 与取 access_token 都可能抛（网关返回 HTML、字段缺失），
        # 必须在 try 内，否则会一路逃到路由层变成裸 500
        token_data = resp.json()
        access_token = token_data["access_token"]
    except requests.RequestException as e:
        return None, None, f"token_request_failed: {e}"
    except (ValueError, KeyError, TypeError) as e:
        return None, None, f"token_malformed: {e}"

    new_refresh = token_data.get("refresh_token", account["refresh_token"])
    expires_in = token_data.get("expires_in", 3600)
    with _lock:
        _token_cache[account_id] = (access_token, now + expires_in, new_refresh)
    return access_token, new_refresh, None


def get_imap_connection(account: dict[str, Any]) -> tuple[imaplib.IMAP4_SSL | None, str | None, str | None]:
    """内部函数：调用方须已持有该账号的锁，请用 imap_session()。"""
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
    """
    errors="replace" 只挡坏字节，挡不住坏的编码名 ——
    `=?unknown-8bit?B?...?=`（RFC 1428 标准写法）会让 bytes.decode 抛 LookupError。
    一封这样的邮件此前足以让整页 500 且永久无法加载。
    """
    if not header_value:
        return ""
    try:
        parts = decode_header(header_value)
    except Exception:
        return str(header_value)
    decoded: list[str] = []
    for part, charset in parts:
        if not isinstance(part, bytes):
            decoded.append(str(part))
            continue
        try:
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        except (LookupError, UnicodeError):
            decoded.append(part.decode("utf-8", errors="replace"))
    return "".join(decoded)


_CODE_KEYWORDS = (
    r"(?:验证码|校验码|驗證碼|动态密码|登录代码|登入代碼|安全代码|"
    r"verification\s*code|security\s*code|one[-\s]?time\s*(?:code|password|passcode)|"
    r"passcode|access\s*code|login\s*code|confirmation\s*code|código|otp|pin\s*code)"
)
_YEAR_RE = re.compile(r"(?:19|20)\d{2}")
# 各公司总部邮编，常年出现在邮件页脚，会被当成验证码
_KNOWN_ZIPS = {"95014", "98052", "94105", "98109", "94103", "10011"}


def _plausible_code(n: str) -> bool:
    if _YEAR_RE.fullmatch(n) or n in _KNOWN_ZIPS:
        return False
    return not (len(set(n)) == 1)  # 000000 之类


def extract_codes(text: str) -> list[str]:
    """
    先找关键词邻近的数字；找不到再兜底。

    兜底只认 6 位：实测线上邮件里 4-5 位的匹配几乎全是噪声
    —— 年份、邮编，以及 charset="iso-8859-1" 里的 8859。
    """
    if not text:
        return []
    near = re.findall(_CODE_KEYWORDS + r"[^0-9A-Za-z]{0,40}(\d{4,8})", text, flags=re.I)
    if not near:
        near = re.findall(r"\b\d{6}\b", text)
    return [n for n in dict.fromkeys(near) if _plausible_code(n)]


# 原来是 `<(script|style).*?>.*?</\1>` —— 两个惰性量词加反向引用，
# 遇到没有闭合标签的正文会灾难性回溯：实测 24KB 输入耗时数分钟，
# 而 PREVIEW_BYTES 正好是 24576，一封构造的邮件就能占满一个 CPU 核。
# 拆成两条无反向引用、且以 \Z 兜底保证终止的模式。
_SCRIPT_RE = re.compile(r"(?is)<script\b[^>]*>.*?(?:</script\s*>|\Z)")
_STYLE_RE = re.compile(r"(?is)<style\b[^>]*>.*?(?:</style\s*>|\Z)")


def _strip_html(html: str) -> str:
    if not html:
        return ""
    text = _STYLE_RE.sub(" ", _SCRIPT_RE.sub(" ", html))
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


def _extract_bodies(msg) -> tuple[str, str, list[dict[str, Any]]]:
    """
    取最佳 html + 纯文本正文，同时顺带收集附件元信息。

    附件的 index 是 msg.walk() 的遍历序号，下载端点按同样的遍历顺序定位，
    因此对同一封邮件是稳定的。
    """
    html_body = ""
    text_body = ""
    attachments: list[dict[str, Any]] = []

    if msg.is_multipart():
        for i, part in enumerate(msg.walk()):
            if part.get_content_maintype() == "multipart":
                continue
            disposition = part.get_content_disposition()
            filename = decode_mime_header(part.get_filename() or "")
            if disposition == "attachment" or (filename and disposition != "inline"):
                payload = part.get_payload(decode=True) or b""
                attachments.append(
                    {
                        "index": i,
                        "filename": filename or f"attachment-{i}",
                        "content_type": part.get_content_type(),
                        "size": len(payload),
                    }
                )
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

    return html_body, text_body, attachments


def fetch_attachment(
    account: dict[str, Any], uid: str, index: int
) -> tuple[dict[str, Any] | None, str | None]:
    """按 walk() 序号取出单个附件的原始字节。"""
    with imap_session(account) as (imap, new_refresh, err):
        if err or not imap:
            return None, err or "连接失败"
        try:
            imap.select("INBOX", readonly=True)
            status, msg_data = imap.uid("fetch", uid.encode(), "(RFC822)")
            if status != "OK" or not msg_data or not msg_data[0]:
                return None, "邮件不存在"
            msg = email_lib.message_from_bytes(msg_data[0][1])
            for i, part in enumerate(msg.walk()):
                if i != index:
                    continue
                if part.get_content_maintype() == "multipart":
                    return None, "该位置不是附件"
                filename = decode_mime_header(part.get_filename() or "") or f"attachment-{i}"
                return {
                    "filename": filename,
                    "content_type": part.get_content_type(),
                    "data": part.get_payload(decode=True) or b"",
                }, None
            return None, "附件不存在"
        except Exception as e:
            return None, str(e)


def _new_refresh(account: dict[str, Any]) -> str | None:
    entry = _token_cache.get(account["id"])
    return entry[2] if entry else None


def probe_account(account: dict[str, Any]) -> dict[str, Any]:
    with imap_session(account) as (imap, new_refresh, err):
        if err or not imap:
            return {"ok": False, "error": err or "unknown", "refresh_token": new_refresh}
        try:
            status, _ = imap.select("INBOX", readonly=True)
            if status != "OK":
                return {"ok": False, "error": "select_failed", "refresh_token": new_refresh}
            return {"ok": True, "error": "", "refresh_token": new_refresh}
        except Exception as e:
            return {"ok": False, "error": f"probe_failed: {e}", "refresh_token": new_refresh}


def _imap_safe(value: str) -> str:
    """
    清洗进入 IMAP 检索条件的字符串。

    实测 outlook.office365.com：引号无论是否用 \\" 转义，都会让 SEARCH 返回
    BAD "The specified message set is invalid."，所以只能剔除而不是转义。
    括号经实测是安全的，予以保留。
    """
    return "".join(ch for ch in value if ch not in '"\\' and ch.isprintable()).strip()


def _searchable_on_server(value: str) -> bool:
    """
    Outlook IMAP 的 SEARCH 只接受 US-ASCII —— 声明 CHARSET UTF-8 会被拒：
    NO [BADCHARSET (US-ASCII)] The specified charset is not supported.
    因此非 ASCII 关键词只能退回本地过滤。
    """
    return value.isascii()


def _alias_matches(msg: dict[str, Any], filter_to: str | None) -> bool:
    """
    IMAP 的 HEADER To 是子串匹配：搜 tag "test" 会把发给 +test2 的信一并命中，
    两个别名互相泄露。服务端只能搜到候选，最终边界要在这里收紧。

    只做剔除（服务端已保证候选都含该 tag），所以不会漏掉合法邮件。
    """
    if not filter_to or "+" not in filter_to:
        return True
    want = filter_to.strip().lower()
    return want in (msg.get("to") or "").lower()


class AliasFilterUnsupported(Exception):
    """别名无法安全地转成 IMAP 条件。宁可报错也不能退化成不过滤。"""


def _build_criteria(filter_to: str | None, search: str | None, search_field: str) -> str:
    """把别名过滤与关键词搜索合成一条 IMAP SEARCH 条件（隐式 AND）。"""
    parts: list[str] = []
    if filter_to:
        # Outlook IMAP 不支持含 + 号的完整地址搜索，退化为搜 tag 片段
        needle = filter_to.split("+", 1)[1].split("@")[0] if "+" in filter_to else filter_to
        needle = _imap_safe(needle)
        if not needle:
            # 之前这里会静默跳过，parts 为空则整条退化成 "ALL" ——
            # 别名边界直接消失，读到同账号其他别名的验证码
            raise AliasFilterUnsupported(filter_to)
        parts.append(f'HEADER To "{needle}"')
    if search and _searchable_on_server(search):
        term = _imap_safe(search)
        if term:
            key = {"from": "FROM", "text": "TEXT"}.get(search_field, "SUBJECT")
            parts.append(f'{key} "{term}"')
    return f"({' '.join(parts)})" if parts else "ALL"


def _search_uids(imap, account_id: int, criteria: str) -> list[bytes] | None:
    """返回按新→旧排序的 UID 列表；60 秒内复用缓存。"""
    key = (account_id, criteria)
    now = time.time()
    with _lock:
        cached = _search_cache.get(key)
        if cached and now - cached[1] < SEARCH_TTL:
            return cached[0]

    # imaplib 默认按 ASCII 编码检索条件，中文搜索词会抛 UnicodeEncodeError；
    # 含非 ASCII 时必须显式声明 CHARSET UTF-8 并传 bytes。
    if criteria.isascii():
        status, data = imap.uid("search", None, criteria)
    else:
        status, data = imap.uid("search", "CHARSET", "UTF-8", criteria.encode("utf-8"))
    if status != "OK":
        return None
    uids = data[0].split()
    uids.reverse()
    with _lock:
        _search_cache[key] = (uids, now)
        # 先按 TTL 清，若仍超限再按时间淘汰最老的 ——
        # 只按 TTL 清的话，一分钟内涌入 200 个不同搜索词就再也清不掉了，
        # 而 criteria 含用户可控的搜索串，键空间无界
        if len(_search_cache) > 200:
            for k, (_, ts) in list(_search_cache.items()):
                if now - ts > SEARCH_TTL:
                    _search_cache.pop(k, None)
            while len(_search_cache) > 200:
                oldest = min(_search_cache, key=lambda k: _search_cache[k][1])
                _search_cache.pop(oldest, None)
    return uids


def _parse_fetch(msg_data) -> list[dict[str, Any]]:
    """
    解析 FETCH 响应为消息摘要列表。

    取的是整封邮件的前 PREVIEW_BYTES 字节并按 MIME 解析，
    而不是 BODY[1] 的原始片段 —— 后者是未解码的（quoted-printable / base64），
    且 HTML 邮件的 part 1 前 2KB 往往全是 <head> 与 CSS，
    导致验证码在列表页提取不出来（详情页却能，因为它做了解码）。
    """
    out: list[dict[str, Any]] = []
    current_parts: list[tuple] = []

    def flush() -> None:
        nonlocal current_parts
        if not current_parts:
            return
        try:
            uid_str = None
            raw = b""
            for part in current_parts:
                desc = part[0].decode("utf-8", errors="replace") if isinstance(part[0], bytes) else ""
                if "BODY[]" in desc or "RFC822" in desc:
                    raw = part[1]
                uid_match = re.search(r"UID (\d+)", desc)
                if uid_match:
                    uid_str = uid_match.group(1)
            if uid_str and raw:
                msg = email_lib.message_from_bytes(raw)
                subject = decode_mime_header(msg.get("Subject", ""))
                html_body, text_body, _ = _extract_bodies(msg)
                # 截断的邮件解出的正文可能不完整，但足够找验证码
                readable = text_body or _strip_html(html_body)
                out.append(
                    {
                        "uid": uid_str,
                        "subject": subject,
                        "from": decode_mime_header(msg.get("From", "")),
                        "to": decode_mime_header(msg.get("To", "")),
                        "date": msg.get("Date", ""),
                        "body_preview": " ".join(readable.split())[:200],
                        "codes": extract_codes(subject + " " + readable),
                    }
                )
        except Exception as e:
            # 单封坏邮件不能拖垮整页 —— 此前一封畸形邮件会让收件箱永久 500
            log.warning("跳过无法解析的邮件: %s", e)
        finally:
            current_parts = []

    for item in msg_data:
        if isinstance(item, tuple):
            current_parts.append(item)
        else:
            # 任何非 tuple 项都作为一封邮件的收尾。
            # 原来是 `item == b")"` 严格相等 —— 服务端在字面量后追加
            # FLAGS/MODSEQ 时收尾项形如 b" FLAGS (\\Seen))"，整封邮件会被默默丢掉。
            flush()
    flush()  # 末尾没有收尾项时兜底
    out.sort(key=lambda m: int(m["uid"]), reverse=True)
    return out


def _fetch_chunk(imap, uids: list[bytes]) -> list[dict[str, Any]] | None:
    if not uids:
        return []
    status, msg_data = imap.uid(
        "fetch",
        b",".join(uids),
        f"(UID BODY.PEEK[]<0.{PREVIEW_BYTES}>)",
    )
    if status != "OK":
        return None
    return _parse_fetch(msg_data)


def fetch_messages(
    account: dict[str, Any],
    page: int = 1,
    per_page: int = 20,
    filter_to: str | None = None,
    codes_only: bool = False,
    search: str | None = None,
    search_field: str = "subject",
) -> tuple[dict[str, Any], str | None]:
    with imap_session(account) as (imap, new_refresh, err):
        if err or not imap:
            return {"error": err or "连接失败", "code": "imap_error"}, None

        new_refresh = new_refresh or _new_refresh(account)
        page = max(1, page)
        per_page = min(max(1, per_page), 50)

        try:
            imap.select("INBOX", readonly=True)
            try:
                criteria = _build_criteria(filter_to, (search or "").strip() or None, search_field)
            except AliasFilterUnsupported:
                return {"error": "该别名无法安全过滤，请重建", "code": "bad_alias"}, new_refresh
            all_uids = _search_uids(imap, account["id"], criteria)
            if all_uids is None:
                return {"error": "搜索邮件失败", "code": "search_failed"}, new_refresh

            total = len(all_uids)
            term = (search or "").strip()
            # 非 ASCII 关键词服务端搜不了，退回本地过滤
            local_term = term if term and not _searchable_on_server(term) else ""

            if not codes_only and not local_term:
                start = (page - 1) * per_page
                page_uids = all_uids[start : start + per_page]
                messages = _fetch_chunk(imap, page_uids)
                if messages is None:
                    return {"error": "拉取邮件失败", "code": "fetch_failed"}, new_refresh
                messages = [m for m in messages if _alias_matches(m, filter_to)]
                return {
                    "messages": messages,
                    "total": total,
                    "page": page,
                    "per_page": per_page,
                    "total_pages": (total + per_page - 1) // per_page,
                }, new_refresh

            # 需要看正文才能判定的过滤（验证码 / 非 ASCII 关键词），
            # 服务端无法预先算出总页数：从头滚动扫描，凑够 page*per_page 条后切片，扫描量封顶。
            needle = local_term.lower()

            def keep(m: dict[str, Any]) -> bool:
                if not _alias_matches(m, filter_to):
                    return False
                if codes_only and not m["codes"]:
                    return False
                if not needle:
                    return True
                if search_field == "from":
                    return needle in (m["from"] or "").lower()
                if search_field == "text":
                    return needle in ((m["subject"] or "") + " " + (m["body_preview"] or "")).lower()
                return needle in (m["subject"] or "").lower()

            wanted = page * per_page
            matched: list[dict[str, Any]] = []
            scanned = 0
            chunk = per_page * 4
            while scanned < len(all_uids) and len(matched) <= wanted and scanned < CODES_SCAN_CAP:
                batch = all_uids[scanned : scanned + chunk]
                rows = _fetch_chunk(imap, batch)
                if rows is None:
                    return {"error": "拉取邮件失败", "code": "fetch_failed"}, new_refresh
                matched.extend(r for r in rows if keep(r))
                scanned += len(batch)

            start = (page - 1) * per_page
            window = matched[start : start + per_page]
            capped = scanned >= CODES_SCAN_CAP and scanned < len(all_uids)
            return {
                "messages": window,
                "total": total,
                "page": page,
                "per_page": per_page,
                # 过滤后的总数未知，用 has_more 驱动前端翻页。
                # 扫描被封顶时后面还有没看过的邮件，不能报"没有更多"，
                # 否则用户会以为验证码不存在。
                "has_more": len(matched) > start + per_page or capped,
                "total_pages": None,
                "scanned": scanned,
                "scan_capped": capped,
                # 前端据此提示：该关键词是本地过滤的，只覆盖已扫描范围
                "local_filter": bool(local_term),
            }, new_refresh
        except Exception as e:
            return {"error": str(e), "code": "fetch_error"}, new_refresh


def fetch_single_message(account: dict[str, Any], uid: str) -> tuple[dict[str, Any], str | None]:
    with imap_session(account) as (imap, new_refresh, err):
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

            html_body, text_body, attachments = _extract_bodies(msg)
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
                "attachments": attachments,
            }, new_refresh
        except Exception as e:
            return {"error": str(e), "code": "fetch_error"}, new_refresh
