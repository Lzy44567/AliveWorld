"""Bounded provider retries, before a response stream is handed to its consumer."""
import asyncio
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx
from openai import APIConnectionError, APIStatusError
from core.generation_control import check_generation, clear_retry, report_retry


def retry_delay(error, ordinal):
    # Read/write failures can have consumed a paid request; do not guess success.
    if isinstance(error, APIConnectionError):
        return 2 ** (ordinal - 1) if isinstance(error.__cause__, (httpx.ConnectError, httpx.ConnectTimeout)) else None
    if not isinstance(error, APIStatusError) or error.status_code not in {429, 502, 503, 504}:
        return None
    body = error.body if isinstance(error.body, dict) else {}
    detail = body.get('error', body)
    code = str(detail.get('code', '') if isinstance(detail, dict) else '').lower()
    if any(word in code for word in ('quota', 'balance', 'billing', 'credit')):
        return None
    header = error.response.headers.get('retry-after')
    if header:
        try:
            delay = max(0, float(header))
        except ValueError:
            try:
                delay = max(0, (parsedate_to_datetime(header) - datetime.now(timezone.utc)).total_seconds())
            except (ValueError, TypeError, OverflowError):
                return None
        return delay if delay <= 60 else None
    return min(8, 2 ** (ordinal - 1))


def wait_retry(seconds):
    deadline = time.monotonic() + seconds
    while True:
        check_generation()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(0.1, remaining))


def request_with_retry(call, retries=0, *, notify=report_retry, wait=wait_retry):
    clear_retry()
    for attempt in range(retries + 1):
        check_generation()
        try:
            return call()
        except Exception as error:
            delay = retry_delay(error, attempt + 1) if attempt < retries else None
            if delay is None:
                raise
            notify(attempt + 1, retries, delay)
            wait(delay)


async def request_with_retry_async(call, retries=0, *, notify=report_retry, wait=asyncio.sleep):
    clear_retry()
    for attempt in range(retries + 1):
        try:
            return await call()
        except Exception as error:
            delay = retry_delay(error, attempt + 1) if attempt < retries else None
            if delay is None:
                raise
            notify(attempt + 1, retries, delay)
            await wait(delay)  # Task cancellation also interrupts the backoff.
