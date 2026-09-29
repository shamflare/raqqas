"""
النماذج الأساسية — أهمّها AppConfig: النسخة الواحدة التي تتحكّم بكل شيء.

قاعدة plan2 §4.2: أي شيء يريد الأدمن تغييره لاحقًا يمرّ من هنا ولا يُكتب في الكود.
"""

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from . import defaults, money

CONFIG_CACHE_KEY = "app_config:v1"
CONFIG_CACHE_TTL = 300


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField("أُنشئ في", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("عُدّل في", auto_now=True)

    class Meta:
        abstract = True


class TranslatedNameModel(models.Model):
    """
    كل ما يكتبه الأدمن يُخزَّن بثلاث لغات (plan2 §8.5).
    العربية إلزامية — والباقي يقع عليها عند الفراغ.
    """

    name_ar = models.CharField("الاسم (عربي)", max_length=120)
    name_tr = models.CharField("الاسم (تركي)", max_length=120, blank=True)
    name_en = models.CharField("الاسم (إنكليزي)", max_length=120, blank=True)

    class Meta:
        abstract = True

    def name_for(self, lang: str) -> str:
        return getattr(self, f"name_{lang}", "") or self.name_ar

    def __str__(self) -> str:
        return self.name_ar


class AppConfig(TimeStampedModel):
    """
    نسخة واحدة (singleton) — id ثابت على 1.
    كل حفظ يرفع `version`، والتطبيق يقارن الرقم ليعرف أن عليه تحديث نسخته المخزّنة.
    """

    SHADOWS = [(s, s) for s in defaults.SHADOW_PRESETS]
    DENSITIES = [(d, d) for d in defaults.DENSITY_PRESETS]
    REVIEW_MODES = [
        ("all", "مراجعة كل إعلان"),
        ("new_users", "مراجعة إعلانات الأعضاء الجدد فقط"),
        ("off", "نشر فوري بلا مراجعة"),
    ]

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    version = models.PositiveIntegerField("رقم النسخة", default=1, editable=False)

    # ---------------- الهوية
    app_name_ar = models.CharField("اسم التطبيق (عربي)", max_length=40, default="سوق الرقة")
    app_name_tr = models.CharField("اسم التطبيق (تركي)", max_length=40, blank=True)
    app_name_en = models.CharField("اسم التطبيق (إنكليزي)", max_length=40, blank=True)
    brand_mark = models.CharField(
        "حرف العلامة", max_length=4, default="س",
        help_text="يظهر داخل المربّع حين لا يوجد شعار مرفوع",
    )
    logo = models.ImageField(
        "شعار التطبيق", upload_to="brand/", blank=True, null=True,
        help_text="يظهر في ترويسة التطبيق فورًا بلا إعادة بناء",
    )
    launcher_icon = models.ImageField(
        "أيقونة الجوال", upload_to="brand/", blank=True, null=True,
        help_text=(
            "أيقونة الشاشة الرئيسية للجوال. تُحفظ هنا وتُطبَّق عند بناء نسخة APK "
            "التالية — أندرويد لا يسمح بتغييرها على جهاز مثبَّت"
        ),
    )

    # ---------------- التصميم
    theme_light = models.JSONField("ألوان الوضع النهاري", default=dict, blank=True)
    theme_dark = models.JSONField("ألوان الوضع الليلي", default=dict, blank=True)
    font_family = models.CharField("الخط", max_length=64, default="Cairo")
    font_scale = models.FloatField(
        "مقياس الخط", default=1.0,
        validators=[MinValueValidator(0.85), MaxValueValidator(1.3)],
    )
    radius = models.JSONField("الاستدارة", default=dict, blank=True)
    shadows = models.CharField("الظلال", max_length=12, choices=SHADOWS, default="soft")
    density = models.CharField("الكثافة", max_length=12, choices=DENSITIES, default="normal")
    dark_mode_enabled = models.BooleanField("تفعيل الوضع الليلي", default=True)

    # ---------------- العملات (تعديل جوهري على plan2 §6)
    #
    # لم يعد هناك «عملة واحدة للمتجر». البائع يختار عملة إعلانه فيُحفظ رقمه
    # كما كتبه، والمشتري يختار العملة التي يقرأ بها، والأدمن يضع بينهما جسر
    # التحويل فقط: «1 دولار = كم». التفصيل في apps/core/money.py.
    base_currency = models.CharField(
        "عملة المحور", max_length=3, default="USD", editable=False,
        help_text="كل أسعار الصرف تُكتب بصيغة «1 دولار = كم» — والمحور لا يُبدَّل",
    )
    default_currency = models.CharField(
        "العملة الافتراضية للعرض", max_length=3, default="USD",
        help_text="ما يقرأ به المستخدم قبل أن يختار عملته",
    )
    enabled_currencies = models.JSONField(
        "العملات المتاحة", default=list, blank=True,
        help_text="ما يظهر في قائمة العملات — فارغة تعني كل عملات الكتالوج",
    )
    rates = models.JSONField(
        "أسعار الصرف", default=dict, blank=True,
        help_text="«1 دولار = كم» لكل عملة. فارغ يعني: لا يُعرض تحويل تقريبي إطلاقًا",
    )
    rates_updated_at = models.DateTimeField("آخر تحديث للأسعار", null=True, blank=True)

    # ---------------- اللغات
    default_language = models.CharField("اللغة الافتراضية", max_length=2, default="ar")
    supported_languages = models.JSONField("اللغات المدعومة", default=list, blank=True)

    # ---------------- الصفحة التعريفية
    landing_ar = models.JSONField("الصفحة التعريفية (عربي)", default=dict, blank=True)
    landing_tr = models.JSONField("الصفحة التعريفية (تركي)", default=dict, blank=True)
    landing_en = models.JSONField("الصفحة التعريفية (إنكليزي)", default=dict, blank=True)
    landing_image = models.ImageField(
        "صورة الصفحة التعريفية", upload_to="landing/", blank=True, null=True
    )

    # ---------------- التطبيق والتوزيع (plan2 §7.2)
    store_url = models.URLField(
        "رابط المتجر", blank=True,
        help_text="صفحة التطبيق على Google Play — يستعملها التطبيق للتحديث والمشاركة",
    )
    apk_url = models.URLField("رابط ملف APK", blank=True)
    apk_sha256 = models.CharField("بصمة الملف", max_length=64, blank=True)
    apk_size_mb = models.FloatField("حجم الملف (ميغا)", default=0)
    latest_version = models.CharField("آخر إصدار", max_length=16, default="1.0.0")
    min_version = models.CharField("أدنى إصدار مسموح", max_length=16, default="1.0.0")
    update_message_ar = models.CharField("رسالة التحديث (عربي)", max_length=200, blank=True)
    update_message_tr = models.CharField("رسالة التحديث (تركي)", max_length=200, blank=True)
    update_message_en = models.CharField("رسالة التحديث (إنكليزي)", max_length=200, blank=True)

    # ---------------- المزايا والحدود
    features = models.JSONField("المزايا", default=dict, blank=True)
    review_mode = models.CharField(
        "نمط المراجعة", max_length=12, choices=REVIEW_MODES, default="all"
    )
    review_threshold = models.PositiveSmallIntegerField(
        "عدد الإعلانات المقبولة قبل الثقة", default=3,
        help_text="يُستخدم مع نمط «الأعضاء الجدد فقط» (plan2 §8.6)",
    )
    listing_expiry_days = models.PositiveSmallIntegerField("مدة صلاحية الإعلان (يوم)", default=60)
    daily_listing_limit = models.PositiveSmallIntegerField("حد الإعلانات اليومي", default=5)
    max_photos_per_listing = models.PositiveSmallIntegerField("أقصى عدد صور", default=10)
    max_video_seconds = models.PositiveSmallIntegerField(
        "أقصى مدة للفيديو (ثانية)", default=60,
        help_text="فيديو واحد لكل إعلان. صفر = إيقاف رفع الفيديو",
    )
    max_video_mb = models.PositiveSmallIntegerField(
        "أقصى حجم للفيديو (ميغابايت)", default=100,
        help_text="حجم الملف كما يرفعه الجوال، قبل ضغطه على الخادم",
    )

    # ---------------- التواصل
    support_whatsapp = models.CharField("واتساب الدعم", max_length=24, blank=True)
    support_email = models.EmailField("بريد الدعم", blank=True)

    updated_by = models.ForeignKey(
        "accounts.User", verbose_name="آخر من عدّل",
        null=True, blank=True, on_delete=models.SET_NULL, related_name="config_updates",
    )

    class Meta:
        verbose_name = "إعدادات التطبيق"
        verbose_name_plural = "إعدادات التطبيق"

    def __str__(self) -> str:
        return f"إعدادات التطبيق (نسخة {self.version})"

    # ------------------------------------------------------------------

    def save(self, *args, **kwargs):
        self.pk = 1
        if not self.theme_light:
            self.theme_light = dict(defaults.DEFAULT_THEME_LIGHT)
        if not self.theme_dark:
            self.theme_dark = dict(defaults.DEFAULT_THEME_DARK)
        if not self.radius:
            self.radius = dict(defaults.DEFAULT_RADIUS)
        if not self.features:
            self.features = dict(defaults.DEFAULT_FEATURES)
        if not self.supported_languages:
            self.supported_languages = ["ar", "tr", "en"]
        if not self.landing_ar:
            self.landing_ar = defaults.default_landing("ar")
        if not self.landing_tr:
            self.landing_tr = defaults.default_landing("tr")
        if not self.landing_en:
            self.landing_en = defaults.default_landing("en")

        # العملات: نضمن سلامة المحفوظ هنا لا في الواجهة وحدها. قيمة تالفة في
        # `rates` تعني سعرًا خاطئًا على شاشة كل مستخدم — وهذا أسوأ بكثير من
        # رفض الحفظ أو تجاهل قيمة واحدة.
        self.rates = money.clean_rates(self.rates)
        allowed = [c for c in (self.enabled_currencies or []) if money.is_valid(c)]
        self.enabled_currencies = allowed or list(money.CURRENCY_CODES)
        if not money.is_valid(self.default_currency):
            self.default_currency = money.BASE_CURRENCY
        if self.default_currency not in self.enabled_currencies:
            self.enabled_currencies.append(self.default_currency)
        self.base_currency = money.BASE_CURRENCY

        # لا نرفع النسخة إلا عند تعديل فعلي بعد الإنشاء
        if self.pk and AppConfig.objects.filter(pk=1).exists():
            self.version = models.F("version") + 1

        super().save(*args, **kwargs)
        self.refresh_from_db(fields=["version"])
        cache.delete(CONFIG_CACHE_KEY)

    def clean(self):
        if self.default_language not in (self.supported_languages or ["ar"]):
            raise ValidationError(
                {"default_language": "اللغة الافتراضية يجب أن تكون ضمن اللغات المدعومة."}
            )
        for code in self.enabled_currencies or []:
            if not money.is_valid(code):
                raise ValidationError({"enabled_currencies": f"عملة غير معروفة: {code}"})

    # ------------------------------------------------------------------

    @classmethod
    def get_solo(cls) -> "AppConfig":
        config = cache.get(CONFIG_CACHE_KEY)
        if config is None:
            config, _ = cls.objects.get_or_create(pk=1)
            cache.set(CONFIG_CACHE_KEY, config, CONFIG_CACHE_TTL)
        return config

    def feature(self, key: str, fallback=False):
        return (self.features or {}).get(key, defaults.DEFAULT_FEATURES.get(key, fallback))

    @property
    def rate_table(self) -> dict:
        """جدول التحويل الكامل — يشمل المحور نفسه (1 دولار = 1 دولار)."""
        return money.full_rates(self.rates)

    @property
    def has_rates(self) -> bool:
        """هل وضع الأدمن سعرًا واحدًا على الأقل؟ بلا ذلك لا نعرض أي تحويل."""
        return bool(money.clean_rates(self.rates))

    def currency_for(self, requested: str | None) -> str:
        """
        العملة التي يُعرض بها لهذا الطلب.

        نرفض ما ليس في القائمة المتاحة بدل أن نصدّقه: قيمة قادمة من العميل
        تصل إلى حساب مالي، ولا يُبنى حساب على مدخل غير مفحوص.
        """
        allowed = self.enabled_currencies or list(money.CURRENCY_CODES)
        if requested and requested in allowed:
            return requested
        return self.default_currency if self.default_currency in allowed else allowed[0]

    def landing_for(self, lang: str) -> dict:
        return getattr(self, f"landing_{lang}", None) or self.landing_ar or {}

    def update_message_for(self, lang: str) -> str:
        return getattr(self, f"update_message_{lang}", "") or self.update_message_ar

    def app_name_for(self, lang: str) -> str:
        return getattr(self, f"app_name_{lang}", "") or self.app_name_ar


class AdminLog(models.Model):
    """سجلّ إجراءات الإدارة — من فعل ماذا ومتى (plan2 §8.5)."""

    ACTIONS = [
        ("approve", "قبول إعلان"),
        ("reject", "رفض إعلان"),
        ("suspend", "إيقاف إعلان"),
        ("delete", "حذف إعلان"),
        ("feature", "تمييز إعلان"),
        ("user_suspend", "إيقاف مستخدم"),
        ("user_ban", "حظر مستخدم"),
        ("user_activate", "تفعيل مستخدم"),
        ("user_auto_publish", "تبديل النشر التلقائي"),
        ("user_password", "تعيين كلمة مرور لمستخدم"),
        ("config", "تعديل الإعدادات"),
        ("report_resolve", "معالجة بلاغ"),
        ("account_deleted", "حذف حساب بطلب صاحبه"),
    ]

    actor = models.ForeignKey(
        "accounts.User", verbose_name="المنفّذ",
        null=True, on_delete=models.SET_NULL, related_name="admin_logs",
    )
    action = models.CharField("الإجراء", max_length=24, choices=ACTIONS, db_index=True)
    target_type = models.CharField("نوع الهدف", max_length=32, blank=True)
    target_id = models.PositiveIntegerField("رقم الهدف", null=True, blank=True)
    note = models.TextField("ملاحظة", blank=True)
    meta = models.JSONField("تفاصيل", default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "سجلّ إدارة"
        verbose_name_plural = "سجلّ الإدارة"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["target_type", "target_id"])]

    def __str__(self) -> str:
        return f"{self.get_action_display()} — {self.target_type}#{self.target_id}"

    @classmethod
    def record(cls, actor, action, target=None, note="", **meta):
        return cls.objects.create(
            actor=actor if getattr(actor, "is_authenticated", False) else None,
            action=action,
            target_type=target.__class__.__name__.lower() if target else "",
            target_id=getattr(target, "pk", None),
            note=note,
            meta=meta,
        )


class DownloadEvent(models.Model):
    """عدّاد تنزيلات APK — بديلنا عن إحصاءات المتجر (plan2 §7.2)."""

    version = models.CharField(max_length=16, blank=True)
    source = models.CharField(max_length=32, blank=True, help_text="landing | qr | share")
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "تنزيل"
        verbose_name_plural = "التنزيلات"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"تنزيل {self.version} — {self.created_at:%Y-%m-%d}"


def now():
    return timezone.now()


# نموذج التحديث عن بُعد يعيش في ملف مستقل — نستورده هنا ليكتشفه Django
from .updates import OtaUpdate  # noqa: E402,F401
