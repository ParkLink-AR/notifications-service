from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Notification
from app.problem_json import problem_response

# The user's own inbox. The gateway authenticates these REQUIRED routes and injects
# X-User-Id -- every query below is scoped to it, so nobody can read or mark anyone
# else's notifications.
router = APIRouter(prefix="/notifications", tags=["inbox"])
# Service-to-service only (X-Internal-Key, see app/trusted_caller.py) -- no gateway route.
internal_router = APIRouter(prefix="/internal", tags=["internal"])

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100


class MarkReadBody(BaseModel):
    # The notifications to mark as read; omitted or null = all of them.
    ids: list[str] | None = Field(default=None, max_length=500)


def _user_uuid(x_user_id: str | None) -> uuid.UUID | None:
    try:
        return uuid.UUID(x_user_id) if x_user_id else None
    except ValueError:
        return None


def _missing_user(request: Request):
    return problem_response(
        request, 400, "Bad Request", "Missing X-User-Id header (request must go through the gateway)."
    )


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    # SQLite (tests) hands back naive datetimes; they're UTC like Postgres' timestamptz.
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _unread_count(db: Session, user_id: uuid.UUID) -> int:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.read_at.is_(None))
        .count()
    )


def _serialize(entry: Notification) -> dict:
    return {
        "id": entry.id,
        "kind": entry.kind,
        "role": entry.role,
        "title": entry.title,
        "body": entry.body,
        "data": entry.data or {},
        "created_at": _iso(entry.created_at),
        "read_at": _iso(entry.read_at),
        "resolved_at": _iso(entry.resolved_at),
    }


@router.get("")
def list_notifications(
    request: Request,
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    before: datetime | None = Query(default=None, description="Only older than this (next page)."),
    x_user_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """The caller's notifications, newest first, plus their unread count (for the tab's
    badge). Paged by `before`: pass the previous page's `next_before` to get older ones."""
    user_id = _user_uuid(x_user_id)
    if user_id is None:
        return _missing_user(request)

    query = db.query(Notification).filter(Notification.user_id == user_id)
    if before is not None:
        query = query.filter(Notification.created_at < before)
    rows = query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit + 1).all()

    page = rows[:limit]
    return {
        "items": [_serialize(row) for row in page],
        "unread_count": _unread_count(db, user_id),
        "next_before": _iso(page[-1].created_at) if len(rows) > limit else None,
    }


@router.get("/unread-count")
def unread_count(
    request: Request,
    x_user_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user_id = _user_uuid(x_user_id)
    if user_id is None:
        return _missing_user(request)
    return {"unread_count": _unread_count(db, user_id)}


@router.post("/read")
def mark_read(
    request: Request,
    body: MarkReadBody | None = None,
    x_user_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Marks the given notifications (or all of them) as read. Idempotent: already-read
    ones keep their original read time. Returns the new unread count."""
    user_id = _user_uuid(x_user_id)
    if user_id is None:
        return _missing_user(request)

    query = db.query(Notification).filter(
        Notification.user_id == user_id, Notification.read_at.is_(None)
    )
    if body is not None and body.ids is not None:
        if not body.ids:
            return {"unread_count": _unread_count(db, user_id)}
        query = query.filter(Notification.id.in_(body.ids))
    query.update({Notification.read_at: datetime.now(timezone.utc)}, synchronize_session=False)
    db.commit()
    return {"unread_count": _unread_count(db, user_id)}


@internal_router.delete("/users/{user_id}/notifications", status_code=204)
def delete_user_notifications(user_id: str, db: Session = Depends(get_db)):
    """Drops a user's whole inbox -- called by auth-service when the account's data is
    deleted for good. Idempotent."""
    owner = _user_uuid(user_id)
    if owner is not None:
        db.query(Notification).filter(Notification.user_id == owner).delete(synchronize_session=False)
        db.commit()
    return Response(status_code=204)
