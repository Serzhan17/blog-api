from settings.base import *  # noqa: F403
from settings.conf import BASE_DIR, config

DEBUG = True
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

# Enable temporarily to compare SQL counts for 10 and 100 admin rows.

if config("BLOG_SQL_DEBUG", default=False, cast=bool):
    LOGGING["loggers"]["django.db.backends"] = {  # noqa: F405
        "handlers": ["console"],
        "level": "DEBUG",
        "propagate": False,
    }
