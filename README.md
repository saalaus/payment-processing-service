# Payment Processing Service

Асинхронный микросервис обработки платежей: API принимает запрос, пишет платёж и событие в outbox в одной транзакции, publisher публикует `payments.new` в RabbitMQ, consumer эмулирует шлюз и шлёт webhook.

## Стек

- FastAPI + Pydantic v2
- SQLAlchemy 2.0 (async) + PostgreSQL + Alembic
- RabbitMQ + FastStream
- Docker Compose

## Запуск

```bash
cp .env.example .env
docker compose up --build
```

Сервисы:

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- RabbitMQ UI: http://localhost:15672 (guest / guest)

API-ключ по умолчанию: `dev-api-key-change-me` (переменная `API_KEY`).

## Примеры

Создание платежа:

```bash
curl -i -X POST http://localhost:8000/api/v1/payments \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key-change-me" \
  -H "Idempotency-Key: test-key-1" \
  -d "{\"amount\": 199.99, \"currency\": \"RUB\", \"description\": \"Order 42\", \"metadata\": {\"order_id\": \"42\"}, \"webhook_url\": \"https://httpbin.org/post\"}"
```

Ответ `202 Accepted`:

```json
{
  "payment_id": "…",
  "status": "pending",
  "created_at": "…"
}
```

Повтор с тем же `Idempotency-Key` и тем же телом вернёт тот же платёж. Другое тело с тем же ключом - `409 Conflict`.

Получение платежа:

```bash
curl -i http://localhost:8000/api/v1/payments/<payment_id> \
  -H "X-API-Key: dev-api-key-change-me"
```

Health (без ключа): `GET http://localhost:8000/health`.

## Как это устроено

1. **Outbox.** `POST /api/v1/payments` сохраняет `payments` (`pending`) и запись в `outbox` в одной транзакции. В брокер API не пишет.
2. **Publisher.** Отдельный процесс читает unpublished outbox (`FOR UPDATE SKIP LOCKED`) и публикует в exchange `payments`, routing key `payments.new`.
3. **Consumer.** Один обработчик: пауза 2–5 секунд, 90% success / 10% fail, обновляет статус, шлёт webhook.
4. **Retry webhook.** До 3 попыток с экспоненциальной задержкой (1s, 2s, 4s).
5. **Retry очереди.** После ошибки обработки сообщение уходит в `payments.retry.1` (1s), затем в `payments.retry.2` (2s) и возвращается в `payments.new`. Третья неуспешная обработка — в `payments.dlq`.
6. **Идемпотентность.** Уникальный `idempotency_key`; повторная обработка уже финализированного платежа не эмулирует шлюз повторно.

Очереди в RabbitMQ UI: `payments.new`, `payments.retry.1`, `payments.retry.2`, `payments.dlq`.

## Локально без Docker

Нужны PostgreSQL и RabbitMQ, затем:

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
uv run python -m app.workers.outbox_publisher
uv run python -m app.workers.consumer
```
