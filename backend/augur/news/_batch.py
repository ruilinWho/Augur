"""并发批处理小工具：把待处理项切批、最多 N 个并发跑。

供 translate/relevance/stock_tag 每轮的批量 LLM 调用提速（作者：尽量并行、不担心 token）。
每批独立成败，失败的批由各自循环逻辑处理（保留待下轮/跳过毒窗）。WORKERS 兼顾速度与
§11 限流——8 个并发对 paid LLM 端点是可承受的常见量级。
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

WORKERS = 8  # 单轮最多并发多少批 LLM 调用


def map_batches(items: list, batch_size: int, fn: Callable, workers: int = WORKERS) -> list:
    """把 items 切成 batch_size 的批，最多 workers 个并发跑 fn(batch)，返回各批结果（与批同序）。

    单批时不开线程池（省开销）；fn 内的异常按 fn 自身约定处理（这里不吞、直接抛出由调用方兜）。
    """
    batches = [items[i : i + batch_size] for i in range(0, len(items), batch_size)]
    if len(batches) <= 1:
        return [fn(b) for b in batches]
    with ThreadPoolExecutor(max_workers=min(workers, len(batches))) as ex:
        return list(ex.map(fn, batches))
