"""进程内滑动窗口限流。

单进程部署（内置调度器本就要求单实例），内存计数足够；
换成多实例时这里需要挪到 Redis。
"""

import threading
import time
from collections import deque

from fastapi import HTTPException

_buckets: dict[str, dict[str, deque]] = {}
_lock = threading.Lock()


def check(scope: str, key: str, limit: int, window: int, detail: str) -> None:
    """超限时抛 429（带 Retry-After）。scope 用于隔离不同接口的计数。"""
    now = time.time()
    with _lock:
        bucket = _buckets.setdefault(scope, {})
        q = bucket.setdefault(key, deque())
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(
                status_code=429,
                detail=detail,
                headers={"Retry-After": str(int(window - (now - q[0])) + 1)},
            )
        q.append(now)
        # 定期清掉已空闲的键，避免被大量不同来源撑爆
        if len(bucket) > 5000:
            for k, dq in list(bucket.items()):
                if not dq or now - dq[-1] > window:
                    bucket.pop(k, None)


def forget(scope: str, key: str) -> None:
    with _lock:
        _buckets.get(scope, {}).pop(key, None)


def client_ip(request) -> str:
    """反代场景取 X-Forwarded-For 的第一跳。"""
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
