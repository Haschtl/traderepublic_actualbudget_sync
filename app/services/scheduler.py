import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.config import settings
from app.mapping.mapper import map_pytr_to_actual
from app.services.actual import push_transactions
from app.services.trade_republic import fetch_all_transactions, fetch_transactions

log = logging.getLogger(__name__)

_sync_lock = asyncio.Lock()


@dataclass(frozen=True)
class CronSchedule:
    minutes: set[int]
    hours: set[int]
    days: set[int]
    months: set[int]
    weekdays: set[int]

    def matches(self, dt: datetime) -> bool:
        # Python: Monday=0. Cron: Sunday=0 or 7.
        cron_weekday = (dt.weekday() + 1) % 7
        return (
            dt.minute in self.minutes
            and dt.hour in self.hours
            and dt.day in self.days
            and dt.month in self.months
            and cron_weekday in self.weekdays
        )

    def next_after(self, dt: datetime) -> datetime:
        candidate = (dt + timedelta(minutes=1)).replace(second=0, microsecond=0)
        end = candidate + timedelta(days=366)
        while candidate <= end:
            if self.matches(candidate):
                return candidate
            candidate += timedelta(minutes=1)
        raise ValueError("No matching cron time found in the next year")


def _parse_cron_field(value: str, minimum: int, maximum: int, *, allow_7_as_0: bool = False) -> set[int]:
    values: set[int] = set()

    for part in value.split(","):
        part = part.strip()
        if not part:
            raise ValueError("empty cron field part")

        if "/" in part:
            base, step_text = part.split("/", 1)
            step = int(step_text)
            if step <= 0:
                raise ValueError("cron step must be greater than zero")
        else:
            base = part
            step = 1

        if base == "*":
            start, end = minimum, maximum
        elif "-" in base:
            start_text, end_text = base.split("-", 1)
            start, end = int(start_text), int(end_text)
        else:
            start = end = int(base)

        if start > end:
            raise ValueError("cron ranges must be ascending")
        if start < minimum or end > maximum:
            raise ValueError(f"cron value {start}-{end} outside {minimum}-{maximum}")

        for field_value in range(start, end + 1, step):
            values.add(0 if allow_7_as_0 and field_value == 7 else field_value)

    return values


def parse_cron(expr: str) -> CronSchedule:
    fields = expr.split()
    if len(fields) != 5:
        raise ValueError("SYNC_CRON must have 5 fields: minute hour day month weekday")

    return CronSchedule(
        minutes=_parse_cron_field(fields[0], 0, 59),
        hours=_parse_cron_field(fields[1], 0, 23),
        days=_parse_cron_field(fields[2], 1, 31),
        months=_parse_cron_field(fields[3], 1, 12),
        weekdays=_parse_cron_field(fields[4], 0, 7, allow_7_as_0=True),
    )


async def run_scheduled_sync() -> dict:
    return await _run_sync(fetch_transactions)


async def run_history_sync(session_id: str | None = None) -> dict:
    return await _run_sync(lambda: fetch_all_transactions(session_id))


async def _run_sync(fetcher) -> dict:
    if _sync_lock.locked():
        log.warning("Scheduled sync skipped because another sync is still running")
        return {"status": "skipped", "reason": "sync already running"}

    async with _sync_lock:
        txs = await asyncio.to_thread(fetcher)
        mapped = map_pytr_to_actual(txs)
        pushed = await asyncio.to_thread(push_transactions, mapped)
        result = {"mapped_count": len(mapped), "pushed": pushed}
        log.info("Sync completed: %s", result)
        return result


async def scheduler_loop(cron_expr: str | None = None) -> None:
    cron_expr = settings.sync_cron if cron_expr is None else cron_expr
    cron_expr = (cron_expr or "").strip()
    if not cron_expr:
        log.info("Scheduled sync disabled because SYNC_CRON is empty")
        return

    schedule = parse_cron(cron_expr)
    log.info("Scheduled sync enabled with SYNC_CRON=%s", cron_expr)

    while True:
        now = datetime.now()
        next_run = schedule.next_after(now)
        delay = max(0.0, (next_run - now).total_seconds())
        log.info("Next scheduled sync at %s", next_run.isoformat(timespec="seconds"))
        await asyncio.sleep(delay)
        try:
            await run_scheduled_sync()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Scheduled sync failed")


def start_scheduler() -> asyncio.Task | None:
    if not (settings.sync_cron or "").strip():
        log.info("Scheduled sync disabled because SYNC_CRON is empty")
        return None
    return asyncio.create_task(scheduler_loop())


async def stop_scheduler(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
