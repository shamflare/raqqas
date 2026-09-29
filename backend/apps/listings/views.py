"""
الإعلانات — قلب التطبيق.

قاعدة الوصول (قرار 17):
    تصفّح · بحث · عرض إعلان        → مفتوح للزائر بلا تسجيل
    نشر · تعديل · مفضلة · بلاغ     → يحتاج تسجيلًا
    كشف رقم البائع                 → يحتاج تسجيلًا (ويُسجَّل كإجراء)
"""

import uuid
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Case, Count, F, Q, When
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import Block
from apps.core.images import process_upload
from apps.core.videos import inspect_upload
from apps.core.models import AdminLog, AppConfig
from apps.core.pagination import DefaultPagination
from apps.core.throttling import FixedScopeThrottle

from .filters import SORTS, ListingFilter
from .models import Favorite, Listing, ListingMedia, RejectionReason, Report
from .serializers import (
    ContactSerializer,
    FavoriteMergeSerializer,
    ListingCardSerializer,
    ListingDetailSerializer,
    ListingWriteSerializer,
    MediaSerializer,
    MediaUploadSerializer,
    MyListingSerializer,
    RejectionReasonSerializer,
    ReportSerializer,
)


def _video_name(original: str | None) -> str:
    """اسم نظيف للملف الأصلي — امتداده كما جاء، فقد يكون mp4 أو mov أو 3gp."""
    suffix = Path(original or "").suffix.lower()
    if suffix not in {".mp4", ".mov", ".m4v", ".3gp", ".webm", ".mkv"}:
        suffix = ".mp4"
    return f"video-{uuid.uuid4().hex[:12]}{suffix}"


class WriteThrottle(FixedScopeThrottle):
    scope = "write"


class ContactThrottle(FixedScopeThrottle):
    scope = "contact"


class ReportThrottle(FixedScopeThrottle):
    scope = "report"


class ListingViewSet(viewsets.ModelViewSet):
    """/api/v1/listings"""

    pagination_class = DefaultPagination
    filterset_class = ListingFilter
    permission_classes = [AllowAny]

    # ------------------------------------------------------------------ أساسيات

    def get_queryset(self):
        user = getattr(self.request, "user", None)
        queryset = Listing.objects.with_relations()

        if self.action in {"list", "retrieve"}:
            queryset = queryset.visible_to(user if self.action == "retrieve" else None)
        else:
            queryset = queryset.exclude(status=Listing.Status.DELETED)

        if self.action in {"list", "retrieve"}:
            # إعلانات من حظرهم المستخدم لا تظهر له — سياسة المحتوى من المستخدمين
            blocked = Block.blocked_ids_for(user)
            if blocked:
                queryset = queryset.exclude(user_id__in=blocked)

        if self.action == "list":
            # الترتيب الافتراضي: المميّز أولًا ثم الأحدث
            queryset = queryset.order_by(*SORTS["newest"])
        return queryset

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return ListingWriteSerializer
        if self.action == "retrieve":
            return ListingDetailSerializer
        return ListingCardSerializer

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_throttles(self):
        if self.action in {"create", "update", "partial_update", "upload_media", "upload_video"}:
            return [WriteThrottle()]
        return super().get_throttles()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["app_config"] = AppConfig.get_solo()
        context["favorite_ids"] = self._favorite_ids()
        return context

    def _favorite_ids(self) -> set[int]:
        user = getattr(self.request, "user", None)
        if not (user and user.is_authenticated):
            return set()
        return set(
            Favorite.objects.filter(user=user).values_list("listing_id", flat=True)
        )

    # ------------------------------------------------------------------ عرض

    def retrieve(self, request, *args, **kwargs):
        listing = self.get_object()
        # لا نحسب مشاهدة صاحب الإعلان لنفسه — كان يضخّم الأرقام بلا معنى
        viewer = request.user if request.user and request.user.is_authenticated else None
        if not viewer or viewer.id != listing.user_id:
            listing.register_view()
            listing.views_count += 1
        serializer = self.get_serializer(listing)
        return Response(serializer.data)

    # ------------------------------------------------------------------ إنشاء وتعديل

    def perform_create(self, serializer):
        config = AppConfig.get_solo()
        user = self.request.user
        self._enforce_daily_limit(user, config)

        listing = serializer.save(user=user, status=Listing.Status.PENDING)
        if self._auto_publish(user, config):
            listing.publish(expiry_days=config.listing_expiry_days)

    def perform_update(self, serializer):
        listing = self.get_object()
        if listing.user_id != self.request.user.id:
            raise PermissionDenied("لا يمكنك تعديل إعلان لا تملكه.")
        if listing.status in {Listing.Status.DELETED, Listing.Status.SUSPENDED}:
            raise ValidationError({"detail": "لا يمكن تعديل هذا الإعلان."})

        config = AppConfig.get_solo()
        updated = serializer.save()
        # أي تعديل على محتوى منشور يعيده للمراجعة — وإلا صار بابًا خلفيًا
        if config.review_mode != "off" and not self._auto_publish(self.request.user, config):
            updated.status = Listing.Status.PENDING
            updated.reviewed_at = None
            updated.save(update_fields=["status", "reviewed_at", "updated_at"])

    def perform_destroy(self, instance):
        if instance.user_id != self.request.user.id:
            raise PermissionDenied("لا يمكنك حذف إعلان لا تملكه.")
        instance.status = Listing.Status.DELETED
        instance.save(update_fields=["status", "updated_at"])

    @staticmethod
    def _enforce_daily_limit(user, config):
        since = timezone.now() - timezone.timedelta(days=1)
        count = Listing.objects.filter(user=user, created_at__gte=since).exclude(
            status=Listing.Status.DELETED
        ).count()
        if count >= config.daily_listing_limit:
            raise ValidationError({
                "detail": f"وصلت الحد اليومي ({config.daily_listing_limit} إعلانات). "
                          "جرّب غدًا أو راسل الدعم."
            })

    @staticmethod
    def _auto_publish(user, config) -> bool:
        """باب الخروج من المراجعة الكاملة (plan2 §8.6) — إعداد واحد في اللوحة."""
        # ثقة ممنوحة يدويًا لهذا المستخدم بعينه — تتقدّم على الوضع العام
        if user.auto_publish:
            return True
        if config.review_mode == "off":
            return True
        if config.review_mode == "new_users":
            return user.listings_approved_count >= config.review_threshold
        return False

    # ------------------------------------------------------------------ إعلاناتي

    @extend_schema(summary="إعلاناتي بكل حالاتها")
    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated],
            url_path="mine")
    def mine(self, request):
        queryset = (
            Listing.objects.with_relations()
            .filter(user=request.user)
            .exclude(status=Listing.Status.DELETED)
            .order_by("-created_at")
        )
        state = request.GET.get("status")
        if state:
            queryset = queryset.filter(status=state)

        counts = dict(
            Listing.objects.filter(user=request.user)
            .exclude(status=Listing.Status.DELETED)
            .values_list("status")
            .annotate(n=Count("id"))
        )

        page = self.paginate_queryset(queryset)
        serializer = MyListingSerializer(page, many=True, context=self.get_serializer_context())
        response = self.get_paginated_response(serializer.data)
        response.data["counts"] = counts
        return response

    # ------------------------------------------------------------------ الصور

    @extend_schema(summary="رفع صور لإعلان", request=MediaUploadSerializer)
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated],
            url_path="media", parser_classes=[MultiPartParser, FormParser])
    def upload_media(self, request, pk=None):
        listing = self.get_object()
        if listing.user_id != request.user.id:
            raise PermissionDenied("لا يمكنك رفع صور لإعلان لا تملكه.")

        config = AppConfig.get_solo()
        images = request.FILES.getlist("images") or request.FILES.getlist("image")
        if not images:
            raise ValidationError({"images": "لم تُرفع أي صورة."})

        # الفيديو لا يُحسب من حصّة الصور — له حصّته (واحد لكل إعلان)
        existing = listing.media.filter(kind=ListingMedia.Kind.PHOTO).count()
        room = config.max_photos_per_listing - existing
        if room <= 0:
            raise ValidationError({
                "images": f"وصلت الحد الأقصى ({config.max_photos_per_listing} صور)."
            })

        created = []
        for index, uploaded in enumerate(images[:room]):
            processed = process_upload(uploaded)
            media = ListingMedia(
                listing=listing,
                width=processed["width"],
                height=processed["height"],
                checksum=processed["checksum"],
                sort_order=existing + index,
                is_main=(existing == 0 and index == 0),
            )
            media.image.save(processed["full"].name, processed["full"], save=False)
            media.thumb.save(processed["thumb"].name, processed["thumb"], save=False)
            media.save()
            created.append(media)

        return Response(
            MediaSerializer(created, many=True, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(summary="رفع فيديو لإعلان (واحد فقط)")
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated],
            url_path="video", parser_classes=[MultiPartParser, FormParser])
    def upload_video(self, request, pk=None):
        """
        مقطع واحد لكل إعلان، بمدة وحجم تضبطهما الإدارة (AppConfig).

        يُفحص ويُستخرج غلافه هنا، ويُحفظ الأصلي كما هو فيُعرض فورًا. الضغط
        يجري بعدها خارج الطلب (`manage.py process_videos`) — انظر apps/core/videos.py.
        """
        listing = self.get_object()
        if listing.user_id != request.user.id:
            raise PermissionDenied("لا يمكنك رفع فيديو لإعلان لا تملكه.")

        config = AppConfig.get_solo()
        if not config.max_video_seconds:
            raise ValidationError({"video": "رفع الفيديو متوقّف حاليًا."})

        uploaded = request.FILES.get("video")
        if not uploaded:
            raise ValidationError({"video": "لم يُرفع أي فيديو."})
        if listing.media.filter(kind=ListingMedia.Kind.VIDEO).exists():
            raise ValidationError({"video": "للإعلان فيديو بالفعل — احذفه أولًا لترفع غيره."})

        try:
            inspected = inspect_upload(
                uploaded,
                max_seconds=config.max_video_seconds,
                max_bytes=config.max_video_mb * 1024 * 1024,
            )
        except DjangoValidationError as exc:
            raise ValidationError({"video": exc.messages[0]}) from exc

        cover = inspected["poster"]
        media = ListingMedia(
            listing=listing,
            kind=ListingMedia.Kind.VIDEO,
            width=cover["width"],
            height=cover["height"],
            duration=inspected["duration"],
            video_state=ListingMedia.VideoState.PENDING,
            # بعد الصور في ترتيب الخادم: التطبيق القديم يعرض الغلاف آخر المعرض
            sort_order=1000,
            is_main=False,
        )
        media.image.save(cover["full"].name, cover["full"], save=False)
        media.thumb.save(cover["thumb"].name, cover["thumb"], save=False)
        media.video.save(_video_name(uploaded.name), uploaded, save=False)
        media.save()

        return Response(
            MediaSerializer(media, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(summary="حذف صورة أو فيديو")
    @action(detail=True, methods=["delete"], permission_classes=[IsAuthenticated],
            url_path=r"media/(?P<media_id>\d+)")
    def delete_media(self, request, pk=None, media_id=None):
        listing = self.get_object()
        if listing.user_id != request.user.id:
            raise PermissionDenied("لا يمكنك تعديل إعلان لا تملكه.")
        media = ListingMedia.objects.filter(listing_id=listing.pk, pk=media_id).first()
        if not media:
            return Response(status=status.HTTP_404_NOT_FOUND)
        was_main = media.is_main
        media.delete()

        # ⚠️ استعلام جديد لا `listing.media` — فذاك يقرأ من نسخة مُحمَّلة مسبقًا
        # (prefetch_related) ما تزال تحوي الصورة المحذوفة، فكنّا نحاول ترقية صفٍّ
        # لم يعد موجودًا فيسقط الطلب بخطأ 500 عند حذف الصورة الرئيسية تحديدًا.
        if was_main:
            # صورة أولًا — غلاف الفيديو لا يصير الصورة الرئيسية ما دامت هناك صور
            first = (
                ListingMedia.objects.filter(listing_id=listing.pk)
                .order_by(
                    Case(When(kind=ListingMedia.Kind.PHOTO, then=0), default=1),
                    "sort_order", "id",
                )
                .first()
            )
            if first:
                first.is_main = True
                first.save(update_fields=["is_main"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ------------------------------------------------------------------ التواصل

    @extend_schema(summary="كشف وسيلة التواصل مع البائع", responses=ContactSerializer)
    @action(detail=True, methods=["get"], permission_classes=[IsAuthenticated],
            throttle_classes=[ContactThrottle], url_path="contact")
    def contact(self, request, pk=None):
        """
        ⚠️ هنا فقط يظهر رقم البائع — ولا يظهر في أي رد عام.

        سببان: قرار 17 (التواصل يحتاج تسجيلًا)، وحماية الأرقام من السحب الآلي.
        """
        listing = self.get_object()
        config = AppConfig.get_solo()

        if not listing.is_published and listing.user_id != request.user.id:
            raise ValidationError({"detail": "هذا الإعلان غير متاح حاليًا."})
        if not config.feature("whatsapp_enabled"):
            raise ValidationError({"detail": "التواصل معطّل مؤقتًا."})

        seller = listing.user
        lang = getattr(request, "lang", "ar")
        link = f"{settings.PUBLIC_SITE_URL}/l/{listing.id}"
        templates = {
            "ar": f"مرحبًا، بخصوص إعلانك: {listing.title}\n{link}",
            "tr": f"Merhaba, ilanınız hakkında: {listing.title}\n{link}",
            "en": f"Hello, regarding your listing: {listing.title}\n{link}",
        }
        message = templates.get(lang, templates["ar"])

        listing.register_contact()

        return Response({
            "phone": seller.contact_number,
            "phone_display": seller.display_phone,
            "whatsapp": seller.contact_number,
            "whatsapp_url": seller.whatsapp_url(message),
            "message": message,
        })

    # ------------------------------------------------------------------ البلاغ

    @extend_schema(summary="الإبلاغ عن إعلان", request=ReportSerializer)
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated],
            throttle_classes=[ReportThrottle], url_path="report")
    def report(self, request, pk=None):
        listing = self.get_object()
        if listing.user_id == request.user.id:
            raise ValidationError({"detail": "لا يمكنك الإبلاغ عن إعلانك."})

        serializer = ReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        report, created = Report.objects.get_or_create(
            listing=listing,
            reporter=request.user,
            status=Report.Status.OPEN,
            defaults=serializer.validated_data,
        )
        if created:
            Listing.objects.filter(pk=listing.pk).update(
                reports_count=F("reports_count") + 1
            )
        return Response(
            {"ok": True, "already_reported": not created},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


# ---------------------------------------------------------------- المفضلة

class FavoriteViewSet(viewsets.ViewSet):
    """/api/v1/favorites — تحتاج تسجيلًا. الزائر يحفظ محليًا ثم يُدمج عند الدخول."""

    permission_classes = [IsAuthenticated]

    def list(self, request):
        queryset = (
            Listing.objects.with_relations()
            .filter(favorited_by__user=request.user)
            .exclude(status=Listing.Status.DELETED)
            .order_by("-favorited_by__created_at")
        )
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = ListingCardSerializer(
            page, many=True,
            context={"request": request, "app_config": AppConfig.get_solo(),
                     "favorite_ids": {listing.id for listing in page}},
        )
        return paginator.get_paginated_response(serializer.data)

    def create(self, request):
        listing_id = request.data.get("listing")
        listing = Listing.objects.filter(pk=listing_id).first()
        if not listing:
            raise ValidationError({"listing": "الإعلان غير موجود."})
        _, created = Favorite.objects.get_or_create(user=request.user, listing=listing)
        if created:
            Listing.objects.filter(pk=listing.pk).update(
                favorites_count=F("favorites_count") + 1
            )
        return Response({"ok": True, "added": created},
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def destroy(self, request, pk=None):
        deleted, _ = Favorite.objects.filter(user=request.user, listing_id=pk).delete()
        if deleted:
            Listing.objects.filter(pk=pk, favorites_count__gt=0).update(
                favorites_count=F("favorites_count") - 1
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(summary="دمج مفضلة الزائر بعد تسجيل الدخول",
                   request=FavoriteMergeSerializer)
    @action(detail=False, methods=["post"], url_path="merge")
    def merge(self, request):
        serializer = FavoriteMergeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = set(serializer.validated_data["listing_ids"])

        existing = set(
            Favorite.objects.filter(user=request.user, listing_id__in=ids)
            .values_list("listing_id", flat=True)
        )
        valid = set(
            Listing.objects.published().filter(pk__in=ids - existing)
            .values_list("id", flat=True)
        )
        with transaction.atomic():
            Favorite.objects.bulk_create(
                [Favorite(user=request.user, listing_id=i) for i in valid],
                ignore_conflicts=True,
            )
            Listing.objects.filter(pk__in=valid).update(
                favorites_count=F("favorites_count") + 1
            )
        return Response({"merged": len(valid), "total": len(existing) + len(valid)})


# ---------------------------------------------------------------- مساعدات عامة

@extend_schema(summary="أسباب الإبلاغ الجاهزة")
@api_view(["GET"])
@permission_classes([AllowAny])
def report_reasons(request):
    lang = getattr(request, "lang", "ar")
    labels = {
        "ar": {"fraud": "احتيال", "fake": "إعلان مزيف", "violation": "محتوى مخالف",
               "banned_item": "منتج ممنوع", "other": "سبب آخر"},
        "tr": {"fraud": "Dolandırıcılık", "fake": "Sahte ilan", "violation": "Uygunsuz içerik",
               "banned_item": "Yasaklı ürün", "other": "Diğer"},
        "en": {"fraud": "Fraud", "fake": "Fake listing", "violation": "Inappropriate content",
               "banned_item": "Banned item", "other": "Other"},
    }.get(lang, {})
    icons = {"fraud": "⚠️", "fake": "🎭", "violation": "🚫", "banned_item": "⛔", "other": "✍️"}
    return Response([
        {"id": key, "label": labels.get(key, label), "icon": icons.get(key, "")}
        for key, label in Report.Reason.choices
    ])


@extend_schema(summary="أسباب الرفض الجاهزة (للإدارة)")
@api_view(["GET"])
@permission_classes([AllowAny])
def rejection_reasons(request):
    queryset = RejectionReason.objects.filter(is_active=True)
    return Response(
        RejectionReasonSerializer(queryset, many=True, context={"request": request}).data
    )


@extend_schema(summary="إحصاءات الصفحة الرئيسية")
@api_view(["GET"])
@permission_classes([AllowAny])
def home_summary(request):
    """
    رد واحد للشاشة الأولى: أقسام + مميّزة + أحدث.
    طلب واحد بدل ثلاثة — فرق محسوس على إنترنت ضعيف.
    """
    from apps.catalog.queries import category_tree_queryset
    from apps.catalog.serializers import CategorySerializer

    roots = category_tree_queryset()

    base = Listing.objects.published().with_relations()
    blocked = Block.blocked_ids_for(request.user)
    if blocked:
        base = base.exclude(user_id__in=blocked)
    favorite_ids = set()
    if request.user and request.user.is_authenticated:
        favorite_ids = set(
            Favorite.objects.filter(user=request.user).values_list("listing_id", flat=True)
        )

    context = {
        "request": request,
        "app_config": AppConfig.get_solo(),
        "favorite_ids": favorite_ids,
    }
    featured = base.filter(is_featured=True).order_by("-published_at")[:10]
    latest = base.filter(is_featured=False).order_by("-published_at")[:20]

    return Response({
        "categories": CategorySerializer(roots, many=True, context=context).data,
        "featured": ListingCardSerializer(featured, many=True, context=context).data,
        "latest": ListingCardSerializer(latest, many=True, context=context).data,
    })
