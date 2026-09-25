from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

# The whole platform assumes Buenos Aires local time (no DST) -- same as
# parking-service/src/availability/buenos-aires-time.ts and booking-service's
# BuenosAiresTimezone constant.
BUENOS_AIRES = ZoneInfo("America/Argentina/Buenos_Aires")

# Used when booking-service could not resolve the spot's human title.
DEFAULT_TITLE = "tu cochera"

_MONTHS = [
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
    "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


@dataclass(frozen=True)
class PushMessage:
    title: str
    body: str


def _fmt_range(start: datetime, end: datetime) -> str:
    local_start = start.astimezone(BUENOS_AIRES)
    local_end = end.astimezone(BUENOS_AIRES)
    fecha = f"{local_start.day} de {_MONTHS[local_start.month]}"
    return f"el {fecha} de {local_start:%H:%M} a {local_end:%H:%M}"


def _fmt_datetime(when: datetime) -> str:
    local = when.astimezone(BUENOS_AIRES)
    return f"{local.day} de {_MONTHS[local.month]} a las {local:%H:%M}"


def _fmt_currency(cents: int) -> str:
    """Formats an amount in centavos as Argentine pesos, e.g. 12345 -> "$123,45"."""
    pesos, centavos = divmod(cents, 100)
    thousands = f"{pesos:,}".replace(",", ".")
    return f"${thousands},{centavos:02d}"


def booking_confirmed_for_driver(spot_title: str, start: datetime, end: datetime) -> PushMessage:
    return PushMessage(
        title="✅ ¡Reserva confirmada!",
        body=f"Tu lugar en {spot_title} para {_fmt_range(start, end)} ya está confirmado. ¡Buen viaje! 🚗",
    )


def booking_verified_for_driver(spot_title: str) -> PushMessage:
    """Sent to the driver once the owner enters their in-person verification code."""
    return PushMessage(
        title="🎉 Tu llegada fue confirmada",
        body=f"El propietario de {spot_title} confirmó tu código. ¡Que disfrutes tu estadía!",
    )


_MESSAGE_PREVIEW_MAX_LEN = 120


def booking_message_received(spot_title: str, body: str) -> PushMessage:
    """Sent to whichever side of a booking (driver or owner) did NOT just send the
    message -- a short preview, same idea as any chat app's push notification."""
    preview = body if len(body) <= _MESSAGE_PREVIEW_MAX_LEN else body[:_MESSAGE_PREVIEW_MAX_LEN - 1] + "…"
    return PushMessage(
        title=f"💬 Nuevo mensaje sobre {spot_title}",
        body=preview,
    )


def support_ticket_replied(subject: str, body: str) -> PushMessage:
    """Sent to a ticket's creator when ParkLink staff reply from admin-dashboard."""
    preview = body if len(body) <= _MESSAGE_PREVIEW_MAX_LEN else body[:_MESSAGE_PREVIEW_MAX_LEN - 1] + "…"
    title = f"🎧 Soporte respondió: {subject}" if subject else "🎧 Soporte respondió tu ticket"
    return PushMessage(title=title, body=preview)


def booking_pending_approval_for_owner(
    spot_title: str, start: datetime, end: datetime, deadline: datetime | None
) -> PushMessage:
    """Sent to the owner right after the driver pays: they must accept or reject."""
    body = (
        f"Alguien reservó y pagó {spot_title} para {_fmt_range(start, end)}. "
        "Aceptá o rechazá la reserva desde la app"
    )
    if deadline is not None:
        body += f" antes del {_fmt_datetime(deadline)}"
    return PushMessage(title="🔔 Tenés una reserva para confirmar", body=body + ".")


def payout_paid(spot_title: str, net_amount: int) -> PushMessage:
    """Sent to the owner when ParkLink staff mark their payout as transferred."""
    title = spot_title or DEFAULT_TITLE
    return PushMessage(
        title="💸 ¡Tu pago fue depositado!",
        body=f"Depositamos {_fmt_currency(net_amount)} por {title} en tu cuenta.",
    )
