from rest_framework import serializers

from apps.accounts.serializers import PublicSellerSerializer
from apps.catalog.models import Category, City
from apps.core import money
from apps.core.models import AppConfig
from apps.core.timeutils import format_price, time_ago

from .models import Favorite, Listing, ListingMedia, RejectionReason, Report


class MediaSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    thumb_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()

    class Meta:
        model = ListingMedia
        # للفيديو: `url` صورة الغلاف و`video_url` المقطع نفسه. التطبيق القديم
        # يقرأ `url` وحده فيعرض الغلاف صورةً — لا ينكسر على رابط mp4.
        fields = [
            "id", "kind", "url", "thumb_url", "video_url", "duration",
            "width", "height", "is_main", "sort_order",
        ]

    def get_url(self, obj) -> str | None:
        return self._absolute(obj.image)

    def get_thumb_url(self, obj) -> str | None:
        return self._absolute(obj.thumb) or self._absolute(obj.image)

    def get_video_url(self, obj) -> str | None:
        return self._absolute(obj.video) if obj.kind == ListingMedia.Kind.VIDEO else None

    def _absolute(self, field):
        if not field:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(field.url) if request else field.url


class BaseListingSerializer(serializers.ModelSerializer):
    """المشترك بين البطاقة والتفاصيل."""

    price_text = serializers.SerializerMethodField()
    time_text = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    thumb = serializers.SerializerMethodField()
    photos_count = serializers.IntegerField(read_only=True)
    has_video = serializers.BooleanField(read_only=True)
    is_favorited = serializers.SerializerMethodField()

    def get_price_text(self, obj) -> str:
        """السعر كما كتبه البائع بعملته — لا يتغيّر مهما تحرّك سعر الصرف."""
        return format_price(obj.price, obj.price_currency, self._lang())

    def get_time_text(self, obj) -> str:
        return time_ago(obj.published_at or obj.created_at, self._lang())

    def get_category(self, obj) -> dict | None:
        if not obj.category_id:
            return None
        lang = self._lang()
        category = obj.category
        parent = category.parent
        return {
            "id": category.id,
            "slug": category.slug,
            "name": category.name_for(lang),
            "icon": category.icon or (parent.icon if parent else ""),
            "parent": (
                {"id": parent.id, "slug": parent.slug, "name": parent.name_for(lang),
                 "icon": parent.icon}
                if parent else None
            ),
        }

    def get_city(self, obj) -> dict | None:
        if not obj.city_id:
            return None
        return {"id": obj.city.id, "slug": obj.city.slug, "name": obj.city.name_for(self._lang())}

    def get_thumb(self, obj) -> str | None:
        media = obj.main_media
        if not media:
            return None
        field = media.thumb or media.image
        request = self.context.get("request")
        return request.build_absolute_uri(field.url) if request else field.url

    def get_is_favorited(self, obj) -> bool:
        ids = self.context.get("favorite_ids")
        return obj.id in ids if ids is not None else False

    # ------------------------------------------------------------------

    def _lang(self) -> str:
        return getattr(self.context.get("request"), "lang", "ar")

    def _config(self):
        config = self.context.get("app_config")
        if config is None:
            config = AppConfig.get_solo()
            self.context["app_config"] = config
        return config


class ListingCardSerializer(BaseListingSerializer):
    """البطاقة في القوائم — أخفّ ما يمكن (الإنترنت ضعيف)."""

    class Meta:
        model = Listing
        fields = [
            "id", "title", "price", "price_currency", "price_text", "condition",
            "is_featured", "status", "thumb", "photos_count", "has_video",
            "category", "city", "address", "time_text", "views_count", "is_favorited",
        ]


class MyListingSerializer(ListingCardSerializer):
    """إعلاناتي — تضيف ما يخصّ صاحب الإعلان فقط."""

    class Meta(ListingCardSerializer.Meta):
        fields = ListingCardSerializer.Meta.fields + [
            "rejection_reason", "published_at", "expires_at", "created_at",
            "favorites_count", "contacts_count",
        ]


class ListingDetailSerializer(BaseListingSerializer):
    media = MediaSerializer(many=True, read_only=True)
    seller = PublicSellerSerializer(source="user", read_only=True)
    can_edit = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            "id", "title", "description", "price", "price_currency", "price_text", "condition",
            "status", "is_featured", "media", "thumb", "photos_count", "has_video",
            "category", "city", "address", "seller",
            "views_count", "favorites_count", "is_favorited",
            "time_text", "published_at", "expires_at", "created_at",
            "rejection_reason", "can_edit",
        ]

    def get_can_edit(self, obj) -> bool:
        user = getattr(self.context.get("request"), "user", None)
        return bool(user and user.is_authenticated and obj.user_id == user.id)


class ListingWriteSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.filter(is_active=True)
    )
    city = serializers.PrimaryKeyRelatedField(queryset=City.objects.filter(is_active=True))

    class Meta:
        model = Listing
        fields = ["id", "title", "description", "price", "price_currency", "condition",
                  "category", "city", "address"]

    def validate_price_currency(self, value):
        """
        لا نقبل إلا عملة متاحة فعلًا في الإعدادات.

        عملة خارج القائمة تعني إعلانًا بسعر لا يستطيع أحد تحويله ولا قراءة
        رمزه — وهو خطأ يظهر عند المشتري لا عند من ارتكبه.
        """
        config = self.context.get("app_config") or AppConfig.get_solo()
        allowed = config.enabled_currencies or list(money.CURRENCY_CODES)
        if value not in allowed:
            raise serializers.ValidationError("عملة غير متاحة.")
        return value

    def validate_address(self, value):
        return " ".join(value.split())[:200]

    def validate_title(self, value):
        value = " ".join(value.split())
        if len(value) < 5:
            raise serializers.ValidationError("العنوان قصير جدًا — اكتب وصفًا واضحًا للمنتج.")
        return value

    def validate_description(self, value):
        value = value.strip()
        config = AppConfig.get_solo()
        minimum = 10
        if len(value) < minimum:
            raise serializers.ValidationError(
                f"الوصف قصير جدًا — اكتب {minimum} أحرف على الأقل."
            )
        return value

    def validate_price(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("السعر لا يمكن أن يكون سالبًا.")
        if value is not None and value > 10**12:
            raise serializers.ValidationError("السعر كبير بشكل غير منطقي.")
        return value

    def validate_category(self, value):
        # نلزم القسم الفرعي: يجعل البحث أدقّ ويمنع تكدّس كل شيء في «أخرى»
        if value.parent_id is None and value.children.filter(is_active=True).exists():
            raise serializers.ValidationError("اختر قسمًا فرعيًا.")
        return value


class MediaUploadSerializer(serializers.Serializer):
    images = serializers.ListField(
        child=serializers.ImageField(),
        min_length=1,
        max_length=10,
        help_text="صور الإعلان — تُعاد معالجتها على الخادم",
    )
    main_index = serializers.IntegerField(required=False, min_value=0, default=0)


class FavoriteMergeSerializer(serializers.Serializer):
    """
    دمج مفضلة الزائر المحفوظة محليًا عند أول تسجيل دخول (قرار 17).
    بلا هذا يفقد الناس ما جمعوه قبل التسجيل — وهو أسوأ انطباع أول.
    """

    listing_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), max_length=300
    )


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ["id", "reason", "note", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_note(self, value):
        return value.strip()[:1000]


class RejectionReasonSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = RejectionReason
        fields = ["id", "name", "name_ar", "name_tr", "name_en", "sort_order"]

    def get_name(self, obj) -> str:
        return obj.name_for(getattr(self.context.get("request"), "lang", "ar"))


class ContactSerializer(serializers.Serializer):
    """رد نقطة كشف وسيلة التواصل — محميّة بتسجيل الدخول."""

    phone = serializers.CharField()
    phone_display = serializers.CharField()
    whatsapp = serializers.CharField()
    whatsapp_url = serializers.URLField()
    message = serializers.CharField()


# ---------------------------------------------------------------- الإدارة

class AdminListingSerializer(BaseListingSerializer):
    seller = serializers.SerializerMethodField()
    media = MediaSerializer(many=True, read_only=True)
    waiting_minutes = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            "id", "title", "description", "price", "price_currency", "price_text", "condition",
            "status", "is_featured", "media", "thumb", "photos_count",
            "category", "city", "address", "seller",
            "views_count", "reports_count", "rejection_reason",
            "created_at", "published_at", "expires_at", "reviewed_at",
            "waiting_minutes", "time_text",
        ]

    def get_seller(self, obj) -> dict:
        return {
            "id": obj.user_id,
            "name": obj.user.name,
            "phone": obj.user.display_phone,
            "role": obj.user.role,
            "status": obj.user.status,
            "approved_count": obj.user.listings_approved_count,
        }

    def get_waiting_minutes(self, obj) -> int | None:
        """مؤشّر زمن الانتظار في صفّ المراجعة (plan2 §8.6)."""
        if obj.status != Listing.Status.PENDING:
            return None
        from django.utils import timezone

        return int((timezone.now() - obj.created_at).total_seconds() // 60)


class ReviewActionSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), min_length=1, max_length=100)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)
