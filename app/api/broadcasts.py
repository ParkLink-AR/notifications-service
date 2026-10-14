"""Announcements ParkLink staff send from the admin panel ("Avisos"): each user in the
audience gets it as a notification in the app (kind "announcement") and a push. Reached
only through the gateway's ADMIN routes."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.handlers.outbound import OutboundPush
from app.messaging import live
from app.models import Broadcast, Notification
from app.services import push

router = APIRouter(prefix="/admin/broadcasts", tags=["broadcasts"])

AUDIENCES = ("all", "drivers", "owners")


class BroadcastIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=1000)
    audience: str = Field(pattern="^(all|drivers|owners)$")


def audience_user_ids(audience: str) -> list[str]:
    """Every active account in the audience, from auth-service."""
    response = httpx.get(
        f"{settings.AUTH_SERVICE_URL}/internal/users/ids",
        params={"audience": audience},
        headers={"X-Internal-Key": settings.INTERNAL_SERVICE_KEY},
        timeout=15.0,
    )
    response.raise_for_status()
    return [str(user_id) for user_id in response.json()]


def _serialize(broadcast: Broadcast) -> dict:
    return {
        "id": broadcast.id,
        "title": broadcast.title,
        "body": broadcast.body,
        "audience": broadcast.audience,
        "recipients": broadcast.recipients,
        "created_by": broadcast.created_by,
        "created_at": broadcast.created_at.isoformat() if broadcast.created_at else None,
    }


@router.post("", status_code=201)
async def send_broadcast(
    payload: BroadcastIn,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
):
    try:
        user_ids = audience_user_ids(payload.audience)
    except httpx.HTTPError as exc:
        logger.warning(f"[broadcasts] could not list the audience: {exc}")
        raise HTTPException(status_code=502, detail="No se pudo obtener a quién mandarle el aviso.") from exc

    title, body = payload.title.strip(), payload.body.strip()
    broadcast = Broadcast(title=title, body=body, audience=payload.audience, recipients=len(user_ids), created_by=x_user_id)
    db.add(broadcast)
    data_payload = {"broadcast_id": broadcast.id, "title": title, "body": body}
    pushes = [
        OutboundPush(user_id, title, body, {"type": "announcement"}, kind="announcement", payload=data_payload)
        for user_id in user_ids
    ]
    db.add_all(
        Notification(user_id=p.user_id, role=None, kind=p.kind, data=p.payload, title=p.title, body=p.body)
        for p in pushes
    )
    db.commit()
    db.refresh(broadcast)

    # After the commit: the inbox is the source of truth, the push only a heads-up.
    try:
        push.send_pushes(db, pushes)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[broadcasts] push failed for broadcast {broadcast.id}: {exc}")
    await live.announce(set(user_ids))
    logger.info(f"[broadcasts] sent {broadcast.id} to {len(user_ids)} users ({payload.audience})")
    return _serialize(broadcast)


@router.get("")
def list_broadcasts(db: Session = Depends(get_db)):
    """What was sent, newest first."""
    rows = db.query(Broadcast).order_by(Broadcast.created_at.desc()).limit(100).all()
    return [_serialize(row) for row in rows]
