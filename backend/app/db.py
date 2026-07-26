import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.config import get_settings

_local = threading.local()


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def get_connection() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        path = Path(get_settings().resolve_db_path())
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
        _local.conn = conn
    return conn


@contextmanager
def db_cursor() -> Iterator[sqlite3.Cursor]:
    conn = get_connection()
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db() -> None:
    with db_cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                password TEXT DEFAULT '',
                client_id TEXT NOT NULL,
                refresh_token TEXT NOT NULL,
                note TEXT DEFAULT '',
                status TEXT DEFAULT 'unknown',
                last_checked_at TEXT,
                last_error TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                alias TEXT NOT NULL UNIQUE,
                tag TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ops_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                target TEXT DEFAULT '',
                detail TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                key_hash TEXT NOT NULL UNIQUE,
                prefix TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                calls INTEGER DEFAULT 0,
                last_used_at TEXT,
                last_target TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_accounts_email ON accounts(email)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_accounts_status ON accounts(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_accounts_updated ON accounts(updated_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_accounts_checked ON accounts(last_checked_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_aliases_account ON aliases(account_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ops_log_created ON ops_log(created_at DESC)")
        _ensure_default_settings(cur)


DEFAULT_SETTINGS = {
    "probe_enabled": "1",
    "probe_interval_minutes": "10",
    "probe_batch_size": "40",
    "probe_workers": "6",
    "probe_stale_hours": "24",
}


def _ensure_default_settings(cur: sqlite3.Cursor) -> None:
    now = _utc_now()
    for key, value in DEFAULT_SETTINGS.items():
        cur.execute(
            "INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, now),
        )


def get_setting(key: str, default: str | None = None) -> str | None:
    with db_cursor() as cur:
        row = cur.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row:
        return row["value"]
    return default if default is not None else DEFAULT_SETTINGS.get(key)


def get_settings_map(keys: list[str] | None = None) -> dict[str, str]:
    wanted = keys or list(DEFAULT_SETTINGS.keys())
    result = {k: DEFAULT_SETTINGS.get(k, "") for k in wanted}
    with db_cursor() as cur:
        placeholders = ",".join("?" * len(wanted))
        rows = cur.execute(
            f"SELECT key, value FROM settings WHERE key IN ({placeholders})",
            wanted,
        ).fetchall()
    for r in rows:
        result[r["key"]] = r["value"]
    return result


def set_settings(values: dict[str, str]) -> dict[str, str]:
    now = _utc_now()
    with db_cursor() as cur:
        for key, value in values.items():
            cur.execute(
                """
                INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (key, str(value), now),
            )
    return get_settings_map(list(values.keys()) if values else None)


def list_accounts_for_probe(limit: int = 40, stale_hours: int = 24) -> list[dict[str, Any]]:
    """Prefer unknown, then oldest checked / never checked within stale window."""
    limit = min(max(1, limit), 200)
    stale_hours = max(1, stale_hours)
    with db_cursor() as cur:
        rows = cur.execute(
            """
            SELECT id, email, status, last_checked_at
            FROM accounts
            ORDER BY
              CASE status WHEN 'unknown' THEN 0 WHEN 'error' THEN 1 ELSE 2 END,
              CASE WHEN last_checked_at IS NULL OR last_checked_at = '' THEN 0 ELSE 1 END,
              last_checked_at ASC,
              id ASC
            LIMIT ?
            """,
            (limit * 3,),
        ).fetchall()
    items = [dict(r) for r in rows]
    # Prefer never-checked / unknown first; still return up to limit for rotation
    return items[:limit]


def _row(r: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(r) if r else None


def list_accounts(
    q: str | None = None,
    status: str | None = None,
    page: int = 1,
    per_page: int = 50,
) -> dict[str, Any]:
    page = max(1, page)
    per_page = min(max(1, per_page), 200)
    where: list[str] = []
    params: list[Any] = []
    if q:
        where.append("(email LIKE ? OR note LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like])
    if status and status != "all":
        where.append("status = ?")
        params.append(status)
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    with db_cursor() as cur:
        total = cur.execute(f"SELECT COUNT(*) FROM accounts {clause}", params).fetchone()[0]
        offset = (page - 1) * per_page
        rows = cur.execute(
            f"""
            SELECT id, email, note, status, last_checked_at, last_error, created_at, updated_at
            FROM accounts {clause}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            params + [per_page, offset],
        ).fetchall()
    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if total else 0,
    }


def get_account(account_id: int, secrets: bool = False) -> dict[str, Any] | None:
    cols = (
        "id, email, password, client_id, refresh_token, note, status, last_checked_at, last_error, created_at, updated_at"
        if secrets
        else "id, email, note, status, last_checked_at, last_error, created_at, updated_at"
    )
    with db_cursor() as cur:
        row = cur.execute(f"SELECT {cols} FROM accounts WHERE id = ?", (account_id,)).fetchone()
    return _row(row)


def get_account_by_email(email: str) -> dict[str, Any] | None:
    with db_cursor() as cur:
        row = cur.execute("SELECT * FROM accounts WHERE email = ?", (email,)).fetchone()
    return _row(row)


def get_account_by_alias(alias: str) -> dict[str, Any] | None:
    with db_cursor() as cur:
        row = cur.execute(
            """
            SELECT a.*, al.alias, al.tag
            FROM aliases al
            JOIN accounts a ON al.account_id = a.id
            WHERE al.alias = ?
            """,
            (alias,),
        ).fetchone()
    return _row(row)


def create_account(
    email: str,
    password: str,
    client_id: str,
    refresh_token: str,
    note: str = "",
) -> int:
    now = _utc_now()
    with db_cursor() as cur:
        cur.execute(
            """
            INSERT INTO accounts (email, password, client_id, refresh_token, note, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'unknown', ?, ?)
            """,
            (email, password, client_id, refresh_token, note, now, now),
        )
        return int(cur.lastrowid)


def update_account(account_id: int, **fields: Any) -> None:
    if not fields:
        return
    fields = {k: v for k, v in fields.items() if k in {
        "email", "password", "client_id", "refresh_token", "note",
        "status", "last_checked_at", "last_error",
    }}
    if not fields:
        return
    fields["updated_at"] = _utc_now()
    sets = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [account_id]
    with db_cursor() as cur:
        cur.execute(f"UPDATE accounts SET {sets} WHERE id = ?", values)


def delete_account(account_id: int) -> None:
    with db_cursor() as cur:
        cur.execute("DELETE FROM aliases WHERE account_id = ?", (account_id,))
        cur.execute("DELETE FROM accounts WHERE id = ?", (account_id,))


def delete_accounts(ids: list[int]) -> int:
    """批量删除，单事务。返回实际删除的账号数。"""
    if not ids:
        return 0
    placeholders = ",".join("?" * len(ids))
    with db_cursor() as cur:
        cur.execute(f"DELETE FROM aliases WHERE account_id IN ({placeholders})", ids)
        cur.execute(f"DELETE FROM accounts WHERE id IN ({placeholders})", ids)
        return cur.rowcount


def list_accounts_by_ids(ids: list[int], secrets: bool = False) -> list[dict[str, Any]]:
    if not ids:
        return []
    cols = (
        "id, email, password, client_id, refresh_token, note, status"
        if secrets
        else "id, email, note, status"
    )
    placeholders = ",".join("?" * len(ids))
    with db_cursor() as cur:
        rows = cur.execute(
            f"SELECT {cols} FROM accounts WHERE id IN ({placeholders}) ORDER BY id",
            ids,
        ).fetchall()
    return [dict(r) for r in rows]


def iter_accounts_for_export(
    q: str | None = None,
    status: str | None = None,
    ids: list[int] | None = None,
) -> Iterator[dict[str, Any]]:
    """导出用：按筛选条件流式产出全部账号（含明文凭据），不做分页。"""
    where: list[str] = []
    params: list[Any] = []
    if ids:
        where.append(f"id IN ({','.join('?' * len(ids))})")
        params.extend(ids)
    if q:
        where.append("(email LIKE ? OR note LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like])
    if status and status != "all":
        where.append("status = ?")
        params.append(status)
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        f"SELECT email, password, client_id, refresh_token, note, status "
        f"FROM accounts {clause} ORDER BY id",
        params,
    )
    while True:
        rows = cur.fetchmany(200)
        if not rows:
            break
        for r in rows:
            yield dict(r)


def list_aliases(account_id: int) -> list[dict[str, Any]]:
    with db_cursor() as cur:
        rows = cur.execute(
            "SELECT id, alias, tag, created_at FROM aliases WHERE account_id = ? ORDER BY id DESC",
            (account_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def create_alias(account_id: int, alias: str, tag: str) -> int:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO aliases (account_id, alias, tag, created_at) VALUES (?, ?, ?, ?)",
            (account_id, alias, tag, _utc_now()),
        )
        return int(cur.lastrowid)


def delete_alias(alias_id: int) -> None:
    with db_cursor() as cur:
        cur.execute("DELETE FROM aliases WHERE id = ?", (alias_id,))


def create_api_key(name: str, key_hash: str, prefix: str) -> int:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO api_keys (name, key_hash, prefix, created_at) VALUES (?, ?, ?, ?)",
            (name, key_hash, prefix, _utc_now()),
        )
        return int(cur.lastrowid)


def list_api_keys() -> list[dict[str, Any]]:
    """不返回 key_hash —— 界面不需要，也没必要多一处泄露面。"""
    with db_cursor() as cur:
        rows = cur.execute(
            """
            SELECT id, name, prefix, enabled, calls, last_used_at, last_target, created_at
            FROM api_keys ORDER BY id DESC
            """
        ).fetchall()
    return [dict(r) for r in rows]


def get_api_key_by_hash(key_hash: str) -> dict[str, Any] | None:
    with db_cursor() as cur:
        row = cur.execute(
            "SELECT id, name, key_hash, enabled FROM api_keys WHERE key_hash = ?",
            (key_hash,),
        ).fetchone()
    return _row(row)


def get_api_key(key_id: int) -> dict[str, Any] | None:
    with db_cursor() as cur:
        row = cur.execute(
            "SELECT id, name, prefix, enabled FROM api_keys WHERE id = ?", (key_id,)
        ).fetchone()
    return _row(row)


def set_api_key_enabled(key_id: int, enabled: bool) -> None:
    with db_cursor() as cur:
        cur.execute("UPDATE api_keys SET enabled = ? WHERE id = ?", (1 if enabled else 0, key_id))


def delete_api_key(key_id: int) -> None:
    with db_cursor() as cur:
        cur.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))


def touch_api_key(key_id: int, target: str = "") -> None:
    """
    记调用量。刻意不写 ops_log —— 脚本轮询会把那张表撑爆，
    调用信息只留在这一行上。
    """
    with db_cursor() as cur:
        cur.execute(
            "UPDATE api_keys SET calls = calls + 1, last_used_at = ?, last_target = ? WHERE id = ?",
            (_utc_now(), target[:120], key_id),
        )


def add_ops_log(action: str, target: str = "", detail: str = "") -> None:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO ops_log (action, target, detail, created_at) VALUES (?, ?, ?, ?)",
            (action, target, detail, _utc_now()),
        )


def list_ops_log(page: int = 1, per_page: int = 50, action: str | None = None) -> dict[str, Any]:
    page = max(1, page)
    per_page = min(max(1, per_page), 200)
    clause = ""
    params: list[Any] = []
    if action and action != "all":
        clause = "WHERE action = ?"
        params.append(action)
    with db_cursor() as cur:
        total = cur.execute(f"SELECT COUNT(*) FROM ops_log {clause}", params).fetchone()[0]
        offset = (page - 1) * per_page
        rows = cur.execute(
            f"""
            SELECT id, action, target, detail, created_at
            FROM ops_log {clause} ORDER BY id DESC LIMIT ? OFFSET ?
            """,
            params + [per_page, offset],
        ).fetchall()
        # 供前端下拉使用；ops_log 的 action 取值有限，DISTINCT 成本可忽略
        actions = [r[0] for r in cur.execute(
            "SELECT DISTINCT action FROM ops_log ORDER BY action"
        ).fetchall()]
    return {
        "items": [dict(r) for r in rows],
        "actions": actions,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if total else 0,
    }


def account_stats() -> dict[str, int]:
    with db_cursor() as cur:
        total = cur.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        ok = cur.execute("SELECT COUNT(*) FROM accounts WHERE status = 'ok'").fetchone()[0]
        err = cur.execute("SELECT COUNT(*) FROM accounts WHERE status = 'error'").fetchone()[0]
        unknown = cur.execute("SELECT COUNT(*) FROM accounts WHERE status = 'unknown'").fetchone()[0]
        aliases = cur.execute("SELECT COUNT(*) FROM aliases").fetchone()[0]
    return {"total": total, "ok": ok, "error": err, "unknown": unknown, "aliases": aliases}
