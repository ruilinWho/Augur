"""news 域共享出站 HTTP（AGENTS.md §5：统一 UA + 超时 + 轻量重试/退避）。

免费源偶发 5xx/超时/限流——给一次廉价重试（仅网络异常 / 429 / 5xx），指数退避。控制在
1 次重试以免放大对免费源的压力（§11 尊重限流）。各适配器把裸 httpx.get 换成这里，UA 单一真相。
（注：SEC EDGAR 另用自己的 UA + ≤10 req/s 节流，不走这里。）
"""

from __future__ import annotations

import time

import httpx

UA = "Mozilla/5.0 (Augur/0.1; local research tool)"
_RETRY_STATUS = {429, 502, 503, 504}


def get(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: float = 12.0,
    retries: int = 1,
    follow_redirects: bool = True,
) -> httpx.Response:
    """GET + raise_for_status；对网络异常 / 429 / 5xx 最多重试 `retries` 次（退避 0.5/1.0s）。"""
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    for attempt in range(retries + 1):
        try:
            with httpx.Client(timeout=timeout, headers=h, follow_redirects=follow_redirects) as c:
                resp = c.get(url, params=params)
            if resp.status_code in _RETRY_STATUS and attempt < retries:
                time.sleep(0.5 * (2**attempt))
                continue
            resp.raise_for_status()
            return resp
        except (httpx.TransportError, httpx.TimeoutException):
            if attempt < retries:
                time.sleep(0.5 * (2**attempt))
                continue
            raise
    raise RuntimeError("unreachable")  # 循环必然 return/raise；满足类型检查
