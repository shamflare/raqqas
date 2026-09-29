"""
صفّ المراجعة وأدوات الإدارة (plan2 §8.6).

الهدف المعلن: تقليل زمن الانتظار — لأن أكثر ما ينفّر البائعين هو انتظار الموافقة.
لذلك: صفّ سريع · موافقة جماعية · أسباب رفض جاهزة · مؤشّر زمن انتظار.
"""

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.accounts.models import User
from apps.core.models import AdminLog, AppConfig
from apps.core.pagination import DefaultPagination
from apps.core.permissions import IsAdminRole, IsStaffRole
from apps.notifications.services import notify_listing_published, notify_listing_rejected

from .models import Listing, Report
from .serializers import AdminListingSerializer, ReviewActionSerializer


def _context(request):
    return {"request": request, "app_config": AppConfig.get_solo(), "favorite_ids": set()}


@extend_schema(summary="صفّ المراجعة")
@api_view(["GET"])
@permission_classes([IsStaffRole])
def review_queue(request):
    queryset = (
        Listing.objects.with_relations()
        .filter(status=Listing.Status.PENDING)
        .order_by("created_at")          # الأقدم أولًا — لا أحد ينتظر للأبد
    )
    paginator = DefaultPagination()
    page = paginator.paginate_queryset(queryset, request)
    serializer = AdminListingSerializer(page, many=True, context=_context(request))
    response = paginator.get_paginated_response(serializer.data)
    response.data["waiting"] = _waiting_stats()
    return response


def _waiting_stats() -> dict:
    """مؤشّر زمن الانتظار — إن تجاوز المتوسط ساعتين، ننتقل لنمط «الجدد فقط»."""
    now = timezone.now()
    pending = Listing.objects.filter(status=Listing.Status.PENDING)
    oldest = pending.order_by("created_at").values_list("created_at", flat=True).first()
    reviewed = (
        Listing.objects.filter(
            reviewed_at__isnull=False, reviewed_at__gte=now - timezone.timedelta(days=7)
        )
        .annotate(
            wait=ExpressionWrapper(
                F("reviewed_at") - F("created_at"), output_field=DurationField()
            )
        )
        .aggregate(avg=Avg("wait"))
    )

    average = reviewed["avg"]
    average_minutes = int(average.total_seconds() // 60) if average else None
    return {
        "pending_count": pending.count(),
        "oldest_wait_minutes": int((now - oldest).total_seconds() // 60) if oldest else 0,
        "avg_wait_minutes_7d": average_minutes,
        "over_threshold": bool(average_minutes and average_minutes > 120),
    }


@extend_schema(summary="قبول إعلانات (فردي أو جماعي)", request=ReviewActionSerializer)
@api_view(["POST"])
@permission_classes([IsStaffRole])
def approve_listings(request):
    serializer = ReviewActionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    config = AppConfig.get_solo()

    listings = Listing.objects.filter(
        pk__in=serializer.validated_data["ids"],
        status__in=[Listing.Status.PENDING, Listing.Status.REJECTED, Listing.Status.SUSPENDED],
    )

    approved = []
    for listing in listings:
        listing.publish(reviewer=request.user, expiry_days=config.listing_expiry_days)
        User.objects.filter(pk=listing.user_id).update(
            listings_approved_count=F("listings_approved_count") + 1
        )
        AdminLog.record(request.user, "approve", listing)
        notify_listing_published(listing)
        approved.append(listing.id)

    return Response({"approved": approved, "count": len(approved)})


@extend_schema(summary="رفض إعلانات بسبب", request=ReviewActionSerializer)
@api_view(["POST"])
@permission_classes([IsStaffRole])
def reject_listings(request):
    serializer = ReviewActionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    reason = (serializer.validated_data.get("reason") or "").strip()
    if not reason:
        return Response(
            {"error": {"code": "validation_error",
                       "message": "سبب الرفض مطلوب — البائع يحتاج أن يعرف ما يصلحه."}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    listings = Listing.objects.filter(
        pk__in=serializer.validated_data["ids"],
        status__in=[Listing.Status.PENDING, Listing.Status.PUBLISHED],
    )
    rejected = []
    for listing in listings:
        listing.reject(reason, reviewer=request.user)
        AdminLog.record(request.user, "reject", listing, note=reason)
        notify_listing_rejected(listing, reason)
        rejected.append(listing.id)

    return Response({"rejected": rejected, "count": len(rejected)})


@extend_schema(summary="إيقاف إعلان منشور", request=ReviewActionSerializer)
@api_view(["POST"])
@permission_classes([IsStaffRole])
def suspend_listings(request):
    serializer = ReviewActionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    reason = serializer.validated_data.get("reason", "")

    listings = list(Listing.objects.filter(pk__in=serializer.validated_data["ids"]))
    Listing.objects.filter(pk__in=[listing.pk for listing in listings]).update(
        status=Listing.Status.SUSPENDED,
        rejection_reason=reason,
        reviewed_by=request.user,
        reviewed_at=timezone.now(),
    )
    for listing in listings:
        AdminLog.record(request.user, "suspend", listing, note=reason)
    return Response({"suspended": [l.pk for l in listings], "count": len(listings)})


@extend_schema(summary="تمييز إعلان / إلغاء التمييز")
@api_view(["POST"])
@permission_classes([IsStaffRole])
def toggle_featured(request, pk: int):
    listing = Listing.objects.filter(pk=pk).first()
    if not listing:
        return Response(status=status.HTTP_404_NOT_FOUND)

    days = int(request.data.get("days") or 0)
    listing.is_featured = not listing.is_featured
    listing.featured_until = (
        timezone.now() + timezone.timedelta(days=days) if listing.is_featured and days else None
    )
    listing.save(update_fields=["is_featured", "featured_until", "updated_at"])
    AdminLog.record(request.user, "feature", listing, note=f"{days} يوم" if days else "")
    return Response({"is_featured": listing.is_featured, "featured_until": listing.featured_until})


@extend_schema(summary="قائمة كل الإعلانات للإدارة")
@api_view(["GET"])
@permission_classes([IsStaffRole])
def admin_listings(request):
    queryset = Listing.objects.with_relations().exclude(status=Listing.Status.DELETED)

    state = request.GET.get("status")
    if state:
        queryset = queryset.filter(status=state)
    search = request.GET.get("q")
    if search:
        queryset = queryset.filter(
            Q(title__icontains=search)
            | Q(user__name__icontains=search)
            | Q(user__phone__icontains=search)
        )
    if request.GET.get("reported") == "1":
        queryset = queryset.filter(reports_count__gt=0)

    paginator = DefaultPagination()
    page = paginator.paginate_queryset(queryset.order_by("-created_at"), request)
    serializer = AdminListingSerializer(page, many=True, context=_context(request))
    return paginator.get_paginated_response(serializer.data)


@extend_schema(summary="لوحة الأرقام")
@api_view(["GET"])
@permission_classes([IsStaffRole])
def dashboard(request):
    now = timezone.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timezone.timedelta(days=7)

    listings = Listing.objects.exclude(status=Listing.Status.DELETED)
    by_status = dict(listings.values_list("status").annotate(n=Count("id")))

    return Response({
        "listings": {
            "total": listings.count(),
            "by_status": by_status,
            "today": listings.filter(created_at__gte=today).count(),
            "week": listings.filter(created_at__gte=week_ago).count(),
        },
        "users": {
            "total": User.objects.count(),
            "today": User.objects.filter(created_at__gte=today).count(),
            "week": User.objects.filter(created_at__gte=week_ago).count(),
            "suspended": User.objects.filter(status=User.Status.SUSPENDED).count(),
        },
        "reports": {
            "open": Report.objects.filter(status=Report.Status.OPEN).count(),
            "total": Report.objects.count(),
        },
        "review": _waiting_stats(),
        "top_categories": list(
            listings.filter(status=Listing.Status.PUBLISHED)
            .values("category__name_ar", "category__parent__name_ar")
            .annotate(n=Count("id")).order_by("-n")[:8]
        ),
    })


@extend_schema(summary="البلاغات المفتوحة")
@api_view(["GET"])
@permission_classes([IsStaffRole])
def admin_reports(request):
    queryset = Report.objects.select_related("listing", "reporter").filter(
        status=request.GET.get("status", Report.Status.OPEN)
    )
    paginator = DefaultPagination()
    page = paginator.paginate_queryset(queryset, request)
    data = [
        {
            "id": report.id,
            "reason": report.reason,
            "reason_display": report.get_reason_display(),
            "note": report.note,
            "created_at": report.created_at,
            "status": report.status,
            "listing": {
                "id": report.listing_id,
                "title": report.listing.title,
                "status": report.listing.status,
                "reports_count": report.listing.reports_count,
            },
            "reporter": {
                "id": report.reporter_id,
                "name": report.reporter.name if report.reporter else "—",
            },
        }
        for report in page
    ]
    return paginator.get_paginated_response(data)


@extend_schema(summary="معالجة بلاغ")
@api_view(["POST"])
@permission_classes([IsStaffRole])
def resolve_report(request, pk: int):
    report = Report.objects.filter(pk=pk).first()
    if not report:
        return Response(status=status.HTTP_404_NOT_FOUND)

    action = request.data.get("action", "dismiss")
    report.status = (
        Report.Status.RESOLVED if action == "resolve" else Report.Status.DISMISSED
    )
    report.resolved_by = request.user
    report.resolved_at = timezone.now()
    report.save(update_fields=["status", "resolved_by", "resolved_at"])
    AdminLog.record(request.user, "report_resolve", report, note=action)
    return Response({"ok": True, "status": report.status})


@extend_schema(summary="إدارة المستخدمين")
@api_view(["GET"])
@permission_classes([IsStaffRole])
def admin_users(request):
    queryset = User.objects.annotate(
        listings_total=Count("listings", filter=~Q(listings__status="deleted"))
    )
    search = request.GET.get("q")
    if search:
        queryset = queryset.filter(Q(name__icontains=search) | Q(phone__icontains=search))
    state = request.GET.get("status")
    if state:
        queryset = queryset.filter(status=state)

    paginator = DefaultPagination()
    page = paginator.paginate_queryset(queryset.order_by("-created_at"), request)
    data = [
        {
            "id": user.id,
            "name": user.name,
            "phone": user.display_phone,
            "whatsapp": user.whatsapp_number,
            "role": user.role,
            "status": user.status,
            "language": user.language,
            "listings_total": user.listings_total,
            "listings_approved_count": user.listings_approved_count,
            "auto_publish": user.auto_publish,
            "created_at": user.created_at,
            "last_seen_at": user.last_seen_at,
        }
        for user in page
    ]
    return paginator.get_paginated_response(data)


@extend_schema(summary="تغيير حالة مستخدم")
@api_view(["POST"])
@permission_classes([IsStaffRole])
def set_user_status(request, pk: int):
    user = User.objects.filter(pk=pk).first()
    if not user:
        return Response(status=status.HTTP_404_NOT_FOUND)
    if user.role == User.Role.ADMIN:
        return Response(
            {"error": {"code": "permission_denied", "message": "لا يمكن تعديل حساب مدير."}},
            status=status.HTTP_403_FORBIDDEN,
        )

    new_status = request.data.get("status")
    if new_status not in dict(User.Status.choices):
        return Response(
            {"error": {"code": "validation_error", "message": "حالة غير معروفة."}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user.status = new_status
    user.suspension_reason = request.data.get("reason", "")
    user.save(update_fields=["status", "suspension_reason"])

    mapping = {"suspended": "user_suspend", "banned": "user_ban", "active": "user_activate"}
    AdminLog.record(request.user, mapping[new_status], user, note=user.suspension_reason)
    return Response({"ok": True, "status": user.status})


@extend_schema(summary="منح مستخدم حقّ النشر بلا مراجعة")
@api_view(["POST"])
@permission_classes([IsStaffRole])
def set_user_auto_publish(request, pk: int):
    """
    ثقة تُمنح لشخص بعينه، لا وضع عام.

    نمط `review_mode` يفتح الباب للجميع دفعة واحدة. هذا يفتحه لبائع عرفتَه
    وراجعتَ إعلاناته — فيسقط عنه الانتظار وحده، ويبقى الباقون تحت المراجعة.
    """
    user = User.objects.filter(pk=pk).first()
    if not user:
        return Response(status=status.HTTP_404_NOT_FOUND)

    enabled = bool(request.data.get("auto_publish"))
    user.auto_publish = enabled
    user.save(update_fields=["auto_publish"])

    AdminLog.record(
        request.user,
        "user_auto_publish",
        user,
        note="تفعيل النشر التلقائي" if enabled else "إيقاف النشر التلقائي",
    )
    return Response({"ok": True, "auto_publish": user.auto_publish})


@extend_schema(summary="تعيين كلمة مرور جديدة لمستخدم")
@api_view(["POST"])
@permission_classes([IsAdminRole])
def set_user_password(request, pk: int):
    """
    للعميل الذي نسي كلمته وتواصل مع الإدارة — حين لا تسعفه الاستعادة عبر واتساب.

    للمدير وحده لا للمشرف: من يملك تبديل كلمة أي حساب يملك الدخول إليه.
    وحسابات المدراء خارج هذا الباب — يستعيدها صاحبها بنفسه.

    يُخرج كل أجهزة المستخدم: إن كان أحد آخر يعرف الكلمة القديمة فقد خرج الآن.
    """
    user = User.objects.filter(pk=pk).first()
    if not user:
        return Response(status=status.HTTP_404_NOT_FOUND)
    if user.role == User.Role.ADMIN:
        return Response(
            {"error": {"code": "permission_denied", "message": "لا يمكن تعديل حساب مدير."}},
            status=status.HTTP_403_FORBIDDEN,
        )

    password = str(request.data.get("new_password") or "").strip()
    try:
        validate_password(password, user)
    except DjangoValidationError as exc:
        return Response(
            {"error": {
                "code": "validation_error",
                "message": exc.messages[0],
                "fields": {"new_password": exc.messages},
            }},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user.set_password_and_revoke_sessions(password)
    # الكلمة نفسها لا تُسجَّل — السجلّ يقول من غيّرها ومتى فقط
    AdminLog.record(request.user, "user_password", user)
    return Response({"ok": True})
