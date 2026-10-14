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
    # A multi-day stay: both dates with their times, compact so it reads in one line.
    return f"del {local_start:%d/%m/%Y %H:%M} al {local_end:%d/%m/%Y %H:%M}"


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


def _fmt_time(when: datetime) -> str:
    return f"{when.astimezone(BUENOS_AIRES):%H:%M}"


def payment_received_for_driver(spot_title: str, start: datetime, end: datetime) -> PushMessage:
    """The driver paid: the booking now waits for the owner to accept it."""
    return PushMessage(
        title="💳 Recibimos tu pago",
        body=(
            f"Tu reserva en {spot_title} para {_fmt_range(start, end)} está esperando que el "
            "propietario la acepte. Te avisamos apenas responda."
        ),
    )


def booking_request_expired_for_owner(spot_title: str, start: datetime, end: datetime) -> PushMessage:
    """The owner never answered a booking request in time: it was cancelled and refunded."""
    return PushMessage(
        title="Se venció una solicitud de reserva",
        body=(
            f"No respondiste a tiempo la reserva en {spot_title} para {_fmt_range(start, end)}. "
            "Se canceló y le devolvimos el pago al conductor."
        ),
    )


def booking_request_reminder_for_owner(spot_title: str, deadline: datetime | None) -> PushMessage:
    """A booking request is about to expire unanswered."""
    until = f" antes de las {_fmt_time(deadline)}" if deadline is not None else ""
    return PushMessage(
        title="⏰ Una reserva espera tu respuesta",
        body=f"Aceptá o rechazá la reserva en {spot_title}{until}, o se cancela sola.",
    )


def payout_approved_for_owner(spot_title: str) -> PushMessage:
    """An admin approved a booking that ended without its arrival code verified."""
    return PushMessage(
        title="✅ Liberamos tu pago",
        body=f"Revisamos la reserva en {spot_title} que terminó sin el código de llegada: la vas a cobrar en tu próxima liquidación.",
    )


def payout_denied_for_owner(spot_title: str) -> PushMessage:
    """An admin refunded the driver of a booking that ended without its arrival code verified."""
    return PushMessage(
        title="No vas a cobrar una reserva",
        body=(
            f"La reserva en {spot_title} terminó sin que cargaras el código de llegada y le devolvimos "
            "el pago al conductor. Cargá siempre el código cuando llega el conductor."
        ),
    )


def unverified_refunded_for_driver(spot_title: str) -> PushMessage:
    """An admin refunded the driver of a booking that ended without its arrival verified."""
    return PushMessage(
        title="💸 Te devolvimos el pago",
        body=f"Revisamos tu reserva en {spot_title}: no se confirmó tu llegada, así que te devolvemos el total.",
    )


def booking_starting_soon_for_driver(spot_title: str, start: datetime) -> PushMessage:
    return PushMessage(
        title="🚗 Tu reserva empieza pronto",
        body=f"Tu lugar en {spot_title} te espera a las {_fmt_time(start)}. Tené a mano tu código de llegada.",
    )


def booking_starting_soon_for_owner(spot_title: str, start: datetime) -> PushMessage:
    return PushMessage(
        title="🚗 Llega un conductor",
        body=f"Una reserva en {spot_title} empieza a las {_fmt_time(start)}. Pedile el código de llegada.",
    )


def stay_ending_for_driver(spot_title: str, end: datetime) -> PushMessage:
    return PushMessage(
        title="⏳ Tu estadía está por terminar",
        body=f"Tu estadía en {spot_title} termina a las {_fmt_time(end)}. Acordate de retirar tu vehículo.",
    )


def review_received(spot_title: str, rating: int, recipient_role: str) -> PushMessage:
    stars = "★" * max(0, min(rating, 5))
    who = "el conductor" if recipient_role == "owner" else "el propietario"
    where = f" por la reserva en {spot_title}" if spot_title else ""
    return PushMessage(title="⭐ Te dejaron una reseña", body=f"{stars} — {who} te calificó{where}.")


def support_ticket_closed(subject: str) -> PushMessage:
    about = f" «{subject}»" if subject else ""
    return PushMessage(
        title="Cerramos tu consulta",
        body=f"Dimos por resuelta tu consulta{about}. Si necesitás algo más, podés escribirnos de nuevo.",
    )


def refund_completed(amount: int, method: str) -> PushMessage:
    how = "por otro medio" if method == "manual" else "por Mercado Pago"
    return PushMessage(
        title="💸 Se acreditó tu reembolso",
        body=f"Te devolvimos {_fmt_currency(amount)} {how}. Perdón por la demora.",
    )


def settlement_drafted(net_amount: int, booking_count: int) -> PushMessage:
    """Sent to the owner when an admin prepares their settlement, before the transfer."""
    reservas = "reserva" if booking_count == 1 else "reservas"
    return PushMessage(
        title="🧾 Estamos preparando tu liquidación",
        body=(
            f"Preparamos tu liquidación de {_fmt_currency(net_amount)} por {booking_count} {reservas}. "
            "Te avisamos cuando hagamos la transferencia."
        ),
    )


def parking_spot_suspended(spot_title: str, notes: str | None) -> PushMessage:
    """ParkLink suspended a published spot (a report, a problem): it's hidden until restored."""
    note = (notes or "").strip()
    reason = f" Motivo: {note}{'' if note.endswith(('.', '!', '?')) else '.'}" if note else ""
    return PushMessage(
        title="ParkLink suspendió tu cochera",
        body=f"{_spot_name(spot_title)} dejó de mostrarse y no recibe reservas nuevas.{reason} Escribinos desde Ayuda si querés revisarlo.",
    )


def parking_spot_restored(spot_title: str) -> PushMessage:
    """ParkLink restored a spot it had suspended."""
    return PushMessage(
        title="✅ Tu cochera volvió a estar publicada",
        body=f"{_spot_name(spot_title)} ya se muestra de nuevo y puede recibir reservas.",
    )


def _refund_text(refunded_centavos: int) -> str:
    pesos = refunded_centavos / 100
    return f"${pesos:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def booking_admin_cancelled_for_driver(spot_title: str, start: datetime, end: datetime, refunded: int) -> PushMessage:
    refund = f" Te devolvemos {_refund_text(refunded)} al mismo medio de pago." if refunded > 0 else ""
    return PushMessage(
        title="ParkLink canceló tu reserva",
        body=f"Cancelamos tu reserva en {spot_title} para {_fmt_range(start, end)}.{refund}",
    )


def booking_admin_cancelled_for_owner(spot_title: str, start: datetime, end: datetime) -> PushMessage:
    return PushMessage(
        title="ParkLink canceló una reserva",
        body=f"Cancelamos la reserva en {spot_title} para {_fmt_range(start, end)}. El horario vuelve a estar libre.",
    )


def booking_admin_refunded_for_driver(spot_title: str, refunded: int) -> PushMessage:
    return PushMessage(
        title="Te devolvimos dinero de una reserva",
        body=f"Te devolvemos {_refund_text(refunded)} de tu reserva en {spot_title}, al mismo medio de pago.",
    )


def booking_admin_refunded_for_owner(spot_title: str, refunded: int) -> PushMessage:
    return PushMessage(
        title="Se reembolsó parte de una reserva",
        body=f"ParkLink le devolvió {_refund_text(refunded)} al conductor de una reserva en {spot_title}. Tu cobro por esa reserva se ajusta en la misma proporción.",
    )


def booking_cancelled_by_owner_for_driver(spot_title: str, start: datetime, end: datetime, note: str) -> PushMessage:
    """The owner called off a booking they had accepted: the driver gets everything back."""
    reason = f" Motivo: {note}" if note else ""
    return PushMessage(
        title="El propietario canceló tu reserva",
        body=f"Se canceló tu reserva en {spot_title} para {_fmt_range(start, end)}. Te devolvemos el total.{reason}",
    )


def booking_late_cancelled_for_owner(spot_title: str, start: datetime, end: datetime) -> PushMessage:
    """The driver cancelled in the booking's last hour: the owner still gets part of it."""
    return PushMessage(
        title="Se canceló una reserva",
        body=(
            f"El conductor canceló su reserva en {spot_title} para {_fmt_range(start, end)} con menos de una hora "
            "de anticipación. Igual cobrás la mitad."
        ),
    )


def booking_extended_for_driver(spot_title: str, end: datetime) -> PushMessage:
    return PushMessage(
        title="✅ Extendiste tu reserva",
        body=f"Tu lugar en {spot_title} ahora es tuyo hasta las {end.astimezone(BUENOS_AIRES):%H:%M}.",
    )


def booking_extended_for_owner(spot_title: str, end: datetime) -> PushMessage:
    return PushMessage(
        title="Extendieron una reserva",
        body=f"El conductor extendió su reserva en {spot_title} hasta las {end.astimezone(BUENOS_AIRES):%H:%M}.",
    )
