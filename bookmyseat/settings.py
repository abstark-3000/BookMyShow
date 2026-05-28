from pathlib import Path
import os
import dj_database_url
from dotenv import load_dotenv

# Load environment variables first before anything else
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ==============================================================================
# SECURITY CONFIGURATION
# ==============================================================================
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-fallback-key')
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = ['*']

CSRF_TRUSTED_ORIGINS = [
    'https://*.ngrok-free.dev',
    'https://*.onrender.com',
]

# ==============================================================================
# APPLICATIONS CONFIGURATION
# ==============================================================================
INSTALLED_APPS = [
    'cloudinary_storage',   # 1. This MUST go first to override static/media backends
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'cloudinary',           # 2. Placed right under staticfiles
    'users',
    'movies',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'bookmyseat.urls'
LOGIN_URL = '/login/'
WSGI_APPLICATION = 'bookmyseat.wsgi.application'

# ==============================================================================
# TEMPLATE ENGINE
# ==============================================================================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# ==============================================================================
# DATABASE CONFIGURATION (Aiven PostgreSQL / SQLite Local Fallback)
# ==============================================================================
DATABASES = {
    'default': dj_database_url.config(
        default=f'sqlite:///{BASE_DIR}/db.sqlite3',
        conn_max_age=600
    )
}

# ==============================================================================
# PASSWORD VALIDATION
# ==============================================================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ==============================================================================
# INTERNATIONALIZATION
# ==============================================================================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ==============================================================================
# STATIC & MEDIA FILE MANAGEMENT (WhiteNoise & Cloudinary)
# ==============================================================================
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.environ.get('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': os.environ.get('CLOUDINARY_API_KEY'),
    'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET'),
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==============================================================================
# REDIS AND CELERY INTEGRATION
# ==============================================================================
RAW_REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

if RAW_REDIS_URL.startswith('rediss://') and 'ssl_cert_reqs' not in RAW_REDIS_URL:
    separator = '&' if '?' in RAW_REDIS_URL else '?'
    REDIS_URL = f"{RAW_REDIS_URL}{separator}ssl_cert_reqs=none"
else:
    REDIS_URL = RAW_REDIS_URL

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = None
CELERY_IGNORE_RESULT = True
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

# 🟢 ADD THIS BLOCK: Tells Celery to safely bypass strict SSL locally
if REDIS_URL.startswith('rediss://'):
    CELERY_BROKER_USE_SSL = {
        'ssl_cert_reqs': 0  # 0 corresponds to CERT_NONE / bypass validation
    }

CELERY_BEAT_SCHEDULE = {
    'release-expired-reservations': {
        'task': 'movies.tasks.release_expired_reservations',
        'schedule': 60.0,
    },
}

# Production Cache Configuration supporting Secure Cloud TLS Connection Strings
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
        'TIMEOUT': 300,
        'OPTIONS': {
            'CONNECTION_POOL_KWARGS': {
                'ssl_cert_reqs': None  # Bypasses strict SSL validation errors for the cache engine
            }
        }
    }
}

# ==============================================================================
# EMAIL SYSTEM CONFIGURATION
# ==============================================================================
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = os.environ.get('EMAIL_HOST_USER')

# ==============================================================================
# RAZORPAY GATEWAY CREDS
# ==============================================================================
RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET')
RAZORPAY_WEBHOOK_SECRET = os.environ.get('RAZORPAY_WEBHOOK_SECRET', 'anyrandomstring')

SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# ==============================================================================
# LOGGING (Using dynamic BASE_DIR path to allow Render execution writes)
# ==============================================================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'email_errors.log'),
        },
    },
    'loggers': {
        'movies.tasks': {
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': True,
        },
    },
}