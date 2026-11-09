import os
from pathlib import Path

from decouple import Config, RepositoryEnv


def configure_settings() -> None:
    env_file = Path(__file__).resolve().parent / ".env"
    config = Config(RepositoryEnv(str(env_file)) if env_file.exists() else {})
    environment = config("BLOG_ENV_ID", default="local")
    if environment not in {"local", "prod"}:
        raise ValueError("BLOG_ENV_ID must be local or prod")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", f"settings.env.{environment}")
