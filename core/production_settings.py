"""
Production Django settings for Sony Feeding Kurtis.
Loaded when DJANGO_SETTINGS_MODULE=core.production_settings.
Enforces SSL, HTTPS cookies, PostgreSQL database, strict CORS, and security headers.
"""

import os
from .settings import *

# Enforce DEBUG is strictly False in production
DEBUG = False

# Production secret key
SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'django-secure-production-fallback-key-replace-in-env-2026',
)

# Production allowed hosts
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv(
        'ALLOWED_HOSTS',
        'sonyfeedingkurtis.com,www.sonyfeedingkurtis.com,api.sonyfeedingkurtis.com,localhost,127.0.0.1,testserver',
    ).split(',')
    if host.strip()
]

# Database configuration: PostgreSQL in production when POSTGRES_DB is provided
DB_NAME = os.getenv('POSTGRES_DB')
if DB_NAME:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': DB_NAME,
            'USER': os.getenv('POSTGRES_USER', 'sony_user'),
            'PASSWORD': os.getenv('POSTGRES_PASSWORD', ''),
            'HOST': os.getenv('POSTGRES_HOST', 'localhost'),
            'PORT': os.getenv('POSTGRES_PORT', '5432'),
            'CONN_MAX_AGE': 600,
        }
    }

# HTTPS & Security Hardening
SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'True').lower() in ('true', '1', 't')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '31536000'))  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Production CORS
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        'CORS_ALLOWED_ORIGINS',
        'https://sonyfeedingkurtis.com,https://www.sonyfeedingkurtis.com',
    ).split(',')
    if origin.strip()
]
for prod_domain in ('https://sonyfeedingkurtis.com', 'https://www.sonyfeedingkurtis.com'):
    if prod_domain not in CORS_ALLOWED_ORIGINS:
        CORS_ALLOWED_ORIGINS.append(prod_domain)
CORS_ALLOW_CREDENTIALS = True

# Static files and media in production
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_ROOT = BASE_DIR / 'media'

# Logging configuration for production
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'payments': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'orders': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

