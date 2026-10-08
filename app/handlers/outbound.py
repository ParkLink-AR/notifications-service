from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class OutboundPush:
    """One notification for a single user: pushed to every registered device of theirs
    (app/services/push.py) and, when it has a `kind`, kept in their notifications inbox
    (app/models/notification.py). Handlers turn a domain event into a list of these."""

    user_id: str
    title: str
    body: str
    data: dict[str, str]
    # Inbox entry: what happened, which side of the booking it's for, and what the app
    # needs to render and open it.
    kind: str = ""
    role: str | None = None
    payload: dict = field(default_factory=dict)
