import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


load_dotenv()


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} não foi definida no arquivo .env")
    return value


def _get_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default))
    try:
        return int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} deve ser um número inteiro") from exc


def _get_list_env(name: str, default: str) -> list[str]:
    raw_value = os.getenv(name, default)
    return [item.strip() for item in raw_value.split(",") if item.strip()]


DATABASE_URL = _get_required_env("DATABASE_URL")
JWT_SECRET_KEY = _get_required_env("JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = _get_int_env("ACCESS_TOKEN_EXPIRE_MINUTES", 1440)
PASSWORD_RESET_EXPIRE_MINUTES = _get_int_env("PASSWORD_RESET_EXPIRE_MINUTES", 30)

APP_TIMEZONE_NAME = os.getenv("APP_TIMEZONE", "America/Fortaleza")
APP_TIMEZONE = ZoneInfo(APP_TIMEZONE_NAME)

RESEND_API_KEY = _get_required_env("RESEND_API_KEY")
EMAIL_FROM = os.getenv("EMAIL_FROM", "Insulinet <onboarding@resend.dev>")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
CORS_ORIGINS = _get_list_env(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
)
