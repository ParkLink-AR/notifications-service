from __future__ import annotations

from loguru import logger
from sqlalchemy.orm import Session

from app.config import settings
from app.handlers.outbound import OutboundPush
from app.models import DeviceToken

# ParkLink brand teal (src/theme/light in the mobile app). Tints the OS-shown
# Android notification.
BRAND_COLOR = "#168B8D"

try:  # firebase-admin is optional for tooling / log-only mode
    import firebase_admin
    from firebase_admin import credentials, messaging
except ImportError:  # pragma: no cover - exercised only where the dep is absent
    firebase_admin = None
    credentials = None
    messaging = None

_firebase_app = None


def init_firebase() -> None:
    """Initialise the Firebase Admin SDK once, from the service-account JSON at
    settings.GOOGLE_APPLICATION_CREDENTIALS. When the path is empty or the
    library is missing, the sender falls back to log-only mode (tests, local
    without Firebase)."""
    global _firebase_app
    if _firebase_app is not None:
        return
    if not settings.GOOGLE_APPLICATION_CREDENTIALS:
        logger.warning("[push] GOOGLE_APPLICATION_CREDENTIALS not set -- sender in log-only mode")
        return
    if firebase_admin is None:
        logger.warning("[push] firebase-admin not installed -- sender in log-only mode")
        return
    try:
        cred = credentials.Certificate(settings.GOOGLE_APPLICATION_CREDENTIALS)
        _firebase_app = firebase_admin.initialize_app(cred)
    except (FileNotFoundError, ValueError) as exc:
        logger.warning(
            f"[push] could not load {settings.GOOGLE_APPLICATION_CREDENTIALS} ({exc}) "
            "-- sender in log-only mode"
        )
        return
    logger.info("[push] Firebase Admin initialised")


def _is_enabled() -> bool:
    return messaging is not None and _firebase_app is not None


def _tokens_for(db: Session, user_ids: set[str]) -> dict[str, list[str]]:
    if not user_ids:
        return {}
    rows = db.query(DeviceToken).filter(DeviceToken.user_id.in_(user_ids)).all()
    out: dict[str, list[str]] = {}
    for row in rows:
        out.setdefault(str(row.user_id), []).append(row.token)
    return out


def prune_tokens(db: Session, tokens: list[str]) -> int:
    """Delete device-token rows FCM reported as permanently invalid."""
    if not tokens:
        return 0
    deleted = (
        db.query(DeviceToken)
        .filter(DeviceToken.token.in_(tokens))
        .delete(synchronize_session=False)
    )
    db.commit()
    if deleted:
        logger.info(f"[push] pruned {deleted} dead token(s)")
    return deleted


def _is_permanent(exc: Exception | None) -> bool:
    if exc is None:
        return False
    if type(exc).__name__ in {"UnregisteredError", "SenderIdMismatchError"}:
        return True
    code = str(getattr(exc, "code", "") or "").lower()
    return "not-registered" in code or "invalid-argument" in code



def _push_data(push: OutboundPush) -> dict[str, str]:
    """The push's data, always saying which side of the app it's for (the inbox entry's
    role) -- tapping it switches the app to that mode before opening the screen."""
    data = {k: str(v) for k, v in push.data.items()}
    if push.role and "role" not in data:
        data["role"] = push.role
    return data

def send_pushes(db: Session, pushes: list[OutboundPush]) -> int:
    """Deliver each OutboundPush to every registered device of its recipient.
    Returns the number of messages FCM accepted (or, in log-only mode, the
    number that would have been sent). Prunes tokens FCM rejects for good."""
    tokens_by_user = _tokens_for(db, {p.user_id for p in pushes})

    targets: list[tuple[OutboundPush, str]] = []
    for push in pushes:
        for token in tokens_by_user.get(push.user_id, []):
            targets.append((push, token))

    if not targets:
        logger.info("[push] no registered devices for recipients; nothing to send")
        return 0

    if not _is_enabled():
        for push, token in targets:
            logger.info(
                f"[push] (log-only) user={push.user_id} token=…{token[-6:]} :: "
                f"{push.title} / {push.body}"
            )
        return len(targets)

    fcm_messages = [
        messaging.Message(
            token=token,
            notification=messaging.Notification(title=push.title, body=push.body),
            data=_push_data(push),
            android=messaging.AndroidConfig(
                priority="high",
                # Small icon comes from the app's expo-notifications config
                # plugin (ParkLink mark); this tints it and routes the
                # OS-shown notification to the app's HIGH-importance "bookings"
                # channel so it pops as a heads-up banner.
                notification=messaging.AndroidNotification(
                    color=BRAND_COLOR,
                    channel_id="bookings",
                ),
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(aps=messaging.Aps(sound="default"))
            ),
        )
        for push, token in targets
    ]

    batch = messaging.send_each(fcm_messages)

    dead: list[str] = []
    for (push, token), result in zip(targets, batch.responses):
        if result.success:
            continue
        logger.warning(
            f"[push] send failed user={push.user_id} token=…{token[-6:]}: {result.exception}"
        )
        if _is_permanent(result.exception):
            dead.append(token)

    prune_tokens(db, dead)
    return batch.success_count
