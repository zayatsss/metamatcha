from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./metamatcha.db"

    # Как часто фоновый воркер опрашивает цену и проверяет триггеры (в секундах).
    trigger_poll_interval: float = 0.5

    # Ключ для шифрования паролей аккаунтов (в проде брать из секретницы/ENV).
    secret_key: str = "CHANGE_ME_use_real_secret_in_production"

    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]


settings = Settings()
