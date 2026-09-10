from __future__ import annotations

from dataclasses import dataclass

import httpx
from loguru import logger

from app.config import settings

DEFAULT_TITLE = "tu cochera"


class RecipientResolutionError(Exception):
    """Transient failure resolving a spot (parking-service unreachable or 5xx).
    The consumer re-queues the message so the owner still gets notified once
    parking-service is back."""


@dataclass(frozen=True)
class SpotInfo:
    owner_id: str | None
    title: str


async def resolve_spot(parking_spot_id: str) -> SpotInfo:
    """Looks up the spot's owner id and human title from parking-service's
    public `GET /parking-spots/{id}` route. A 404 (spot paused/deleted after
    the booking) yields a fallback so the driver notification still goes out;
    any other failure raises RecipientResolutionError to trigger a retry."""
    url = f"{settings.PARKING_SERVICE_URL}/parking-spots/{parking_spot_id}"
    try:
        async with httpx.AsyncClient(timeout=settings.UPSTREAM_TIMEOUT_SECONDS) as client:
            resp = await client.get(url)
    except httpx.HTTPError as exc:
        raise RecipientResolutionError(f"parking-service unreachable: {exc}") from exc

    if resp.status_code == 200:
        data = resp.json()
        return SpotInfo(owner_id=data.get("ownerId"), title=data.get("title") or DEFAULT_TITLE)

    if resp.status_code == 404:
        logger.warning(f"[recipients] spot {parking_spot_id} not found; using fallback title")
        return SpotInfo(owner_id=None, title=DEFAULT_TITLE)

    raise RecipientResolutionError(f"parking-service returned {resp.status_code}")
