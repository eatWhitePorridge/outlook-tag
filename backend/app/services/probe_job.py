"""Shared probe helpers used by API and background scheduler."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

from app import db
from app.services import mail as mail_service


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _maybe_refresh(account_id: int, account: dict, new_refresh: str | None) -> None:
    if new_refresh and new_refresh != account.get("refresh_token"):
        db.update_account(account_id, refresh_token=new_refresh)


def probe_one_account(account_id: int) -> dict[str, Any]:
    full = db.get_account(account_id, secrets=True)
    if not full:
        return {"id": account_id, "ok": False, "error": "账号不存在"}
    r = mail_service.probe_account(full)
    now = _utc_now()
    if r["ok"]:
        db.update_account(account_id, status="ok", last_checked_at=now, last_error="")
    else:
        db.update_account(
            account_id,
            status="error",
            last_checked_at=now,
            last_error=(r.get("error") or "")[:500],
        )
    _maybe_refresh(account_id, full, r.get("refresh_token"))
    return {
        "id": account_id,
        "email": full["email"],
        "ok": r["ok"],
        "error": r.get("error", ""),
    }


def run_probe_batch(
    limit: int = 40,
    workers: int = 6,
    only_unknown: bool = False,
    source: str = "manual",
    ids: list[int] | None = None,
) -> dict[str, Any]:
    limit = min(max(1, limit), 200)
    workers = min(max(1, workers), 16)

    if ids:
        items = db.list_accounts_by_ids(ids)
    elif only_unknown:
        items = db.list_accounts(status="unknown", page=1, per_page=limit)["items"]
    else:
        cfg = db.get_settings_map(["probe_stale_hours"])
        stale_hours = int(cfg.get("probe_stale_hours") or 24)
        items = db.list_accounts_for_probe(limit=limit, stale_hours=stale_hours)

    if not items:
        return {"probed": 0, "ok": 0, "error": 0, "results": [], "source": source}

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(workers, len(items))) as pool:
        futures = [pool.submit(probe_one_account, it["id"]) for it in items]
        for f in as_completed(futures):
            try:
                row = f.result()
                if row:
                    results.append(row)
            except Exception as e:
                results.append({"ok": False, "error": str(e)})

    ok_n = sum(1 for r in results if r.get("ok"))
    err_n = len(results) - ok_n
    db.add_ops_log(
        "probe_batch",
        f"{len(results)}",
        f"source={source} ok={ok_n} error={err_n}",
    )
    return {
        "probed": len(results),
        "ok": ok_n,
        "error": err_n,
        "results": results,
        "source": source,
    }
