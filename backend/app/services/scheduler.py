"""Background probe scheduler."""

import logging
import threading
import time
from typing import Any

from app import db
from app.services.probe_job import run_probe_batch

log = logging.getLogger("probe.scheduler")

_stop = threading.Event()
_thread: threading.Thread | None = None
_lock = threading.Lock()
_state: dict[str, Any] = {
    "running": False,
    "last_run_at": None,
    "last_result": None,
    "next_run_in_sec": None,
    "cycle": 0,
    "busy": False,
}


def get_scheduler_status() -> dict[str, Any]:
    cfg = db.get_settings_map()
    with _lock:
        st = dict(_state)
    return {
        **st,
        "enabled": cfg.get("probe_enabled") == "1",
        "interval_minutes": int(cfg.get("probe_interval_minutes") or 10),
        "batch_size": int(cfg.get("probe_batch_size") or 40),
        "workers": int(cfg.get("probe_workers") or 6),
        "stale_hours": int(cfg.get("probe_stale_hours") or 24),
        "thread_alive": bool(_thread and _thread.is_alive()),
    }


def _tick_once() -> None:
    cfg = db.get_settings_map()
    if cfg.get("probe_enabled") != "1":
        return
    limit = int(cfg.get("probe_batch_size") or 40)
    workers = int(cfg.get("probe_workers") or 6)
    with _lock:
        if _state["busy"]:
            return
        _state["busy"] = True
    try:
        result = run_probe_batch(limit=limit, workers=workers, only_unknown=False, source="scheduler")
        with _lock:
            _state["last_run_at"] = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
            _state["last_result"] = {
                "probed": result["probed"],
                "ok": result["ok"],
                "error": result["error"],
            }
            _state["cycle"] = int(_state["cycle"]) + 1
        log.info(
            "probe cycle done probed=%s ok=%s error=%s",
            result["probed"],
            result["ok"],
            result["error"],
        )
    except Exception:
        log.exception("probe cycle failed")
    finally:
        with _lock:
            _state["busy"] = False


def _loop() -> None:
    # first run shortly after boot
    if not _stop.wait(15):
        _tick_once()
    while not _stop.is_set():
        cfg = db.get_settings_map()
        minutes = max(1, int(cfg.get("probe_interval_minutes") or 10))
        wait_sec = minutes * 60
        # sleep in slices so config changes apply sooner
        slept = 0
        while slept < wait_sec and not _stop.is_set():
            with _lock:
                _state["next_run_in_sec"] = wait_sec - slept
            step = min(5, wait_sec - slept)
            if _stop.wait(step):
                break
            slept += step
            # re-read interval if shortened
            cfg2 = db.get_settings_map(["probe_interval_minutes", "probe_enabled"])
            if cfg2.get("probe_enabled") != "1":
                # idle while disabled
                while not _stop.is_set() and db.get_setting("probe_enabled") != "1":
                    with _lock:
                        _state["next_run_in_sec"] = None
                    _stop.wait(5)
                break
            new_min = max(1, int(cfg2.get("probe_interval_minutes") or 10))
            if new_min * 60 != wait_sec:
                break
        else:
            if not _stop.is_set():
                _tick_once()


def start_scheduler() -> None:
    global _thread
    with _lock:
        if _thread and _thread.is_alive():
            return
        _stop.clear()
        _state["running"] = True
        _thread = threading.Thread(target=_loop, name="probe-scheduler", daemon=True)
        _thread.start()
        log.info("probe scheduler started")


def stop_scheduler() -> None:
    global _thread
    _stop.set()
    t = _thread
    if t and t.is_alive():
        t.join(timeout=3)
    with _lock:
        _state["running"] = False
        _thread = None
    log.info("probe scheduler stopped")


def run_now() -> dict[str, Any]:
    """Trigger one cycle immediately (still respects batch settings)."""
    cfg = db.get_settings_map()
    limit = int(cfg.get("probe_batch_size") or 40)
    workers = int(cfg.get("probe_workers") or 6)
    with _lock:
        if _state["busy"]:
            return {"busy": True, "probed": 0}
        _state["busy"] = True
    try:
        result = run_probe_batch(limit=limit, workers=workers, only_unknown=False, source="manual_now")
        with _lock:
            _state["last_run_at"] = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
            _state["last_result"] = {
                "probed": result["probed"],
                "ok": result["ok"],
                "error": result["error"],
            }
            _state["cycle"] = int(_state["cycle"]) + 1
        return result
    finally:
        with _lock:
            _state["busy"] = False
