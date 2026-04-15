from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://fortold:fortold_dev@localhost:5432/fortold_db"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # JWT
    jwt_secret_key: str = "CHANGE_ME"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # Claude API
    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-4-6"
    llm_timeout_seconds: int = 60
    llm_max_tokens: int = 4096

    # Storage
    upload_dir: str = "/app/uploads"
    artifacts_dir: str = "/app/artifacts"
    max_upload_bytes: int = 104_857_600  # 100 MB

    # App
    environment: str = "development"
    cors_origins: str = "http://localhost:3000"
    log_level: str = "INFO"

    # RQ
    rq_queue_name: str = "fortold_queue"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


settings = Settings()
