"""
settings.py — منصة رفيق ADHD Learning System (Production Ready)
══════════════════════════════════════════════════════════
ملف .env المطلوب في جذر المشروع للتطوير المحلي فقط:
  SECRET_KEY, DEBUG, ALLOWED_HOSTS, DATABASE_URL,
  EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, HF_API_TOKEN, API_ENCRYPTION_KEY
"""

from pathlib import Path
import dj_database_url
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# تحميل ملف .env للتطوير المحلي فقط (بيئة Render تقرأ من الإعدادات مباشرة)
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / '.env')
except ImportError:
    pass

# ── الإعدادات الحساسة ────────────────────────────────────────
SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'django-insecure-change-me-before-production'
)

DEBUG = os.environ.get('DEBUG', 'True') == 'True'

# استقبال الهوستس ديناميكياً لتشمل سيرفرات Render والمحلي و ngrok
ALLOWED_HOSTS = os.environ.get(
    'ALLOWED_HOSTS', 
    'localhost,127.0.0.1,gigantic-dice-unheated.ngrok-free.dev,rafeeq-platform-tpne.onrender.com'
).split(',')

# إضافة دعم النطاقات الفرعية لـ Render لضمان القبول التلقائي
if '.onrender.com' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append('.onrender.com')

# ── التطبيقات ────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'learning',
    'accounts',
    'student_app',
    'parent_app',
    'admin_portal',
]

# ── Middleware ───────────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # إدارة الملفات الثابتة في الإنتاج
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Custom
    'accounts.middleware.LoginRateLimitMiddleware',
    'accounts.middleware.ProfileCompletionMiddleware',
    'accounts.middleware.SecurityHeadersMiddleware',
    'accounts.middleware.DisableBackCacheMiddleware',
]

ROOT_URLCONF = 'adhd_learning_system.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [os.path.join(BASE_DIR, 'templates')],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.debug',
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
    ]},
}]

WSGI_APPLICATION = 'adhd_learning_system.wsgi.application'

# ── قاعدة البيانات (PostgreSQL) ───────────────────────────────
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL', 'postgresql://postgres:@localhost:5432/ADHD_Learning_System'),
        conn_max_age=600,
        conn_health_checks=True,
    )
}
# التعديل: رفع مهلة الاتصال إلى 30 ثانية لتفادي الـ 502 الناتجة عن ضغط السيرفر
DATABASES['default']['OPTIONS'] = {'connect_timeout': 30}

# ── كلمات المرور ─────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ── الإعدادات الإقليمية ──────────────────────────────────────
LANGUAGE_CODE = 'ar'
TIME_ZONE     = 'Asia/Jerusalem'
USE_I18N      = True
USE_TZ        = True
APPEND_SLASH  = True

# ── الملفات الثابتة والوسائط ─────────────────────────────────
STATIC_URL       = 'static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT      = os.path.join(BASE_DIR, 'staticfiles')

# إعداد محرك تخزين وضغط ملفات الـ Static على بيئة الإنتاج لـ WhiteNoise
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ✅ إضافة دعم WhiteNoise لملفات الوسائط (MEDIA) لتمكين تحميل مرفقات VR
WHITENOISE_MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
WHITENOISE_MEDIA_PREFIX = '/media/'
WHITENOISE_MEDIA_FILES = True  # تفعيل خدمة ملفات الوسائط عبر WhiteNoise

MEDIA_URL        = '/media/'
MEDIA_ROOT       = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Cache — لـ Rate Limiting و Sessions ──────────────────────
CACHES = {
    'default': {
        'BACKEND':  'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'django_cache_table',
        'TIMEOUT':  300,
    }
}
AUTH_USER_MODEL    = 'learning.User'

# ── الجلسات ──────────────────────────────────────────────────
SESSION_COOKIE_AGE                 = 10800
SESSION_SAVE_EVERY_REQUEST         = True
SESSION_EXPIRE_AT_BROWSER_CLOSE    = False
SESSION_COOKIE_HTTPONLY            = True
SESSION_COOKIE_SAMESITE            = 'Lax'
SESSION_ENGINE = 'django.contrib.sessions.backends.db'

# ── CSRF ─────────────────────────────────────────────────────
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_TRUSTED_ORIGINS = [
    'https://gigantic-dice-unheated.ngrok-free.dev',
    'https://rafeeq-platform-tpne.onrender.com',
    'https://*.onrender.com'  # قبول أي رابط فرعي تولده منصة Render تلقائياً
]

# ── المصادقة ─────────────────────────────────────────────────
LOGIN_URL           = 'accounts:login'
LOGIN_REDIRECT_URL  = 'accounts:home'
LOGOUT_REDIRECT_URL = 'accounts:login'

# ── مفاتيح API ───────────────────────────────────────────────
HF_API_TOKEN       = os.environ.get('HF_API_TOKEN', '')
API_ENCRYPTION_KEY = os.environ.get('API_ENCRYPTION_KEY', '')

# ── البريد الإلكتروني ────────────────────────────────────────
EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST          = 'smtp.gmail.com'
EMAIL_PORT          = 587
EMAIL_USE_TLS       = True
EMAIL_HOST_USER     = os.environ.get('EMAIL_HOST_USER',     '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL  = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@edupal.com')

# ── إعدادات الأمان وسياسة الصلاحيات ───────────────────────────
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

SECURE_PERMISSIONS_POLICY = {
    "microphone": ["self"],
    "camera": ["self"],
    "display-capture": ["self"],
}

# تفعيل طبقات الحماية الصارمة تلقائياً فقط عندما يكون DEBUG = False في الإنتاج
if not DEBUG:
    SECURE_SSL_REDIRECT            = True
    SESSION_COOKIE_SECURE          = True
    CSRF_COOKIE_SECURE             = True
    SECURE_HSTS_SECONDS            = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD            = True
    SECURE_CONTENT_TYPE_NOSNIFF    = True
    X_FRAME_OPTIONS                = 'SAMEORIGIN'
    SECURE_BROWSER_XSS_FILTER       = True
    SECURE_REFERRER_POLICY         = "no-referrer-when-downgrade"

# ── إخفاء SessionInterrupted من الـ logs ─────────────────────
import logging as _logging

class _IgnoreSessionInterrupted(_logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        return ('SessionInterrupted' not in msg and
                'session was deleted before' not in msg)

_logging.getLogger('django.request').addFilter(_IgnoreSessionInterrupted())

# ── Azure Speech Service ───────────────────────────────────────
AZURE_SPEECH_KEY = os.environ.get('AZURE_SPEECH_KEY', '')
AZURE_SPEECH_REGION = os.environ.get('AZURE_SPEECH_REGION', 'eastus')

# ── Logging ──────────────────────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {'verbose': {'format': '%(levelname)s %(asctime)s %(module)s %(message)s'}},
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'verbose'},
    },
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'WARNING'},
        'accounts': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
        'learning': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
    },
}