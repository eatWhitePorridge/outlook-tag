from flask import Flask, request, jsonify, render_template, session, redirect
from db import (init_db, list_accounts, get_account, get_account_by_email,
                create_account, update_account, delete_account,
                list_aliases, create_alias, delete_alias, get_account_by_alias)
from mail_service import fetch_messages, fetch_single_message
import random
import string
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "outlook-tag-secret-key-2026")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "17605209236qQ.")

init_db()


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin"):
            if request.is_json:
                return jsonify({"error": "未登录"}), 401
            return redirect("/admin/login")
        return f(*args, **kwargs)
    return decorated


@app.route("/")
def user_index():
    return render_template("user.html")


@app.route("/admin")
@admin_required
def admin_index():
    return render_template("index.html")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        data = request.form if request.form else request.json
        pwd = data.get("password", "")
        if pwd == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/admin")
        return render_template("login.html", error="密码错误")
    return render_template("login.html", error=None)


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect("/admin/login")


@app.route("/api/accounts", methods=["GET"])
@admin_required
def api_list_accounts():
    return jsonify(list_accounts())


@app.route("/api/accounts/<int:account_id>", methods=["GET"])
@admin_required
def api_get_account_detail(account_id):
    account = get_account(account_id)
    if not account:
        return jsonify({"error": "账号不存在"}), 404
    return jsonify({
        "id": account["id"],
        "email": account["email"],
        "password": account["password"],
        "client_id": account["client_id"],
        "refresh_token": account["refresh_token"],
    })


@app.route("/api/accounts", methods=["POST"])
@admin_required
def api_create_account():
    data = request.json
    raw = data.get("raw", "").strip()
    if raw:
        parts = raw.split("----")
        if len(parts) == 4:
            email_addr = parts[0]
            password = parts[1]
            # 自动判断: UUID 格式的是 client_id，长字符串是 refresh_token
            field3, field4 = parts[2], parts[3]
            import re as _re
            if _re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', field3):
                client_id, refresh_token = field3, field4
            elif _re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', field4):
                client_id, refresh_token = field4, field3
            else:
                client_id, refresh_token = field3, field4
        else:
            return jsonify({"error": "格式错误，需要: 邮箱----密码----client_id----refresh_token"}), 400
    else:
        email_addr = data.get("email", "")
        password = data.get("password", "")
        client_id = data.get("client_id", "")
        refresh_token = data.get("refresh_token", "")

    if not email_addr or not client_id or not refresh_token:
        return jsonify({"error": "邮箱、client_id、refresh_token 不能为空"}), 400

    account_id = create_account(email_addr, password, client_id, refresh_token)
    return jsonify({"id": account_id, "email": email_addr})


@app.route("/api/accounts/<int:account_id>", methods=["PUT"])
@admin_required
def api_update_account(account_id):
    data = request.json
    fields = {}
    for key in ("email", "password", "client_id", "refresh_token"):
        if key in data:
            fields[key] = data[key]
    if not fields:
        return jsonify({"error": "没有要更新的字段"}), 400
    update_account(account_id, **fields)
    return jsonify({"ok": True})


@app.route("/api/accounts/<int:account_id>", methods=["DELETE"])
@admin_required
def api_delete_account(account_id):
    delete_account(account_id)
    return jsonify({"ok": True})


@app.route("/api/accounts/<int:account_id>/messages", methods=["GET"])
def api_get_messages(account_id):
    account = get_account(account_id)
    if not account:
        return jsonify({"error": "账号不存在"}), 404
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    filter_to = request.args.get("filter_to", None)
    result, new_refresh_token = fetch_messages(account, page=page, per_page=per_page, filter_to=filter_to)
    if "error" in result:
        return jsonify(result), 500
    if new_refresh_token and new_refresh_token != account["refresh_token"]:
        update_account(account_id, refresh_token=new_refresh_token)
    return jsonify(result)


@app.route("/api/accounts/<int:account_id>/messages/<uid>", methods=["GET"])
def api_get_message_detail(account_id, uid):
    account = get_account(account_id)
    if not account:
        return jsonify({"error": "账号不存在"}), 404
    result, new_refresh_token = fetch_single_message(account, uid)
    if "error" in result:
        return jsonify(result), 500
    if new_refresh_token and new_refresh_token != account["refresh_token"]:
        update_account(account_id, refresh_token=new_refresh_token)
    return jsonify(result)


@app.route("/api/lookup", methods=["POST"])
def api_lookup():
    data = request.json
    email_addr = data.get("email", "").strip()
    if not email_addr:
        return jsonify({"error": "请输入邮箱地址"}), 400
    # 先查主邮箱
    account = get_account_by_email(email_addr)
    if account:
        return jsonify({"id": account["id"], "display": email_addr, "filter_to": email_addr})
    # 再查别名
    account = get_account_by_alias(email_addr)
    if account:
        return jsonify({"id": account["id"], "display": email_addr, "filter_to": email_addr})
    return jsonify({"error": "邮箱不存在"}), 404


@app.route("/api/accounts/<int:account_id>/aliases", methods=["GET"])
@admin_required
def api_list_aliases(account_id):
    return jsonify(list_aliases(account_id))


@app.route("/api/accounts/<int:account_id>/aliases", methods=["POST"])
@admin_required
def api_create_alias(account_id):
    account = get_account(account_id)
    if not account:
        return jsonify({"error": "账号不存在"}), 404
    data = request.json
    tag = data.get("tag", "").strip()
    if not tag:
        tag = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    local, domain = account["email"].split("@", 1)
    alias = f"{local}+{tag}@{domain}"
    try:
        alias_id = create_alias(account_id, alias, tag)
    except Exception:
        return jsonify({"error": "别名已存在"}), 400
    return jsonify({"id": alias_id, "alias": alias, "tag": tag})


@app.route("/api/aliases/<int:alias_id>", methods=["DELETE"])
@admin_required
def api_delete_alias(alias_id):
    delete_alias(alias_id)
    return jsonify({"ok": True})


if __name__ == "__main__":
    import os
    debug = os.environ.get("DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=8080, debug=debug)
