"""تسلسل إعدادات التطبيق — الشكل المتفق عليه في plan2 §4.2."""

from rest_framework import serializers

from . import defaults, money
from .models import AppConfig, DownloadEvent


class AppConfigSerializer(serializers.ModelSerializer):
    """
    الرد العام الذي يطلبه التطبيق عند كل إقلاع.
    مبنيّ متداخلًا لأن التطبيق يمرّره كما هو إلى ThemeProvider.
    """

    brand = serializers.SerializerMethodField()
    theme = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    languages = serializers.SerializerMethodField()
    landing = serializers.SerializerMethodField()
    app = serializers.SerializerMethodField()
    features = serializers.SerializerMethodField()
    limits = serializers.SerializerMethodField()
    support = serializers.SerializerMethodField()
    legal = serializers.SerializerMethodField()

    class Meta:
        model = AppConfig
        fields = [
            "version", "brand", "theme", "currency", "languages",
            "landing", "app", "features", "limits", "support", "legal",
        ]

    # ------------------------------------------------------------------

    def get_brand(self, obj: AppConfig) -> dict:
        """
        الاسم والشعار.

        `names` بالثلاث لغات لأن الصفحة التعريفية تعرض الثلاث في صفحة واحدة،
        بينما التطبيق يكتفي بـ `name` بلغة الطلب.
        """
        return {
            "name": obj.app_name_for(self._lang()),
            "names": {
                "ar": obj.app_name_ar,
                "tr": obj.app_name_tr or obj.app_name_ar,
                "en": obj.app_name_en or obj.app_name_ar,
            },
            "mark": obj.brand_mark,
            "logo": self._media_url(obj.logo),
            # للعرض في اللوحة فقط — الجوال لا يستطيع تبديل أيقونته بلا بناء جديد
            "launcher_icon": self._media_url(obj.launcher_icon),
        }

    def _media_url(self, field) -> str | None:
        if not field:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(field.url) if request else field.url

    def get_theme(self, obj: AppConfig) -> dict:
        return {
            "light": {**defaults.DEFAULT_THEME_LIGHT, **(obj.theme_light or {})},
            "dark": {**defaults.DEFAULT_THEME_DARK, **(obj.theme_dark or {})},
            "font": {"family": obj.font_family, "scale": obj.font_scale},
            "radius": {**defaults.DEFAULT_RADIUS, **(obj.radius or {})},
            "shadows": obj.shadows,
            "density": obj.density,
            "darkModeEnabled": obj.dark_mode_enabled,
        }

    def get_currency(self, obj: AppConfig) -> dict:
        """
        كل ما يحتاجه العميل ليعرض أي سعر بأي عملة — **بلا طلب إضافي**.

        نرسل الكتالوج وجدول الأسعار كاملين ليجري التطبيق التحويل عنده. البديل
        (تحويل على الخادم) كان يعني إعادة تحميل كل قائمة عند كل تبديل عملة،
        على إنترنت ضعيف، مقابل ضربَي قسمة يقوم بهما الجوال في أقل من مللي ثانية.
        """
        lang = self._lang()
        enabled = obj.enabled_currencies or list(money.CURRENCY_CODES)
        return {
            "base": obj.base_currency,
            "default": obj.default_currency,
            "enabled": enabled,
            "catalogue": [c for c in money.catalogue(lang) if c["code"] in enabled],
            # جدول فارغ = لم يضبط الأدمن الأسعار بعد ⇒ لا يُعرض أي تحويل تقريبي
            "rates": money.clean_rates(obj.rates),
            "rates_updated_at": obj.rates_updated_at,
        }

    def get_languages(self, obj: AppConfig) -> dict:
        return {
            "supported": obj.supported_languages or ["ar", "tr", "en"],
            "default": obj.default_language,
            "rtl": ["ar"],
        }

    def get_landing(self, obj: AppConfig) -> dict:
        request = self.context.get("request")
        image = None
        if obj.landing_image:
            image = obj.landing_image.url
            if request is not None:
                image = request.build_absolute_uri(image)
        return {
            "ar": obj.landing_ar,
            "tr": obj.landing_tr,
            "en": obj.landing_en,
            "image": image,
        }

    def get_app(self, obj: AppConfig) -> dict:
        lang = self._lang()
        return {
            "latest_version": obj.latest_version,
            "min_version": obj.min_version,
            "store_url": obj.store_url,
            "apk_url": obj.apk_url,
            "apk_sha256": obj.apk_sha256,
            "apk_size_mb": obj.apk_size_mb,
            "update_message": obj.update_message_for(lang),
        }

    def get_features(self, obj: AppConfig) -> dict:
        return {**defaults.DEFAULT_FEATURES, **(obj.features or {})}

    def get_limits(self, obj: AppConfig) -> dict:
        return {
            "listing_expiry_days": obj.listing_expiry_days,
            "daily_listing_limit": obj.daily_listing_limit,
            "max_photos_per_listing": obj.max_photos_per_listing,
            "max_video_seconds": obj.max_video_seconds,
            "max_video_mb": obj.max_video_mb,
            "min_description_length": defaults.DEFAULT_LIMITS["min_description_length"],
        }

    def get_support(self, obj: AppConfig) -> dict:
        return {"whatsapp": obj.support_whatsapp, "email": obj.support_email}

    def get_legal(self, obj: AppConfig) -> dict:
        """
        روابط الوثائق القانونية.

        Google Play يشترط أن يصل المستخدم إلى سياسة الخصوصية وإلى طريقة حذف
        حسابه **من داخل التطبيق** لا من المتجر فقط. نبنيها من عنوان الطلب
        نفسه فلا تحتاج ضبطًا يدويًا ولا تتعطّل إن تغيّر النطاق.
        """
        request = self.context.get("request")
        paths = {
            "privacy": "/privacy",
            "terms": "/terms",
            "delete_account": "/delete-account",
        }
        if request is None:
            return paths
        return {key: request.build_absolute_uri(path) for key, path in paths.items()}

    def _lang(self) -> str:
        request = self.context.get("request")
        return getattr(request, "lang", "ar")


HEX_RE = r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"


class ThemeMapField(serializers.DictField):
    """يقبل خريطة {مفتاح: لون} ويتحقّق أن كل قيمة لون HEX صالح."""

    def to_internal_value(self, data):
        import re

        value = super().to_internal_value(data)
        unknown = set(value) - set(defaults.DEFAULT_THEME_LIGHT)
        if unknown:
            raise serializers.ValidationError(
                f"مفاتيح غير معروفة: {', '.join(sorted(unknown))}"
            )
        for key, color in value.items():
            if not isinstance(color, str) or not re.match(HEX_RE, color):
                raise serializers.ValidationError(
                    {key: "القيمة يجب أن تكون لونًا بصيغة #RRGGBB."}
                )
        return value


class AppConfigWriteSerializer(serializers.ModelSerializer):
    """التعديل من لوحة الإدارة — حقول مسطّحة وتحقّق صارم."""

    theme_light = ThemeMapField(required=False)
    theme_dark = ThemeMapField(required=False)

    class Meta:
        model = AppConfig
        fields = [
            "app_name_ar", "app_name_tr", "app_name_en",
            "brand_mark", "logo", "launcher_icon",
            "theme_light", "theme_dark", "font_family", "font_scale",
            "radius", "shadows", "density", "dark_mode_enabled",
            "default_currency", "enabled_currencies", "rates",
            "default_language", "supported_languages",
            "landing_ar", "landing_tr", "landing_en", "landing_image",
            "store_url", "apk_url", "apk_sha256", "apk_size_mb",
            "latest_version", "min_version",
            "update_message_ar", "update_message_tr", "update_message_en",
            "features", "review_mode", "review_threshold",
            "listing_expiry_days", "daily_listing_limit", "max_photos_per_listing",
            "max_video_seconds", "max_video_mb",
            "support_whatsapp", "support_email",
        ]

    def validate_rates(self, value):
        """
        سعر الصرف مدخل مالي — نفحصه بصرامة ونشرح الخطأ، ولا نبتلع قيمة سيئة.

        `clean_rates` تتجاهل الفاسد بصمت (وهذا صحيح عند القراءة من قاعدة
        البيانات)، لكن الأدمن الذي كتب «14,500» بفاصلة يستحق أن يُقال له ذلك
        بدل أن يحفظ ويظنّ أنه نجح ثم يكتشف أن السعر لم يتغيّر.
        """
        if not isinstance(value, dict):
            raise serializers.ValidationError("أسعار الصرف يجب أن تكون خريطة {العملة: السعر}.")
        errors = {}
        cleaned = {}
        for code, raw in value.items():
            if code == money.BASE_CURRENCY:
                continue  # 1 دولار = 1 دولار — ليست بيانات يدخلها أحد
            if not money.is_valid(code):
                errors[code] = "عملة غير معروفة."
                continue
            try:
                number = float(str(raw).replace(",", "").strip())
            except (TypeError, ValueError):
                errors[code] = "اكتب رقمًا بلا فواصل، مثل 14500 أو 35.2"
                continue
            if number <= 0:
                errors[code] = "السعر يجب أن يكون أكبر من صفر."
                continue
            cleaned[code] = number
        if errors:
            raise serializers.ValidationError(errors)
        return cleaned

    def validate_enabled_currencies(self, value):
        if not isinstance(value, list) or not value:
            raise serializers.ValidationError("اختر عملة واحدة على الأقل.")
        unknown = [c for c in value if not money.is_valid(c)]
        if unknown:
            raise serializers.ValidationError(f"عملات غير معروفة: {', '.join(unknown)}")
        return value

    def validate_default_currency(self, value):
        if not money.is_valid(value):
            raise serializers.ValidationError("عملة غير معروفة.")
        return value

    def validate_app_name_ar(self, value):
        value = " ".join(value.split())
        if len(value) < 2:
            raise serializers.ValidationError("اسم التطبيق قصير جدًا.")
        return value

    def validate_logo(self, value):
        return self._check_icon(value, "الشعار")

    def validate_launcher_icon(self, value):
        return self._check_icon(value, "أيقونة الجوال")

    @staticmethod
    def _check_icon(value, label: str):
        """
        الأيقونة تُعرض صغيرة جدًا — فملفّ ضخم عبء بلا مقابل، وصورة مستطيلة
        تُقصّ من أطرافها على الجوال. نرفض الحالتين هنا بدل أن يكتشفهما الأدمن
        بعد النشر.
        """
        if value in (None, ""):
            return value
        if value.size > 2 * 1024 * 1024:
            raise serializers.ValidationError(f"حجم {label} يتجاوز 2 ميغابايت.")
        from PIL import Image

        image = Image.open(value)
        width, height = image.size
        value.seek(0)
        if min(width, height) < 256:
            raise serializers.ValidationError(
                f"{label} صغيرة — المطلوب 256×256 على الأقل (الحالية {width}×{height})."
            )
        if abs(width - height) > max(width, height) * 0.02:
            raise serializers.ValidationError(
                f"{label} يجب أن تكون مربّعة — الحالية {width}×{height}."
            )
        return value

    def validate_font_family(self, value):
        if value not in defaults.BUNDLED_FONTS:
            raise serializers.ValidationError(
                "الخط غير محزوم داخل التطبيق. المتاح: "
                + "، ".join(defaults.BUNDLED_FONTS)
            )
        return value

    def validate_radius(self, value):
        allowed = set(defaults.DEFAULT_RADIUS)
        unknown = set(value) - allowed
        if unknown:
            raise serializers.ValidationError(f"مفاتيح غير معروفة: {', '.join(unknown)}")
        for key, number in value.items():
            if not isinstance(number, (int, float)) or not (0 <= number <= 999):
                raise serializers.ValidationError({key: "قيمة استدارة غير صالحة."})
        return value

    def validate_features(self, value):
        unknown = set(value) - set(defaults.DEFAULT_FEATURES)
        if unknown:
            raise serializers.ValidationError(f"مزايا غير معروفة: {', '.join(unknown)}")
        return {k: bool(v) for k, v in value.items()}

    def validate_supported_languages(self, value):
        allowed = {"ar", "tr", "en"}
        if not value or not set(value) <= allowed:
            raise serializers.ValidationError("اللغات المسموحة: ar, tr, en.")
        return list(dict.fromkeys(value))

    def validate(self, attrs):
        languages = attrs.get("supported_languages") or (
            self.instance.supported_languages if self.instance else ["ar"]
        )
        default = attrs.get("default_language") or (
            self.instance.default_language if self.instance else "ar"
        )
        if default not in languages:
            raise serializers.ValidationError(
                {"default_language": "اللغة الافتراضية يجب أن تكون ضمن اللغات المدعومة."}
            )
        return attrs


class ThemePresetSerializer(serializers.Serializer):
    key = serializers.CharField()
    name_ar = serializers.CharField()
    name_tr = serializers.CharField()
    name_en = serializers.CharField()
    light = serializers.DictField()
    dark = serializers.DictField()


class DownloadEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = DownloadEvent
        fields = ["version", "source"]
