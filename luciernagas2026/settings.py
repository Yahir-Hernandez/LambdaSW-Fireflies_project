from pathlib import Path
import environ

env = environ.Env()


BASE_DIR = Path(__file__).resolve().parent.parent
environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY = env('SECRET_KEY', default='django-insecure-local-dev-key')

DEBUG = env.bool('DEBUG', default=False)

ALLOWED_HOSTS = env.list(
    'ALLOWED_HOSTS',
    default=['localhost', '127.0.0.1', '[::1]'],
)
RENDER_EXTERNAL_HOSTNAME = env('RENDER_EXTERNAL_HOSTNAME', default='')
if RENDER_EXTERNAL_HOSTNAME and RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[])
if RENDER_EXTERNAL_HOSTNAME:
    render_origin = f"https://{RENDER_EXTERNAL_HOSTNAME}"
    if render_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(render_origin)

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

LOGIN_URL = "sistema_app:login"
LOGIN_REDIRECT_URL = "sistema_app:home"

LANGUAGE_CODE = 'es-mx'
TIME_ZONE = 'America/Mexico_City'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'sistema_app',
    'crispy_forms',
    'crispy_bootstrap5',
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

ROOT_URLCONF = 'luciernagas2026.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'sistema_app' / 'templates'],
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

WSGI_APPLICATION = 'luciernagas2026.wsgi.application'

DATABASE_URL = env('DATABASE_URL', default='')
if DATABASE_URL:
    DATABASES = {
        'default': env.db('DATABASE_URL'),
    }
    DATABASES['default']['CONN_MAX_AGE'] = env.int('DATABASE_CONN_MAX_AGE', default=600)
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
    {'NAME': 'sistema_app.validators.UppercaseValidator'},
    {'NAME': 'sistema_app.validators.LowercaseValidator'},
    {'NAME': 'sistema_app.validators.NumberValidator'},
    {'NAME': 'sistema_app.validators.SpecialCharValidator'},
]

SESSION_COOKIE_AGE = 1800
SESSION_SAVE_EVERY_REQUEST = True

USE_I18N = True

USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
WHITENOISE_MANIFEST_STRICT = env.bool('WHITENOISE_MANIFEST_STRICT', default=False)
USE_WHITENOISE_STORAGE = env.bool(
    'USE_WHITENOISE_STORAGE',
    default=env.bool('RENDER', default=False),
)

if USE_WHITENOISE_STORAGE:
    STORAGES = {
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }

EMAIL_BACKEND = env(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.filebased.EmailBackend',
)
EMAIL_FILE_PATH = env('EMAIL_FILE_PATH', default=str(BASE_DIR / 'sent_emails'))
DEFAULT_FROM_EMAIL = env(
    'DEFAULT_FROM_EMAIL',
    default='noreply@luciernagas2026.mx',
)

EMAIL_HOST          = env('EMAIL_HOST',          default='smtp.gmail.com')
EMAIL_PORT          = env.int('EMAIL_PORT',      default=587)
EMAIL_USE_TLS       = env.bool('EMAIL_USE_TLS',  default=True)
EMAIL_HOST_USER     = env('EMAIL_HOST_USER',     default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')

SENDGRID_API_KEY = env('SENDGRID_API_KEY', default='')
SENDGRID_API_URL = env(
    'SENDGRID_API_URL',
    default='https://api.sendgrid.com/v3/mail/send',
)
SENDGRID_TIMEOUT = env.int('SENDGRID_TIMEOUT', default=10)
SENDGRID_SANDBOX_MODE = env.bool('SENDGRID_SANDBOX_MODE', default=False)

EMAIL_IMAGE_MODE = env('EMAIL_IMAGE_MODE', default='inline')

SITE_URL = env(
    'SITE_URL',
    default=env('RENDER_EXTERNAL_URL', default='http://localhost:8000'),
)

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(name)s %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'sistema_app': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
