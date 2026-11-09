from settings.base import *  # noqa: F403
from settings.conf import (
    BLOG_DB_HOST,
    BLOG_DB_NAME,
    BLOG_DB_PASSWORD,
    BLOG_DB_PORT,
    BLOG_DB_SSLMODE,
    BLOG_DB_USER,
)

DEBUG = False
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": BLOG_DB_NAME,
        "USER": BLOG_DB_USER,
        "PASSWORD": BLOG_DB_PASSWORD,
        "HOST": BLOG_DB_HOST,
        "PORT": BLOG_DB_PORT,
        "OPTIONS": {"sslmode": BLOG_DB_SSLMODE},
    }
}
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_CONTENT_TYPE_NOSNIFF = True
