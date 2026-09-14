from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OutboundPush:
    """One notification to deliver to every registered device of a single user.
    Handlers turn a domain event into a list of these; app/services/push.py sends
    them."""

    user_id: str
    title: str
    body: str
    data: dict[str, str]
