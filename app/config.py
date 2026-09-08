from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"

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
    GOOGLE_APPLICATION_CREDENTIALS: str = ""

    # The AMQP consumer starts with the app. Disabled in the test suite.
    CONSUMER_ENABLED: bool = True

    HTTP_PORT: int = 8000

    model_config = ConfigDict(extra="ignore", env_file=".env", env_file_encoding="utf-8")


settings = Settings()
