"""Settings loaded from env vars (12-factor)."""
from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    env: str = "dev"
    frontend_origin: str = "https://app.quantpilot.io"

    # Database
    database_url: str = "postgresql+psycopg2://quantpilot:dev@localhost:5432/quantpilot"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_secret: str = "dev-secret-change-me"
    jwt_alg: str = "HS256"
    jwt_ttl_min: int = 30
    jwt_refresh_ttl_days: int = 14

    # KMS-style symmetric key (dev only; use real KMS in prod)
    kms_key_b64: str = ""  # 32 bytes base64 for Fernet-like AEAD

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8080/auth/google/callback"
    google_scopes: str = (
        "openid email "
        "https://www.googleapis.com/auth/spreadsheets "
        "https://www.googleapis.com/auth/drive.file "
        "https://www.googleapis.com/auth/script.projects"
    )

    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    gemini_daily_quota_per_user: int = 100

    # Rate limits (Redis token bucket)
    rate_per_user_per_min: int = 60
    rate_per_ip_per_min: int = 600

    class Config:
        env_prefix = "QP_"
        env_file = ".env"

    @model_validator(mode="after")
    def validate_runtime_config(self):
        if self.env not in {"dev", "test", "prod"}:
            raise ValueError("QP_ENV must be dev, test, or prod")
        if self.env == "prod":
            if self.jwt_secret == "dev-secret-change-me" or len(self.jwt_secret) < 32:
                raise ValueError("QP_JWT_SECRET must be a random value of at least 32 characters in prod")
            if not self.kms_key_b64:
                raise ValueError("QP_KMS_KEY_B64 is required in prod")
            try:
                key = __import__("base64").b64decode(self.kms_key_b64, validate=True)
            except Exception as exc:
                raise ValueError("QP_KMS_KEY_B64 must be valid base64") from exc
            if len(key) not in {16, 24, 32}:
                raise ValueError("QP_KMS_KEY_B64 must decode to an AES key")
            if not self.frontend_origin.startswith("https://"):
                raise ValueError("QP_FRONTEND_ORIGIN must use HTTPS in prod")
        return self


settings = Settings()
