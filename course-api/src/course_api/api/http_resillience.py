"""HTTP resilience helper, bounded retry w/ retry after

This file could be unnecessary, edit as needed"""

import asyncio
from typing import Any
import httpx
import structlog 

log = structlog.get_logger(__name__)

async def request_with_retry(
        client: httpx.AsyncClient,
        method: str,
        url: str,
        max_retries: int = 3,
        max_backoff: float = 30.0,
        **kwargs: Any,
) -> httpx.Response:
    for attempt in range(max_retries + 1):
        is_last = attempt == max_retries
        try:
            response = await client.request(method, url, **kwargs)
        except httpx.TransportError:
            if is_last:
                raise
            wait = min(2 ** attempt, max_backoff)
            log.info("retry_transport_error", attempt=attempt, wait_s=wait)
            await asyncio.sleep(wait)
            continue

        if response.status_code != 429 or is_last:
            return response

        wait = _parse_retry_after(response.headers.get("Retry-After"))
        if wait is None:
            wait = min(2**attempt, max_backoff)
        log.info("retry_after_429", attempt=attempt, wait_s=wait)
        await asyncio.sleep(wait)

    raise AssertionError("unreachable: retry loop existed without returing or raising")

def _parse_retry_after(header: str | None) -> float | None:

    if header is None:
        return None
    try:
        return float(header)
    except ValueError:
        return None