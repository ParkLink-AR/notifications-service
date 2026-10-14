from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    # Shared secrets proving a request came through the ParkLink gateway or from another
    # ParkLink service (see app/trusted_caller.py). Both empty = every request passes, for
    # a bare local run outside docker compose.
    GATEWAY_INTERNAL_SECRET: str = ""
    INTERNAL_SERVICE_KEY: str = ""

    # notifications-service owns a small DB: the user -> device-token map and a
    # log of already-processed event ids (RabbitMQ is at-least-once).
    DATABASE_URL: str = "postgresql://parklink_notif:parklink_notif@db-notifications:5432/parklink_notif_db"

    # Shared event bus. Same exchange gateway/app/rabbitmq.py and
    # booking-service/cmd/setup_rabbitmq.go declare. The booking.* events are
    # self-contained (spot title + both party ids embedded by booking-service),
    # so this service makes no outbound calls to resolve a recipient.
    RABBITMQ_URL: str = "amqp://guest:guest@rabbitmq:5672/"
    EVENTS_EXCHANGE: str = "parklink.events"
    # Our OWN queue -- not booking-service's "events.notifications" (that one is
    # its own log-only consumer). Distinct queues each get their own copy.
    NOTIFICATIONS_QUEUE: str = "notifications.events"

    # Path to the Firebase service-account JSON used by the Admin SDK. Empty =
    # run the push sender in log-only mode (tests, or local without Firebase).
    # Firebase service-account JSON. Committed at ./secrets (private repo); this
    # default is used when running the service directly. In docker it's set to
    # /run/secrets/firebase-service-account.json by compose. Empty = log-only.
    GOOGLE_APPLICATION_CREDENTIALS: str = "./secrets/firebase-service-account.json"

    # Transactional email through Brevo (same account auth-service uses). Empty key = log-only.
    BREVO_API_KEY: str = ""
    EMAIL_FROM: str = "no-reply@mail.parklink.com.ar"
    EMAIL_FROM_NAME: str = "ParkLink Argentina"
    # Where ParkLink staff hear about support tickets: a new ticket, or a user writing on one.
    SUPPORT_INBOX_EMAIL: str = "contacto@parklink.com.ar"
    # auth-service, for the accounts an admin's announcement goes to (see app/api/broadcasts.py).
    AUTH_SERVICE_URL: str = "http://auth-service:8000"

    # The admin panel's base URL, for the "open the ticket" link in those emails. Empty = no link.
    ADMIN_PANEL_URL: str = ""

    # The AMQP consumer starts with the app. Disabled in the test suite.
    CONSUMER_ENABLED: bool = True

    HTTP_PORT: int = 8000

    model_config = ConfigDict(extra="ignore", env_file=".env", env_file_encoding="utf-8")


settings = Settings()
