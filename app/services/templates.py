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


def booking_confirmed_for_driver(spot_title: str, start: datetime, end: datetime) -> PushMessage:
    return PushMessage(
        title="Reserva confirmada",
        body=f"Tu reserva en {spot_title} {_fmt_range(start, end)} está confirmada.",
    )


def booking_confirmed_for_owner(spot_title: str, start: datetime, end: datetime) -> PushMessage:
    return PushMessage(
        title="Nueva reserva",
        body=f"Reservaron tu cochera {spot_title} {_fmt_range(start, end)}.",
    )


def booking_pending_approval_for_owner(
    spot_title: str, start: datetime, end: datetime, deadline: datetime | None
) -> PushMessage:
    """Sent to the owner right after the driver pays: they must accept or reject."""
    body = (
        f"Reservaron y pagaron {spot_title} {_fmt_range(start, end)}. "
        "Confirmá o rechazá la reserva"
    )
    if deadline is not None:
        body += f" antes del {_fmt_datetime(deadline)}"
    return PushMessage(title="Confirmá una reserva", body=body + ".")
