import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "mail.db"))


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            password TEXT DEFAULT '',
            client_id TEXT NOT NULL,
            refresh_token TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            alias TEXT NOT NULL UNIQUE,
            tag TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()


def list_accounts():
    conn = get_db()
    rows = conn.execute("SELECT id, email, created_at FROM accounts ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_account(account_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_account_by_email(email):
    conn = get_db()
    row = conn.execute("SELECT * FROM accounts WHERE email = ?", (email,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_account(email, password, client_id, refresh_token):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO accounts (email, password, client_id, refresh_token) VALUES (?, ?, ?, ?)",
        (email, password, client_id, refresh_token),
    )
    conn.commit()
    account_id = cur.lastrowid
    conn.close()
    return account_id


def update_account(account_id, **fields):
    conn = get_db()
    sets = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [account_id]
    conn.execute(f"UPDATE accounts SET {sets} WHERE id = ?", values)
    conn.commit()
    conn.close()


def delete_account(account_id):
    conn = get_db()
    conn.execute("DELETE FROM aliases WHERE account_id = ?", (account_id,))
    conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
    conn.commit()
    conn.close()


def list_aliases(account_id):
    conn = get_db()
    rows = conn.execute("SELECT id, alias, tag, created_at FROM aliases WHERE account_id = ? ORDER BY id DESC", (account_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_alias(account_id, alias, tag):
    conn = get_db()
    cur = conn.execute("INSERT INTO aliases (account_id, alias, tag) VALUES (?, ?, ?)", (account_id, alias, tag))
    conn.commit()
    alias_id = cur.lastrowid
    conn.close()
    return alias_id


def delete_alias(alias_id):
    conn = get_db()
    conn.execute("DELETE FROM aliases WHERE id = ?", (alias_id,))
    conn.commit()
    conn.close()


def get_account_by_alias(alias):
    conn = get_db()
    row = conn.execute("SELECT a.*, al.alias, al.tag FROM aliases al JOIN accounts a ON al.account_id = a.id WHERE al.alias = ?", (alias,)).fetchone()
    conn.close()
    return dict(row) if row else None
