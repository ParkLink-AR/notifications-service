from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DeviceToken
from app.problem_json import problem_response

router = APIRouter(prefix="/notifications", tags=["tokens"])
# Service-to-service only (X-Internal-Key, see app/trusted_caller.py) -- no gateway route.
internal_router = APIRouter(prefix="/internal", tags=["internal"])

VALID_PLATFORMS = {"android", "ios"}


class RegisterTokenBody(BaseModel):
    token: str = Field(min_length=1, max_length=4096)
    platform: str
    device_id: str | None = Field(default=None, max_length=255)


@router.put("/tokens")
def register_token(
    body: RegisterTokenBody,
    request: Request,
    x_user_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Upsert the caller's FCM token. The gateway validates the JWT for this
    REQUIRED route and injects X-User-Id (same contract parking-service relies
    on) -- a missing header means the request bypassed the gateway."""
    if not x_user_id:
        return problem_response(
            request, 400, "Bad Request",
            "Missing X-User-Id header (request must go through the gateway).",
        )
    if body.platform not in VALID_PLATFORMS:
        return problem_response(
            request, 400, "Bad Request", "platform must be one of: android, ios",
        )

    existing = db.get(DeviceToken, body.token)
    if existing is None:
        db.add(
            DeviceToken(
                token=body.token,
                user_id=x_user_id,
                platform=body.platform,
                device_id=body.device_id,
            )
        )
    else:
        existing.user_id = x_user_id
        existing.platform = body.platform
        if body.device_id is not None:
            existing.device_id = body.device_id
    db.commit()
    return {"status": "ok"}


@router.delete("/tokens/{token}", status_code=204)
def delete_token(
    token: str,
    x_user_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Drop a token on logout. Idempotent -- deleting an unknown token is a
    no-op 204."""
    row = db.get(DeviceToken, token)
    if row is not None:
        db.delete(row)
        db.commit()
    return Response(status_code=204)


@internal_router.delete("/users/{user_id}/device-tokens", status_code=204)
def delete_user_tokens(user_id: str, db: Session = Depends(get_db)):
    """Drops every device token of a user, so they get no more pushes -- called by
    auth-service when the account is suspended or closed. Idempotent."""
    db.query(DeviceToken).filter(DeviceToken.user_id == user_id).delete(synchronize_session=False)
    db.commit()
    return Response(status_code=204)
