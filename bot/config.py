from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки читаются из переменных окружения (или из файла .env)."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Токен бота от @BotFather
    bot_token: str

    # Публичный HTTPS-адрес сервиса, например https://example.com
    # Если пусто — вебхук не выставляется (удобно для локальной отладки через polling)
    base_webhook_url: str = ""
    webhook_path: str = "/webhook"
    # Секрет для заголовка X-Telegram-Bot-Api-Secret-Token
    webhook_secret: str = ""

    host: str = "0.0.0.0"
    port: int = 8080

    db_path: str = "salah.db"
    days_per_year: int = 365


settings = Settings()
