import os
import re
import time
import imaplib
import email
import base64
from email.header import decode_header
import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")
EMAIL = os.getenv("EMAIL")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "30"))

TOKEN_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
IMAP_HOST = "outlook.office365.com"
IMAP_PORT = 993

access_token = None
current_refresh_token = REFRESH_TOKEN
seen_uids = set()


def get_access_token():
    global access_token, current_refresh_token
    data = {
        "client_id": CLIENT_ID,
        "grant_type": "refresh_token",
        "refresh_token": current_refresh_token,
    }
    resp = requests.post(TOKEN_URL, data=data)
    if resp.status_code != 200:
        print(f"[错误] 获取 token 失败: {resp.status_code} {resp.text}")
        return False
    token_data = resp.json()
    access_token = token_data["access_token"]
    if "refresh_token" in token_data:
        current_refresh_token = token_data["refresh_token"]
    return True


def build_xoauth2_string(user, token):
    auth_string = f"user={user}\x01auth=Bearer {token}\x01\x01"
    return auth_string


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
            content_type = part.get_content_type()
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        charset = msg.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")
    return ""


def extract_codes(text):
    return re.findall(r"\b\d{4,8}\b", text)


def init_seen_uids():
    """首次运行时记录所有已有未读邮件UID，不处理它们"""
    global seen_uids, access_token
    try:
        imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        auth_string = build_xoauth2_string(EMAIL, access_token)
        imap.authenticate("XOAUTH2", lambda x: auth_string.encode())
        imap.select("INBOX")
        status, data = imap.uid("search", None, "UNSEEN")
        if status == "OK" and data[0]:
            uids = data[0].split()
            seen_uids = set(uids)
            print(f"[信息] 跳过 {len(seen_uids)} 封已有未读邮件，只监听新邮件")
        imap.logout()
    except Exception as e:
        print(f"[警告] 初始化时出错: {e}")


def check_mail():
    global access_token, seen_uids
    try:
        imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        auth_string = build_xoauth2_string(EMAIL, access_token)
        imap.authenticate("XOAUTH2", lambda x: auth_string.encode())
    except imaplib.IMAP4.error as e:
        error_msg = str(e)
        if "AUTHENTICATE" in error_msg:
            print("[信息] Token 可能过期，正在刷新...")
            if not get_access_token():
                return
            try:
                imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
                auth_string = build_xoauth2_string(EMAIL, access_token)
                imap.authenticate("XOAUTH2", lambda x: auth_string.encode())
            except Exception as e2:
                print(f"[错误] 重新认证失败: {e2}")
                return
        else:
            print(f"[错误] IMAP 连接失败: {e}")
            return

    imap.select("INBOX")
    status, data = imap.uid("search", None, "UNSEEN")
    if status != "OK":
        imap.logout()
        return

    uids = data[0].split()
    for uid in uids:
        if uid in seen_uids:
            continue
        seen_uids.add(uid)

        status, msg_data = imap.uid("fetch", uid, "(RFC822)")
        if status != "OK":
            continue

        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        subject = decode_mime_header(msg.get("Subject", ""))
        sender = decode_mime_header(msg.get("From", ""))
        date_str = msg.get("Date", "")
        body = get_email_body(msg)

        codes = extract_codes(subject) + extract_codes(body)
        if codes:
            print(f"\n{'='*50}")
            print(f"[验证码] {', '.join(set(codes))}")
            print(f"  发件人: {sender}")
            print(f"  主题: {subject}")
            print(f"  时间: {date_str}")
            print(f"{'='*50}\n")

    imap.logout()


def main():
    print(f"[启动] 邮箱验证码检查器 (IMAP)")
    print(f"[邮箱] {EMAIL}")
    print(f"[配置] 每 {CHECK_INTERVAL} 秒检查一次")
    print()

    if not get_access_token():
        print("[错误] 无法获取 access token，请检查凭据")
        return

    print("[成功] Token 获取成功")
    init_seen_uids()
    print("[监听] 开始监听新邮件...\n")

    while True:
        try:
            check_mail()
        except Exception as e:
            print(f"[错误] {e}")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
