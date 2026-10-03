from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/payments"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    api_key: str = "dev-api-key-change-me"

    outbox_poll_interval_seconds: float = 0.5
    outbox_batch_size: int = 20

    webhook_timeout_seconds: float = 10.0
    webhook_max_attempts: int = 3

    payment_success_rate: float = 0.9
    gateway_delay_min_seconds: float = 2.0
    gateway_delay_max_seconds: float = 5.0

    max_process_attempts: int = 3


settings = Settings()
