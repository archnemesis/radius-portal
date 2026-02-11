import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    app_secret: str = os.getenv("APP_SECRET", "dev-secret-change-me")

    db_host: str = os.getenv("RADIUS_DB_HOST", "localhost")
    db_port: int = int(os.getenv("RADIUS_DB_PORT", "5432"))
    db_name: str = os.getenv("RADIUS_DB_NAME", "radius")
    db_user: str = os.getenv("RADIUS_DB_USER", "radius")
    db_pass: str = os.getenv("RADIUS_DB_PASS", "")

    flask_host: str = os.getenv("FLASK_HOST", "127.0.0.1")
    flask_port: int = int(os.getenv("FLASK_PORT", "5000"))
    flask_debug: bool = os.getenv("FLASK_DEBUG", "0") == "1"
