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
    if local_start.date() == local_end.date():
        return f"el {_fmt_date(local_start)}, de {local_start:%H:%M} a {local_end:%H:%M}"
    return f"del {_fmt_date(local_start)} a las {local_start:%H:%M} al {_fmt_date(local_end)} a las {local_end:%H:%M}"


def _fmt_date(local: datetime) -> str:
    """"14 de septiembre de 2026" -- the app's long date format."""
    return f"{local.day} de {_MONTHS[local.month]} de {local.year}"


def _fmt_datetime(when: datetime) -> str:
    local = when.astimezone(BUENOS_AIRES)
    return f"{_fmt_date(local)} a las {local:%H:%M}"


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


def settlement_paid(net_amount: int, booking_count: int) -> PushMessage:
    """Sent to the owner when an admin confirms a settlement's bank transfer,
    which pays out one or more bookings' pending balances in a single transfer."""
    reservas = "reserva" if booking_count == 1 else "reservas"
    return PushMessage(
        title="💸 ¡Tu pago fue depositado!",
        body=f"Depositamos {_fmt_currency(net_amount)} correspondientes a {booking_count} {reservas}.",
    )


def booking_cancelled_by_owner_account_for_driver(spot_title: str, start: datetime, end: datetime) -> PushMessage:
    """The owner's account was closed or suspended: the driver's booking was cancelled and
    fully refunded."""
    return PushMessage(
        title="Tu reserva fue cancelada",
        body=(
            f"Tu reserva en {spot_title} para {_fmt_range(start, end)} se canceló porque la "
            "cochera dejó de estar disponible. Te devolvemos el total."
        ),
    )


def booking_cancelled_by_driver_account_for_owner(spot_title: str, start: datetime, end: datetime) -> PushMessage:
    """The driver's account was closed or suspended: their booking on the owner's spot is off."""
    return PushMessage(
        title="Se canceló una reserva",
        body=f"La reserva en {spot_title} para {_fmt_range(start, end)} se canceló: el conductor ya no está en ParkLink.",
    )


def booking_rejected_for_driver(spot_title: str, start: datetime, end: datetime) -> PushMessage:
    """The owner rejected the driver's booking request; the payment is refunded."""
    return PushMessage(
        title="Tu reserva fue rechazada",
        body=(
            f"El propietario de {spot_title} no pudo aceptar tu reserva para {_fmt_range(start, end)}. "
            "Te devolvemos el total."
        ),
    )


def booking_request_expired_for_driver(spot_title: str, start: datetime, end: datetime) -> PushMessage:
    """The owner never answered the driver's booking request in time; it was refunded."""
    return PushMessage(
        title="Tu reserva no fue confirmada",
        body=(
            f"El propietario de {spot_title} no respondió a tiempo tu reserva para {_fmt_range(start, end)}. "
            "Te devolvemos el total."
        ),
    )


def booking_cancelled_by_driver_for_owner(spot_title: str, start: datetime, end: datetime) -> PushMessage:
    """The driver cancelled their booking on the owner's spot -- the slot is free again."""
    return PushMessage(
        title="Se canceló una reserva",
        body=f"El conductor canceló su reserva en {spot_title} para {_fmt_range(start, end)}. El horario vuelve a estar libre.",
    )


def booking_completed_for_driver(spot_title: str) -> PushMessage:
    """The stay is over: the driver is asked to review the spot and its owner."""
    return PushMessage(
        title="⭐ ¿Cómo te fue?",
        body=f"Tu estadía en {spot_title} terminó. Calificá la cochera y al propietario.",
    )


def booking_completed_for_owner(spot_title: str) -> PushMessage:
    """The stay is over: the owner is asked to review the driver."""
    return PushMessage(
        title="⭐ Calificá al conductor",
        body=f"Terminó la reserva en {spot_title}. Contanos cómo fue el conductor.",
    )


def parking_spot_approved(spot_title: str) -> PushMessage:
    """Sent to the owner when an admin approves their new parking spot: it's published."""
    return PushMessage(
        title="✅ ¡Tu cochera fue aprobada!",
        body=f"{_spot_name(spot_title)} ya está publicada y los conductores pueden reservarla.",
    )


def parking_spot_rejected(spot_title: str, notes: str | None) -> PushMessage:
    """Sent to the owner when an admin rejects their new parking spot, with the admin's
    reason when there is one."""
    note = (notes or "").strip()
    reason = f" Motivo: {note}{'' if note.endswith(('.', '!', '?')) else '.'}" if note else ""
    return PushMessage(
        title="Tu cochera no fue aprobada",
        body=f"{_spot_name(spot_title)} no se publicó.{reason} Podés corregirla y volver a enviarla.",
    )


def _spot_name(spot_title: str) -> str:
    return f"«{spot_title}»" if spot_title else "Tu cochera"
