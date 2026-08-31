import os
from urllib.parse import urlparse

from .base import *  # noqa: F401,F403

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
DEBUG = False

# Render sets RENDER_EXTERNAL_HOSTNAME automatically (e.g. bookwise.onrender.com).
# Extra hosts can be supplied via ALLOWED_HOSTS as a comma-separated list.
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]

RENDER_EXTERNAL_HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")

# ---------------------------------------------------------------------------
# Database — parsed from a single DATABASE_URL (Neon / Supabase / Render PG)
# Format: postgresql://USER:PASSWORD@HOST:PORT/DBNAME?sslmode=require
# ---------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    _db = urlparse(DATABASE_URL)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _db.path.lstrip("/"),
            "USER": _db.username,
            "PASSWORD": _db.password,
            "HOST": _db.hostname,
            "PORT": str(_db.port or "5432"),
            "OPTIONS": {"sslmode": os.getenv("DB_SSLMODE", "require")},
            "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
        }
    }
else:
    # Fallback to discrete DB_* vars (same shape as dev) if no URL is provided.
    DATABASES = {
        "default": {
            "ENGINE": os.getenv("DB_ENGINE", "django.db.backends.postgresql"),
            "NAME": os.getenv("DB_NAME"),
            "USER": os.getenv("DB_USER"),
            "PASSWORD": os.getenv("DB_PASSWORD"),
            "HOST": os.getenv("DB_HOST"),
            "PORT": os.getenv("DB_PORT"),
            "OPTIONS": {"sslmode": os.getenv("DB_SSLMODE", "require")},
        }
    }

# ---------------------------------------------------------------------------
# Storage
#   - Static files: WhiteNoise with compressed, hashed manifest
#   - Media (user uploads): Cloudinary, so files persist and are served over
#     HTTPS (Render's disk is ephemeral). Configured via the CLOUDINARY_URL env
#     var (cloudinary://<api_key>:<api_secret>@<cloud_name>).
# ---------------------------------------------------------------------------
STORAGES = {
    "default": {"BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

# ---------------------------------------------------------------------------
# Security — Render terminates TLS at its proxy
# ---------------------------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "True") == "True"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "3600"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# ---------------------------------------------------------------------------
# Email — Mailjet via django-anymail (HTTPS API; works on hosts that block SMTP).
# MAILJET_API_KEY / MAILJET_SECRET_KEY and DEFAULT_FROM_EMAIL come from base.py
# (all read from environment variables).
# ---------------------------------------------------------------------------
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "anymail.backends.mailjet.EmailBackend")

# ---------------------------------------------------------------------------
# Logging — send everything to stdout so Render captures it
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
}
