"""الإعلانات وصورها والمفضلة والبلاغات."""

from django.core.validators import MinLengthValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.core import money
from apps.core.models import TimeStampedModel, TranslatedNameModel


class ListingQuerySet(models.QuerySet):
    def published(self):
        return self.filter(status=Listing.Status.PUBLISHED).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        )

    def visible_to(self, user):
        """المنشور للجميع — وصاحب الإعلان يرى إعلاناته بكل حالاتها."""
        if user is not None and getattr(user, "is_authenticated", False):
            if user.is_staff_role:
                return self.exclude(status=Listing.Status.DELETED)
            return self.published() | self.filter(user=user).exclude(
                status=Listing.Status.DELETED
            )
        return self.published()

    def with_relations(self):
        return self.select_related(
            "user", "category", "category__parent", "city"
        ).prefetch_related("media")


class Listing(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "مسودّة"
        PENDING = "pending", "قيد المراجعة"
        PUBLISHED = "published", "منشور"
        REJECTED = "rejected", "مرفوض"
        EXPIRED = "expired", "منتهٍ"
        SUSPENDED = "suspended", "موقوف"
        DELETED = "deleted", "محذوف"

    class Condition(models.TextChoices):
        NEW = "new", "جديد"
        USED = "used", "مستعمل"

    user = models.ForeignKey(
        "accounts.User", verbose_name="صاحب الإعلان",
        on_delete=models.CASCADE, related_name="listings",
    )
    category = models.ForeignKey(
        "catalog.Category", verbose_name="القسم",
        on_delete=models.PROTECT, related_name="listings",
    )
    city = models.ForeignKey(
        "catalog.City", verbose_name="المحافظة",
        on_delete=models.PROTECT, related_name="listings",
    )
    address = models.CharField(
        "العنوان", max_length=200, blank=True,
        help_text="يكتبه صاحب الإعلان بحرّية — لا قائمة ثابتة",
    )
    # يبقى للإعلانات القديمة فقط. الحقل الحيّ الآن هو `city` + `address`.
    neighborhood = models.ForeignKey(
        "catalog.Neighborhood", verbose_name="الحي (متروك)",
        null=True, blank=True,
        on_delete=models.SET_NULL, related_name="listings",
    )

    title = models.CharField("العنوان", max_length=120, validators=[MinLengthValidator(5)])
    description = models.TextField("الوصف", max_length=4000)

    # السعر بالعملة التي اختارها البائع. null = «على السوم».
    #
    # ⚠️ العملة تُحفظ مع الإعلان ولا تُشتقّ من الإعدادات. هذا ما يجعل رقم
    # البائع ثابتًا مدى حياة الإعلان مهما تحرّك سعر الصرف — التحويل يحدث عند
    # العرض فقط (apps/core/money.py).
    price = models.BigIntegerField("السعر", null=True, blank=True, db_index=True)
    price_currency = models.CharField(
        "عملة السعر", max_length=3, default=money.BASE_CURRENCY,
        choices=money.CURRENCY_CHOICES, db_index=True,
    )
    condition = models.CharField(
        "الحالة", max_length=8, choices=Condition.choices, default=Condition.USED
    )

    status = models.CharField(
        "حالة الإعلان", max_length=12, choices=Status.choices,
        default=Status.PENDING, db_index=True,
    )
    rejection_reason = models.TextField("سبب الرفض", blank=True)

    is_featured = models.BooleanField("مميّز", default=False, db_index=True)
    featured_until = models.DateTimeField("مميّز حتى", null=True, blank=True)

    views_count = models.PositiveIntegerField("المشاهدات", default=0)
    contacts_count = models.PositiveIntegerField("مرّات كشف الرقم", default=0)
    favorites_count = models.PositiveIntegerField("مرّات الحفظ", default=0)
    reports_count = models.PositiveIntegerField("عدد البلاغات", default=0)

    reviewed_by = models.ForeignKey(
        "accounts.User", verbose_name="راجعه",
        null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_listings",
    )
    reviewed_at = models.DateTimeField("تاريخ المراجعة", null=True, blank=True)
    published_at = models.DateTimeField("تاريخ النشر", null=True, blank=True, db_index=True)
    expires_at = models.DateTimeField("ينتهي في", null=True, blank=True, db_index=True)

    objects = ListingQuerySet.as_manager()

    class Meta:
        verbose_name = "إعلان"
        verbose_name_plural = "الإعلانات"
        ordering = ["-is_featured", "-published_at", "-created_at"]
        indexes = [
            models.Index(fields=["status", "-published_at"]),
            models.Index(fields=["category", "status"]),
            models.Index(fields=["city", "status"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self) -> str:
        return self.title

    # ------------------------------------------------------------------

    @property
    def is_published(self) -> bool:
        return self.status == self.Status.PUBLISHED and not self.is_expired

    @property
    def is_expired(self) -> bool:
        return bool(self.expires_at and self.expires_at <= timezone.now())

    @property
    def is_featured_now(self) -> bool:
        if not self.is_featured:
            return False
        return self.featured_until is None or self.featured_until > timezone.now()

    @property
    def main_media(self):
        media = list(self.media.all())
        if not media:
            return None
        return next((m for m in media if m.is_main), media[0])

    @property
    def photos_count(self) -> int:
        return sum(1 for m in self.media.all() if m.kind == ListingMedia.Kind.PHOTO)

    @property
    def has_video(self) -> bool:
        return any(m.kind == ListingMedia.Kind.VIDEO for m in self.media.all())

    # ------------------------------------------------------------------

    def publish(self, *, reviewer=None, expiry_days: int = 60):
        now = timezone.now()
        self.status = self.Status.PUBLISHED
        self.rejection_reason = ""
        self.published_at = self.published_at or now
        self.expires_at = now + timezone.timedelta(days=expiry_days)
        self.reviewed_by = reviewer
        self.reviewed_at = now
        self.save(update_fields=[
            "status", "rejection_reason", "published_at", "expires_at",
            "reviewed_by", "reviewed_at", "updated_at",
        ])

    def reject(self, reason: str, *, reviewer=None):
        self.status = self.Status.REJECTED
        self.rejection_reason = reason
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.save(update_fields=[
            "status", "rejection_reason", "reviewed_by", "reviewed_at", "updated_at"
        ])

    def register_view(self):
        Listing.objects.filter(pk=self.pk).update(views_count=F("views_count") + 1)

    def register_contact(self):
        Listing.objects.filter(pk=self.pk).update(contacts_count=F("contacts_count") + 1)


def media_path(instance, filename: str) -> str:
    return f"listings/{instance.listing_id}/{filename}"


class ListingMedia(models.Model):
    class Kind(models.TextChoices):
        PHOTO = "photo", "صورة"
        VIDEO = "video", "فيديو"

    listing = models.ForeignKey(
        Listing, verbose_name="الإعلان", on_delete=models.CASCADE, related_name="media"
    )
    class VideoState(models.TextChoices):
        NONE = "", "—"
        PENDING = "pending", "بانتظار الضغط"
        READY = "ready", "مضغوط"
        FAILED = "failed", "تعذّر الضغط (يُعرض الأصلي)"

    kind = models.CharField("النوع", max_length=8, choices=Kind.choices, default=Kind.PHOTO)
    # للفيديو: صورة الغلاف. هكذا يعرضه التطبيق القديم صورةً ولا ينكسر.
    image = models.ImageField("الصورة", upload_to=media_path)
    thumb = models.ImageField("المصغّرة", upload_to=media_path, blank=True, null=True)
    video = models.FileField("الفيديو", upload_to=media_path, blank=True, null=True)
    duration = models.PositiveIntegerField("المدة (ثانية)", default=0)
    video_state = models.CharField(
        "حالة الفيديو", max_length=8, choices=VideoState.choices,
        default=VideoState.NONE, blank=True, db_index=True,
    )
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    checksum = models.CharField(max_length=64, blank=True, db_index=True)
    is_main = models.BooleanField("الصورة الرئيسية", default=False)
    sort_order = models.PositiveSmallIntegerField("الترتيب", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "صورة إعلان"
        verbose_name_plural = "صور الإعلانات"
        ordering = ["sort_order", "id"]

    def __str__(self) -> str:
        label = "فيديو" if self.kind == self.Kind.VIDEO else "صورة"
        return f"{label} #{self.pk} — إعلان {self.listing_id}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_main:
            ListingMedia.objects.filter(listing_id=self.listing_id).exclude(
                pk=self.pk
            ).update(is_main=False)


class Favorite(models.Model):
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="favorites"
    )
    listing = models.ForeignKey(
        Listing, on_delete=models.CASCADE, related_name="favorited_by"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "مفضّلة"
        verbose_name_plural = "المفضلة"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "listing"], name="uniq_favorite")
        ]

    def __str__(self) -> str:
        return f"{self.user_id} ❤ {self.listing_id}"


class RejectionReason(TranslatedNameModel):
    """أسباب رفض جاهزة — تسرّع المراجعة (plan2 §8.6)."""

    is_active = models.BooleanField("مفعّل", default=True)
    sort_order = models.PositiveSmallIntegerField("الترتيب", default=0)

    class Meta:
        verbose_name = "سبب رفض"
        verbose_name_plural = "أسباب الرفض"
        ordering = ["sort_order", "id"]


class Report(models.Model):
    class Reason(models.TextChoices):
        FRAUD = "fraud", "احتيال"
        FAKE = "fake", "إعلان مزيف"
        VIOLATION = "violation", "محتوى مخالف"
        BANNED_ITEM = "banned_item", "منتج ممنوع"
        OTHER = "other", "سبب آخر"

    class Status(models.TextChoices):
        OPEN = "open", "مفتوح"
        RESOLVED = "resolved", "عولج"
        DISMISSED = "dismissed", "مرفوض"

    listing = models.ForeignKey(
        Listing, verbose_name="الإعلان", on_delete=models.CASCADE, related_name="reports"
    )
    reporter = models.ForeignKey(
        "accounts.User", verbose_name="المُبلِّغ",
        null=True, on_delete=models.SET_NULL, related_name="reports",
    )
    reason = models.CharField("السبب", max_length=16, choices=Reason.choices)
    note = models.TextField("تفاصيل", blank=True, max_length=1000)
    status = models.CharField(
        "الحالة", max_length=12, choices=Status.choices, default=Status.OPEN, db_index=True
    )
    resolved_by = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="resolved_reports",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "بلاغ"
        verbose_name_plural = "البلاغات"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["listing", "reporter"],
                condition=Q(status="open"),
                name="uniq_open_report_per_user",
            )
        ]

    def __str__(self) -> str:
        return f"بلاغ {self.get_reason_display()} — إعلان {self.listing_id}"
