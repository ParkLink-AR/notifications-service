from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

# The whole platform assumes Buenos Aires local time (no DST) -- same as
# parking-service/src/availability/buenos-aires-time.ts and booking-service's
# BuenosAiresTimezone constant.
BUENOS_AIRES = ZoneInfo("America/Argentina/Buenos_Aires")

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
