from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    env: str = "development"

    cache_enabled: bool = True

    # Reject registrations whose email domain can't receive mail (MX lookup).
    # Disabled in tests so the suite never depends on live DNS.
    verify_email_deliverability: bool = True
    email_verify_timeout: float = 5.0  # seconds, per DNS query

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()