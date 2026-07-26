from fastapi import APIRouter, Depends

from app import db
from app.auth import require_admin
from app.schemas import SystemSettingsUpdate
from app.services import scheduler

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/system")
def get_system_settings(_: dict = Depends(require_admin)):
    cfg = db.get_settings_map()
    status = scheduler.get_scheduler_status()
    return {
        "probe_enabled": cfg.get("probe_enabled") == "1",
        "probe_interval_minutes": int(cfg.get("probe_interval_minutes") or 10),
        "probe_batch_size": int(cfg.get("probe_batch_size") or 40),
        "probe_workers": int(cfg.get("probe_workers") or 6),
        "probe_stale_hours": int(cfg.get("probe_stale_hours") or 24),
        "scheduler": status,
    }


@router.put("/system")
def update_system_settings(body: SystemSettingsUpdate, admin: dict = Depends(require_admin)):
    payload: dict[str, str] = {}
    if body.probe_enabled is not None:
        payload["probe_enabled"] = "1" if body.probe_enabled else "0"
    if body.probe_interval_minutes is not None:
        payload["probe_interval_minutes"] = str(max(1, min(body.probe_interval_minutes, 24 * 60)))
    if body.probe_batch_size is not None:
        payload["probe_batch_size"] = str(max(1, min(body.probe_batch_size, 200)))
    if body.probe_workers is not None:
        payload["probe_workers"] = str(max(1, min(body.probe_workers, 16)))
    if body.probe_stale_hours is not None:
        payload["probe_stale_hours"] = str(max(1, min(body.probe_stale_hours, 168)))
    if payload:
        db.set_settings(payload)
        db.add_ops_log("update_settings", "system", ",".join(payload.keys()))
    return get_system_settings(admin)


@router.post("/probe/run-now")
def probe_run_now(_: dict = Depends(require_admin)):
    result = scheduler.run_now()
    return result
