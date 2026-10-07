from __future__ import annotations

import asyncio
import json
from typing import Awaitable, Callable

import aio_pika
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.exc import OperationalError

from app.config import settings
from app.database import SessionLocal
from app.handlers.booking_cancelled import build_booking_cancelled_pushes
from app.handlers.booking_confirmed import build_booking_confirmed_pushes
from app.handlers.booking_message_sent import build_booking_message_sent_pushes
from app.handlers.booking_pending_approval import build_booking_pending_approval_pushes
from app.handlers.booking_verified import build_booking_verified_pushes
from app.handlers.outbound import OutboundPush
from app.handlers.settlement_paid import build_settlement_paid_pushes
from app.handlers.support_ticket_replied import build_support_ticket_replied_pushes
from app.messaging.events import (
    BookingCancelledEvent,
    BookingConfirmedEvent,
    BookingMessageSentEvent,
    BookingPendingApprovalEvent,
    BookingVerifiedEvent,
    SettlementPaidEvent,
    SupportTicketRepliedEvent,
)
from app.models import ProcessedEvent
from app.services import push

# Add a routing key + an entry in HANDLERS to support another event. Nothing
# else needs to change.
BINDING_KEYS = [
    "booking.confirmed",
    "booking.pending_approval",
    "booking.verified",
    "booking.message_sent",
    "support.ticket_replied",
    "settlement.paid",
    "booking.cancelled",
]

RETRY_DELAY_SECONDS = 5


def _process_event(
    body: dict,
    event_cls: type[BaseModel],
    build_pushes: Callable[..., list[OutboundPush]],
    session_factory,
) -> None:
    """Shared pipeline: validate -> skip if already processed -> build pushes ->
    send -> record. RabbitMQ is at-least-once, so ProcessedEvent is the dedupe key."""
    event = event_cls.model_validate(body)
    db = session_factory()
    try:
        if db.get(ProcessedEvent, event.event_id) is not None:
            logger.info(f"[consumer] event {event.event_id} already processed, skipping")
            return
        pushes = build_pushes(event)
        push.send_pushes(db, pushes)
        db.add(ProcessedEvent(event_id=event.event_id, event_type=event.event_type))
        db.commit()
        logger.info(
            f"[consumer] handled {event.event_type} event={event.event_id} pushes={len(pushes)}"
        )
    finally:
        db.close()


async def _handle_booking_confirmed(body: dict, session_factory=SessionLocal) -> None:
    _process_event(body, BookingConfirmedEvent, build_booking_confirmed_pushes, session_factory)


async def _handle_booking_pending_approval(body: dict, session_factory=SessionLocal) -> None:
    _process_event(
        body, BookingPendingApprovalEvent, build_booking_pending_approval_pushes, session_factory
    )


async def _handle_booking_verified(body: dict, session_factory=SessionLocal) -> None:
    _process_event(body, BookingVerifiedEvent, build_booking_verified_pushes, session_factory)


async def _handle_booking_message_sent(body: dict, session_factory=SessionLocal) -> None:
    _process_event(
        body, BookingMessageSentEvent, build_booking_message_sent_pushes, session_factory
    )


async def _handle_support_ticket_replied(body: dict, session_factory=SessionLocal) -> None:
    _process_event(
        body, SupportTicketRepliedEvent, build_support_ticket_replied_pushes, session_factory
    )


async def _handle_settlement_paid(body: dict, session_factory=SessionLocal) -> None:
    _process_event(body, SettlementPaidEvent, build_settlement_paid_pushes, session_factory)


async def _handle_booking_cancelled(body: dict, session_factory=SessionLocal) -> None:
    _process_event(body, BookingCancelledEvent, build_booking_cancelled_pushes, session_factory)


HANDLERS: dict[str, Callable[[dict], Awaitable[None]]] = {
    "booking.confirmed": _handle_booking_confirmed,
    "booking.pending_approval": _handle_booking_pending_approval,
    "booking.verified": _handle_booking_verified,
    "booking.message_sent": _handle_booking_message_sent,
    "support.ticket_replied": _handle_support_ticket_replied,
    "settlement.paid": _handle_settlement_paid,
    "booking.cancelled": _handle_booking_cancelled,
}

# Failures that mean "try again later" rather than "this message is broken".
TRANSIENT_ERRORS = (ConnectionError, TimeoutError, OperationalError)


class Consumer:
    """Consumes domain events from the shared `parklink.events` topic exchange
    on notifications-service's own durable queue, and dispatches them to
    HANDLERS. Manual ack: a transient failure re-queues the message."""

    def __init__(self) -> None:
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._stopping = False

    async def run(self) -> None:
        while not self._stopping:
            try:
                await self._consume()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - broker down must not kill the process
                logger.warning(
                    f"[consumer] connection problem ({exc}); retrying in {RETRY_DELAY_SECONDS}s"
                )
                await asyncio.sleep(RETRY_DELAY_SECONDS)

    async def _consume(self) -> None:
        self._connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        async with self._connection:
            channel = await self._connection.channel()
            await channel.set_qos(prefetch_count=10)
            exchange = await channel.declare_exchange(
                settings.EVENTS_EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True
            )
            queue = await channel.declare_queue(settings.NOTIFICATIONS_QUEUE, durable=True)
            for key in BINDING_KEYS:
                await queue.bind(exchange, routing_key=key)
            logger.info(
                f"[consumer] queue '{settings.NOTIFICATIONS_QUEUE}' bound to {BINDING_KEYS}"
            )
            await queue.consume(self._on_message)
            await asyncio.Future()  # block until the task is cancelled

    async def _on_message(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        async with message.process(requeue=True, ignore_processed=True):
            routing_key = message.routing_key or ""
            handler = HANDLERS.get(routing_key)
            if handler is None:
                logger.warning(f"[consumer] no handler for '{routing_key}', dropping")
                return

            try:
                body = json.loads(message.body.decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as exc:
                logger.warning(f"[consumer] bad payload on '{routing_key}': {exc}; dropping")
                return

            try:
                await handler(body)
            except TRANSIENT_ERRORS as exc:
                logger.warning(
                    f"[consumer] transient failure on '{routing_key}': {exc}; requeueing"
                )
                raise  # message.process re-raises -> nack(requeue=True)
            except Exception as exc:  # noqa: BLE001 - malformed/unhandleable -> drop, don't loop
                logger.exception(f"[consumer] unrecoverable error on '{routing_key}': {exc}")
                return

    async def stop(self) -> None:
        self._stopping = True
        if self._connection is not None and not self._connection.is_closed:
            await self._connection.close()
