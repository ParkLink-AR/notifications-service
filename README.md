# notifications-service

Las notificaciones de conductores y propietarios de ParkLink: la **bandeja** de cada
usuario (la pestaña Notificaciones de la app y su contador de no leídas) y los **push**
por **Firebase Cloud Messaging** (Android + iOS) con el **Firebase Admin SDK**.

Se alimenta de los **eventos** que publica `booking-service` en el exchange topic
`parklink.events` de RabbitMQ. Por cada evento que le toca a un usuario guarda una entrada
en su bandeja (tabla `notifications`), le manda el push y publica `notification.created`
para que el gateway le avise al instante a la app abierta (WebSocket
`/notifications/live`, ver `gateway/app/live.py`). La bandeja es la fuente de verdad: el
push y el aviso en vivo son solo avisos de que hay algo nuevo.

Construido con **FastAPI** + **SQLAlchemy** + **aio-pika** + **firebase-admin**, mismas
convenciones que `auth-service` / `gateway` (problem+json, `loguru`, `/livez` `/readyz`,
esquema por `Base.metadata.create_all`, sin migraciones).

## Qué implementa

### Consumo de eventos

`app/messaging/consumer.py` declara una queue **propia** (`notifications.events`) bindeada
al exchange `parklink.events`, con `prefetch=10` y **ack manual**.

| Routing key | Handler | Para quién (`kind` en la bandeja) |
|---|---|---|
| `booking.pending_approval` | `booking_pending_approval.py` | propietario (`owner_request`) |
| `booking.confirmed` | `booking_confirmed.py` | conductor (`driver_confirmed`) |
| `booking.cancelled` | `booking_cancelled.py` | según `cancelled_by`: conductor (`driver_rejected`, `driver_request_expired`, `driver_spot_unavailable`) o propietario (`owner_booking_cancelled`) |
| `booking.verified` | `booking_verified.py` | conductor (`driver_verified`) |
| `booking.completed` | `booking_completed.py` | conductor (`driver_review_prompt`) y propietario (`owner_review_prompt`) |
| `booking.message_sent` | `booking_message_sent.py` | el otro lado de la reserva (`message_received`) |
| `support.ticket_replied` | `support_ticket_replied.py` | quien abrió el ticket (`ticket_replied`) |
| `settlement.paid` | `settlement_paid.py` | propietario (`owner_settlement_paid`) |

Sumar otro evento = agregar una entrada a `BINDING_KEYS` y una función a `HANDLERS`.
`booking.confirmed` y `booking.cancelled` además marcan como respondida (`resolved_at`) la
solicitud del propietario sobre esa reserva, así la app deja de ofrecer aceptar/rechazar.

**Idempotencia:** RabbitMQ entrega *at-least-once*. Antes de actuar, el consumer chequea
la tabla `processed_events` por `event_id` y saltea los duplicados. La entrada de la bandeja
y la marca de procesado se guardan en la misma transacción, así un evento repetido nunca
duplica una notificación; el push se manda después (si falla, la notificación igual queda).

### Bandeja (vía gateway, autenticada)

| Método y ruta | Qué hace |
|---|---|
| `GET /notifications?limit=50&before=<iso>` | Las notificaciones del usuario, de la más nueva a la más vieja, con `unread_count` y `next_before` para la página siguiente |
| `GET /notifications/unread-count` | Solo el contador de no leídas |
| `POST /notifications/read` `{"ids": [...]}` | Marca como leídas esas (o todas, sin `ids`); devuelve el nuevo `unread_count` |
| `DELETE /internal/users/{id}/notifications` | Solo entre servicios: auth-service borra la bandeja al eliminar la cuenta |

Cada entrada trae `kind`, `role` (`driver`/`owner`) y `data` (cochera, fechas, ids): la app
arma el texto en el idioma del usuario. `title`/`body` son los textos del push en castellano.

**Reintentos:** si el handler falla por algo transitorio (parking-service caído, timeout),
el mensaje se re-encola (`nack requeue=True`). Un payload malformado se descarta (ack) para
no quedar en loop.

### Contrato de `booking.confirmed`

Lo publica `booking-service` al confirmar una reserva. `owner_user_id` y el título de la
cochera **no** viajan en el evento (booking-service no los tiene): los resuelve este
servicio con `GET {PARKING_SERVICE_URL}/parking-spots/{parking_spot_id}` (ruta pública).

```json
{
  "event_id": "uuid",
  "event_type": "booking.confirmed",
  "occurred_at": "2026-09-04T18:03:00-03:00",
  "booking_id": "uuid",
  "parking_spot_id": "uuid",
  "driver_user_id": "uuid",
  "start": "2026-09-04T18:00:00-03:00",
  "end": "2026-09-04T20:00:00-03:00",
  "amount": 240000,
  "payment_id": "mp-123"
}
```

### Registro de device tokens

Detrás del gateway, rutas `REQUIRED` (el gateway valida el JWT e inyecta `X-User-Id`).

| Método | Ruta | Body | Efecto |
|---|---|---|---|
| `PUT` | `/notifications/tokens` | `{ "token": str, "platform": "android"\|"ios", "device_id"?: str }` | upsert por `token`, dueño = `X-User-Id` |
| `DELETE` | `/notifications/tokens/{token}` | — | borra el token (logout). Idempotente. |

Health: `GET /livez`, `GET /readyz` (chequea DB), `GET /health`.

### Envío por FCM

`app/services/push.py` inicializa el Admin SDK desde el JSON de service account en
`GOOGLE_APPLICATION_CREDENTIALS` y manda con `messaging.send_each()`. Si FCM reporta un
token como definitivamente inválido (`UnregisteredError`, `invalid-argument`), esa fila se
borra de `device_tokens`.

**Modo log-only:** si `GOOGLE_APPLICATION_CREDENTIALS` está vacío (tests, o local sin
Firebase), el sender no llama a FCM: sólo loguea qué habría mandado. El resto del flujo
(consumo, resolución de destinatarios, idempotencia) funciona igual.

## Variables de entorno

Ver [`.env.example`](.env.example).

| Variable | Descripción | Default |
|---|---|---|
| `DATABASE_URL` | Postgres propio (device tokens + eventos procesados) | `postgresql://parklink_notif:parklink_notif@db-notifications:5432/parklink_notif_db` |
| `RABBITMQ_URL` | Broker compartido | `amqp://guest:guest@rabbitmq:5672/` |
| `EVENTS_EXCHANGE` | Exchange topic compartido | `parklink.events` |
| `NOTIFICATIONS_QUEUE` | Queue propia de este servicio | `notifications.events` |
| `PARKING_SERVICE_URL` | Para resolver propietario + título de cochera | `http://parking-service:3001` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Ruta al JSON de service account de Firebase. Vacío = modo log-only | *(vacío)* |
| `CONSUMER_ENABLED` | Arranca el consumer con la app. `false` en tests | `true` |
| `HTTP_PORT` | Puerto HTTP | `8000` |

## Setup de Firebase (una vez)

1. Firebase Console → crear proyecto.
2. **Android**: agregar app (`com.parklink.mobile`) → `google-services.json` va en `mobile/`.
3. **iOS**: agregar app (`com.parklink.mobile`) → `GoogleService-Info.plist` va en `mobile/`.
4. **iOS APNs**: Apple Developer → crear *APNs Auth Key* (`.p8`) → subirla en Firebase
   Console → Project Settings → Cloud Messaging.
5. **Backend**: Firebase Console → Project Settings → *Service accounts* → *Generate new
   private key* → guardar el JSON en `notifications-service/secrets/firebase-service-account.json`
   (gitignored). En Render, cargarlo como *secret file*.

## Cómo levantarlo

### Con Docker (aislado)

```bash
cp .env.example .env
mkdir -p secrets && cp /ruta/al/firebase-service-account.json secrets/
docker compose up --build
```

Levanta `db-notifications` (puerto host `5436`), RabbitMQ (`5672` / UI `15672`) y el
servicio (`8085` → `8000`).

Para el ecosistema completo, usar `../root/compose.yaml` (`notifications-service` ya está
declarado ahí, junto con la ruta en el gateway).

### Local (sin Docker)

```bash
pip install -r requirements.txt
cp .env.example .env   # apuntar DATABASE_URL / RABBITMQ_URL / PARKING_SERVICE_URL a localhost
uvicorn main:app --reload --port 8000
```

## Tests

```bash
pip install -r requirements.txt
pytest
```

No requieren Docker, RabbitMQ ni Firebase: usan SQLite, el consumer arranca apagado
(`CONSUMER_ENABLED=false`) y el sender corre en modo log-only.

```
tests/
├── conftest.py                        # TestClient + SQLite + override de get_db
├── test_tokens_api.py                 # PUT/DELETE /notifications/tokens, upsert, validaciones
├── test_booking_confirmed_handler.py  # evento -> mensajes (conductor + propietario), fallbacks
├── test_push_service.py               # fan-out por dispositivo, prune de tokens muertos
└── test_consumer_idempotency.py       # mismo event_id 2 veces -> 1 envío
```

## Estructura

```
main.py                     # FastAPI app: lifespan (create_all + init firebase + task del consumer)
app/
├── config.py               # Settings (pydantic-settings)
├── database.py             # engine / SessionLocal / Base
├── problem_json.py         # respuestas application/problem+json
├── logger.py
├── models/
│   ├── guid.py             # UUID portable (copiado de auth-service)
│   ├── device_token.py     # tabla device_tokens
│   └── processed_event.py  # tabla processed_events (idempotencia)
├── api/
│   └── tokens.py           # PUT/DELETE /notifications/tokens
├── messaging/
│   ├── events.py           # modelos pydantic de los eventos entrantes
│   └── consumer.py         # aio-pika: queue, bindings, dispatch, ack manual
├── handlers/
│   └── booking_confirmed.py# evento -> list[OutboundPush]
└── services/
    ├── recipients.py       # resuelve owner_id + título vía parking-service
    ├── templates.py        # textos (es-AR) por tipo de notificación
    └── push.py             # firebase-admin: send_each + prune de tokens
```
