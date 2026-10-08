"""Tells whoever holds a live connection to the app that a user has something new in
their inbox: a `notification.created` message on the shared exchange, which the gateway
relays to that user's open app over its WebSocket. Only a hint -- the app then refetches
the inbox, which stays the source of truth -- so a lost one costs nothing but delay."""

from __future__ import annotations

import json

import aio_pika
from loguru import logger

ROUTING_KEY = "notification.created"

_exchange: aio_pika.abc.AbstractExchange | None = None


def bind(exchange: aio_pika.abc.AbstractExchange | None) -> None:
    """Set by the consumer once it's connected (None when it disconnects)."""
    global _exchange
    _exchange = exchange


async def announce(user_ids: set[str]) -> None:
    if not user_ids or _exchange is None:
        return
    message = aio_pika.Message(
        body=json.dumps({"user_ids": sorted(user_ids)}).encode("utf-8"),
        content_type="application/json",
        # Transient on purpose: a hint nobody was connected to receive is worthless later.
        delivery_mode=aio_pika.DeliveryMode.NOT_PERSISTENT,
    )
    try:
        await _exchange.publish(message, routing_key=ROUTING_KEY)
    except Exception as exc:  # noqa: BLE001 - the inbox is already saved; this is best-effort
        logger.warning(f"[live] could not announce new notifications: {exc}")
