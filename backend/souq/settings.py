"""
سوق الرقة — إعدادات Django

التطوير المحلي:  يعمل على SQLite بلا أي إعداد (شغّل migrate وانتهى).
الإنتاج:         ضع DATABASE_URL لـ PostgreSQL في ملف .env  (قرار plan2 §7).
"""

from datetime import timedelta
from pathlib import Path
import os
import sys

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# تُتيح استيراد التطبيقات كـ apps.core بدل المسار الكامل
sys.path.insert(0, str(BASE_DIR))

load_dotenv(BASE_DIR / ".env")


def env_bool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(key: str, default: str = "") -> list[str]:
    return [v.strip() for v in os.getenv(key, default).split(",") if v.strip()]


# ---------------------------------------------------------------- الأساسيات

SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-insecure-key-change-me-in-production")
DEBUG = env_bool("DEBUG", True)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0,10.0.2.2")

# رابط الواجهة العامة — يُستخدم في روابط المشاركة داخل رسائل واتساب
PUBLIC_SITE_URL = os.getenv("PUBLIC_SITE_URL", "http://localhost:3000").rstrip("/")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # طرف ثالث
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    # تطبيقاتنا
    "apps.core",
    "apps.accounts",
    "apps.catalog",
    "apps.listings",
    "apps.messaging",
    "apps.notifications",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.LanguageMiddleware",
]

ROOT_URLCONF = "souq.urls"
WSGI_APPLICATION = "souq.wsgi.application"
ASGI_APPLICATION = "souq.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------------------------------------------- قاعدة البيانات

DATABASES = {
    "default": dj_database_url.config(
        default=os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 6}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------- اللغة والوقت

LANGUAGE_CODE = "ar"
TIME_ZONE = os.getenv("TIME_ZONE", "Asia/Damascus")
USE_I18N = True
USE_TZ = True

# اللغات الثلاث المعتمدة (plan2 §5) — الترتيب يحدّد لاحقة الحقول: name_ar / name_tr / name_en
SUPPORTED_LANGUAGES = ["ar", "tr", "en"]
DEFAULT_LANGUAGE = "ar"

# ---------------------------------------------------------------- الملفات

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", BASE_DIR / "media"))

# حدود الصور — الإنترنت في الرقة ضعيف (plan2 §7)
IMAGE_MAX_UPLOAD_BYTES = int(os.getenv("IMAGE_MAX_UPLOAD_BYTES", 12 * 1024 * 1024))
IMAGE_MAX_EDGE = 1600      # أطول ضلع للصورة الكاملة
IMAGE_THUMB_EDGE = 480     # أطول ضلع للمصغّرة
IMAGE_QUALITY = 82

DATA_UPLOAD_MAX_MEMORY_SIZE = IMAGE_MAX_UPLOAD_BYTES
FILE_UPLOAD_MAX_MEMORY_SIZE = IMAGE_MAX_UPLOAD_BYTES

# مسار ffmpeg لضغط الفيديو. فارغ = ffmpeg النظام إن وُجد، وإلا نسخة imageio-ffmpeg
FFMPEG_BINARY = os.getenv("FFMPEG_BINARY", "")

# ---------------------------------------------------------------- DRF

REST_FRAMEWORK = {
    # ليست JWTAuthentication المجرّدة: نسختنا تُبطل الرموز الصادرة قبل آخر
    # تغيير لكلمة المرور، وإلا بقي السارق داخلًا تسعين يومًا بعد الاستعادة.
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.accounts.tokens.SouqJWTAuthentication",
    ),
    # القاعدة الأساسية: القراءة مفتوحة للزائر، والكتابة تحتاج تسجيلًا (plan2 §11 / قرار 17)
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ),
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.DefaultPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
    # لا محدِّد افتراضي: كل عرض يعلن محدِّده صراحةً (apps.core.throttling).
    # كان هنا `ScopedRateThrottle` وهي لا تحدّ شيئًا ما لم يحمل العرض
    # `throttle_scope` — فكانت حمايةً موهومة. التفاصيل في core/throttling.py.
    "DEFAULT_THROTTLE_RATES": {
        "auth": "20/hour",          # تسجيل الدخول والتسجيل
        "contact": "60/hour",       # كشف رقم البائع
        "write": "120/hour",        # النشر والتعديل
        "report": "10/hour",        # البلاغات
        "reset": "10/hour",         # طلب رمز استعادة — والحدّ الفعلي في الجدول
    },
}

SIMPLE_JWT = {
    # عمر طويل نسبيًا — الإنترنت متقطّع ولا نريد إخراج الناس كل ساعة
    "ACCESS_TOKEN_LIFETIME": timedelta(days=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=90),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "سوق الرقة — API",
    "DESCRIPTION": "واجهة برمجة التطبيق للتطبيق المحمول ولوحة الإدارة.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

# ---------------------------------------------------------------- CORS

CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8081,http://localhost:19006",
)
CORS_ALLOW_CREDENTIALS = False
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "http://localhost:3000")

# ---------------------------------------------------------------- الأمان (إنتاج)

if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_CONTENT_TYPE_NOSNIFF = True

# ---------------------------------------------------------------- التخزين المؤقت

CACHES = {
    "default": {
        "BACKEND": os.getenv(
            "CACHE_BACKEND", "django.core.cache.backends.locmem.LocMemCache"
        ),
        "LOCATION": os.getenv("CACHE_LOCATION", "souq-local"),
    }
}

# أثناء الاختبارات: بلا تخزين مؤقّت.
# AppConfig نسخة واحدة مخزّنة في الذاكرة، وهي تعيش أطول من تراجع المعاملة (rollback)
# بين الاختبارات فتتسرّب حالة اختبار إلى الذي يليه.
if "test" in sys.argv:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}

# ---------------------------------------------------------------- الإشعارات (FCM)

FCM_SERVER_KEY = os.getenv("FCM_SERVER_KEY", "")

# ---------------------------------------------------------------- واتساب (رموز الاستعادة)

# bot = خدمة Node محلية (deploy/wa-bot) · cloud = Meta الرسمي · log = السجلّ فقط.
# الافتراضي `log` عمدًا: خادم بلا إعداد يجب ألّا يدّعي أنه يرسل.
# التفاصيل والتحذيرات في deploy/WHATSAPP.md.
WHATSAPP_PROVIDER = os.getenv("WHATSAPP_PROVIDER", "log")

# الخدمة الجانبية — على 127.0.0.1 وحدها، فلا منفذ مكشوف على الإنترنت
WHATSAPP_BOT_URL = os.getenv("WHATSAPP_BOT_URL", "http://127.0.0.1:8787")
WHATSAPP_BOT_TOKEN = os.getenv("WHATSAPP_BOT_TOKEN", "")

# Meta WhatsApp Cloud API — جاهز للتبديل بلا تعديل كود
WHATSAPP_CLOUD_TOKEN = os.getenv("WHATSAPP_CLOUD_TOKEN", "")
WHATSAPP_CLOUD_PHONE_ID = os.getenv("WHATSAPP_CLOUD_PHONE_ID", "")
WHATSAPP_CLOUD_TEMPLATE = os.getenv("WHATSAPP_CLOUD_TEMPLATE", "password_reset")
WHATSAPP_CLOUD_TEMPLATE_LANG = os.getenv("WHATSAPP_CLOUD_TEMPLATE_LANG", "ar")

# ---------------------------------------------------------------- السجلات

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "{levelname} {asctime} {name} — {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
}
