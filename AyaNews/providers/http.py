"""数据源共享的 HTTP 请求工具。"""
from __future__ import annotations

import time

import requests

DEFAULT_TIMEOUT = 30
DEFAULT_RETRIES = 2


def get_with_retry(
    url: str,
    params: dict,
    *,
    label: str,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
) -> requests.Response:
    """带重试的 GET；每次失败打印提示，全部失败后抛出最后一次异常。"""
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            last_exc = exc
            print(f"[{label}] 第 {attempt} 次请求失败：{exc}，稍后重试…")
            time.sleep(2)
    raise last_exc
