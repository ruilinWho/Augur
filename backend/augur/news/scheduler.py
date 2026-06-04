"""每日新闻任务（APScheduler）：抓取信源 + （若 LLM 就绪）生成趋势日报。

后台线程调度（BackgroundScheduler）——任务是阻塞 I/O，跑在独立线程不挡事件循环。
失败只记日志、绝不让 app 启动/运行崩掉。时区取 settings.tz。
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from ..config import get_settings
from ..llm import gateway
from . import service

log = logging.getLogger("augur.news")
_scheduler: BackgroundScheduler | None = None


def _daily_job() -> None:
    try:
        res = service.refresh()
        log.info("news ingest: %s", res)
    except Exception:  # noqa: BLE001
        log.exception("news ingest failed")
    try:
        dres = service.refresh_directed()  # 自选股定向抓取（按 ticker 直取，喂个股叙事）
        log.info("directed fetch: %s", dres)
    except Exception:  # noqa: BLE001
        log.exception("directed fetch failed")
    # 仅当 summarize 角色就绪时才生成日报（未配置 LLM → 静默跳过，不报错）
    try:
        gateway.check_ready("summarize")
    except gateway.LLMNotConfigured:
        return
    try:
        for _ in service.generate_report_stream():  # 消费流以触发落库
            pass
        log.info("news daily report generated")
    except Exception:  # noqa: BLE001
        log.exception("news report generation failed")
    try:
        service.generate_clusters(days=1)  # 今日要点 → 总览「晨读 Top3」早晨即就绪
        log.info("news daily clusters generated")
    except Exception:  # noqa: BLE001
        log.exception("news clusters generation failed")
    try:
        service.generate_opportunities()  # 今日机会 → 「资讯·总结」早晨即就绪（与日报/要点一致）
        log.info("news daily opportunities generated")
    except Exception:  # noqa: BLE001
        log.exception("news opportunities generation failed")


def start() -> None:
    """启动每日任务（幂等）。app lifespan 调用，失败不阻断启动。"""
    global _scheduler
    if _scheduler is not None:
        return
    try:
        tz = get_settings().tz
        sched = BackgroundScheduler(timezone=tz)
        # 每天本地 07:30：晨间抓取 +（若已配置）生成日报/要点/机会 → 晨读即就绪
        sched.add_job(
            _daily_job,
            CronTrigger(hour=7, minute=30, timezone=tz),
            id="news_daily",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        # 每天本地 23:30：**当天归档**——哪天主人没手动点「生成」，也把当天全量新闻蒸馏存档
        # （日报/要点/机会，ON CONFLICT 覆盖），这样久未打开回来翻每一天都有快照。job 幂等。
        sched.add_job(
            _daily_job,
            CronTrigger(hour=23, minute=30, timezone=tz),
            id="news_archive",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        sched.start()
        _scheduler = sched
        log.info("news scheduler started (daily 07:30 + archive 23:30 %s)", tz)
    except Exception:  # noqa: BLE001
        log.exception("news scheduler failed to start")


def stop() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
