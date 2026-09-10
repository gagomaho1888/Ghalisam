import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


# ---------------------------------------------------------------------------
# Environment variables
# ---------------------------------------------------------------------------

def env_str(key: str, default: str = '') -> str:
    return os.environ.get(key, default)

def env_bool(key: str, default: bool = False) -> bool:
    val = os.environ.get(key, str(default)).strip().lower()
    return val in ('1', 'true', 'yes', 'on')

def env_int(key: str, default: int = 0) -> int:
    try:
        return int(os.environ.get(key, str(default)))
    except (ValueError, TypeError):
        return default

def env_list(key: str, default: str = '') -> list:
    raw = os.environ.get(key, default)
    return [h.strip() for h in raw.split(',') if h.strip()]


# ---------------------------------------------------------------------------
# Security – keep secrets out of the repo
# ---------------------------------------------------------------------------

_secret = env_str('DJANGO_SECRET_KEY')
if not _secret or _secret == 'change-me-to-a-long-random-string':
    raise ValueError(
        'DJANGO_SECRET_KEY doit être défini avec une valeur forte et unique en production. '
        'Générez-en une avec : python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"'
    )
SECRET_KEY = _secret

DEBUG = env_bool('DJANGO_DEBUG', False)

ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'ghalisam.onrender.com']

# Production security – active seulement quand DEBUG=False
if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool('DJANGO_SECURE_SSL_REDIRECT', True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env_int('DJANGO_HSTS_SECONDS', 31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    X_FRAME_OPTIONS = 'DENY'
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

SECURE_CONTENT_TYPE_NOSNIFF = True

# Content-Security-Policy – active en production (DEBUG=False) par défaut,
# ou quand CSP_ENABLED=True explicitement (utile pour tester en dev).
CSP_ENABLED = env_bool('DJANGO_CSP_ENABLED', not DEBUG)

CONTENT_SECURITY_POLICY = {
    "default-src": "'self'",
    "script-src": "'self' __NONCE__",
    "style-src": "'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src": "'self' data: https://fonts.gstatic.com",
    "img-src": "'self' data: https://via.placeholder.com https://*.tile.openstreetmap.org",
    "connect-src": "'self' ws: wss:",
    "object-src": "'none'",
    "base-uri": "'self'",
    "frame-ancestors": "'none'",
    "form-action": "'self'",
}


# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.postgres',
    'channels',
    'Articles',
    'Utilisateurs',
    'dbfiles',
]

ASGI_APPLICATION = 'ecommerce.asgi.application'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': env_str(
            'CHANNEL_BACKEND',
            'channels.layers.InMemoryChannelLayer',
        ),
        'CONFIG': {},
    },
}

# Activer Redis quand la variable REDIS_URL est définie
_redis_url = env_str('REDIS_URL', '')
if _redis_url:
    CHANNEL_LAYERS['default'] = {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [_redis_url],
        },
    }
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': [_redis_url],
            'KEY_PREFIX': 'ecommerce',
        },
    }
elif not DEBUG:
    import logging
    logging.getLogger('django').warning(
        'REDIS_URL non défini en production. '
        'Les notifications WebSocket ne fonctionneront que sur un seul worker '
        'et les rate-limits ne seront pas partagés entre workers. '
        'Définissez REDIS_URL pour un fonctionnement multi-worker.'
    )

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'ecommerce.middleware.CSPMiddleware',
    'ecommerce.middleware.Handle404Middleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ecommerce.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
                'ecommerce.middleware.csp_nonce',
            ],
        },
    },
]

WSGI_APPLICATION = 'ecommerce.wsgi.application'


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

import dj_database_url

DATABASES = {}
_db_url = env_str('DATABASE_URL')
if _db_url:
    DATABASES['default'] = dj_database_url.parse(
        _db_url,
        conn_max_age=600,
        conn_health_checks=True,
    )
    # Neon impose le SSL : on force sslmode=require si absent de l'URL
    DATABASES['default'].setdefault('OPTIONS', {})
    if not any(opt.startswith('sslmode') for opt in DATABASES['default']['OPTIONS']):
        DATABASES['default']['OPTIONS']['sslmode'] = 'require'
else:
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env_str('DB_NAME', 'ecommerce'),
        'USER': env_str('DB_USER', 'postgres'),
        'PASSWORD': env_str('DB_PASSWORD', 'change-me' if env_bool('DJANGO_DEBUG', False) else ''),
        'HOST': env_str('DB_HOST', 'localhost'),
        'PORT': env_str('DB_PORT', '5432'),
        'OPTIONS': {'sslmode': env_str('DB_SSLMODE', 'prefer')},
    }


# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------

LANGUAGE_CODE = 'fr-fr'

TIME_ZONE = 'Africa/Abidjan'

USE_I18N = True

USE_TZ = True


# ---------------------------------------------------------------------------
# Email – Gmail SMTP
# ---------------------------------------------------------------------------

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env_str('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = env_str('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER


# ---------------------------------------------------------------------------
# Static & media files
# ---------------------------------------------------------------------------

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Stockage des fichiers uploadés.
# - Local : disque (FileSystemStorage), comportement actuel.
# - Render/Neon : dans PostgreSQL via "dbfiles.storage.DatabaseFileStorage"
#   (le disque de Render est éphémère, il est effacé à chaque déploiement).
STORAGES = {
    'default': {
        'BACKEND': env_str(
            'DEFAULT_FILE_STORAGE',
            # Sur Render : fichiers dans la base (disque éphémère).
            # En local : disque, comportement actuel.
            'dbfiles.storage.DatabaseFileStorage' if os.environ.get('RENDER') else 'django.core.files.storage.FileSystemStorage',
        ),
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}

# Whitenoise : cache long pour les fichiers statiques et mediums
WHITENOISE_MAX_AGE = 31536000
WHITENOISE_SKIP_COMPRESS_EXTENSIONS = ()


# ---------------------------------------------------------------------------
# Logging – indispensable en production
# ---------------------------------------------------------------------------

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': env_str('DJANGO_LOG_LEVEL', 'INFO'),
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': env_str('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'Utilisateurs': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}


# ---------------------------------------------------------------------------
# Session security
# ---------------------------------------------------------------------------

SESSION_COOKIE_AGE = 60 * 60 * 24 * 7  # 1 semaine
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = False
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

LOGIN_URL = '/connexion/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
