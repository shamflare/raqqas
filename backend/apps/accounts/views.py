"""نقاط المصادقة — التسجيل والدخول والملف الشخصي."""

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.throttling import FixedScopeThrottle

from . import recovery
from .models import Device, User
from .serializers import (
    ChangePasswordSerializer,
    DeviceSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
    UserSerializer,
    VerifyResetCodeSerializer,
    tokens_for,
)


class AuthThrottle(FixedScopeThrottle):
    scope = "auth"


class ResetThrottle(FixedScopeThrottle):
    """
    حدّ على طلبات الاستعادة من مصدر واحد.

    الحدّ الحقيقي لكل حساب في `PasswordResetCode.throttled`، وهذا يقف أمام نوع
    آخر من العبث: من يجرّب **أرقامًا كثيرة** من مكان واحد ليعرف أيّها مسجّل.
    """

    scope = "reset"


class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AuthThrottle]

    @extend_schema(summary="إنشاء حساب", request=RegisterSerializer)
    def post(self, request):
        serializer = RegisterSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {"user": UserSerializer(user).data, "tokens": tokens_for(user)},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AuthThrottle]

    @extend_schema(summary="تسجيل الدخول", request=LoginSerializer)
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        user.touch()
        return Response({"user": UserSerializer(user).data, "tokens": tokens_for(user)})


class MeView(RetrieveUpdateAPIView):
    """GET/PATCH /auth/me — الاسم واللغة ورقم واتساب."""

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def perform_update(self, serializer):
        serializer.save()
        self.request.user.touch()


@extend_schema(summary="تغيير كلمة المرور", request=ChangePasswordSerializer)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([AuthThrottle])
def change_password(request):
    serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    user = request.user
    # يُخرج كل جهاز آخر، ويعيد للجهاز الحالي رموزًا جديدة. من غيّر كلمته لأنه
    # يشكّ أن أحدًا يعرفها يجب أن يخرج ذلك الأحد فعلًا، لا بعد تسعين يومًا.
    user.set_password_and_revoke_sessions(serializer.validated_data["new_password"])
    return Response({"ok": True, "tokens": tokens_for(user)})


# ------------------------------------------------------ استعادة كلمة المرور


def _recovery_error(exc: recovery.RecoveryError) -> Response:
    return Response(
        {"error": {"code": exc.code, "message": exc.message}},
        status=status.HTTP_400_BAD_REQUEST,
    )


@extend_schema(summary="① طلب رمز استعادة كلمة المرور", request=ForgotPasswordSerializer)
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([ResetThrottle])
def forgot_password(request):
    """
    POST /auth/password/forgot — يرسل رمزًا إلى واتساب صاحب الحساب.

    الردّ **واحد** سواء كان الرقم مسجّلًا أم لا (انظر `recovery.request_code`).
    """
    serializer = ForgotPasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        result = recovery.request_code(
            serializer.validated_data["phone"], lang=getattr(request, "lang", "ar")
        )
    except recovery.RecoveryError as exc:
        return _recovery_error(exc)
    return Response(result)


@extend_schema(summary="② التحقّق من رمز الاستعادة", request=VerifyResetCodeSerializer)
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([ResetThrottle])
def verify_reset_code(request):
    """POST /auth/password/verify — يعيد تذكرة قصيرة العمر تُستعمل في الخطوة ③."""
    serializer = VerifyResetCodeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        result = recovery.verify_code(
            serializer.validated_data["phone"], serializer.validated_data["code"]
        )
    except recovery.RecoveryError as exc:
        return _recovery_error(exc)
    return Response(result)


@extend_schema(summary="③ تعيين كلمة مرور جديدة", request=ResetPasswordSerializer)
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([ResetThrottle])
def reset_password(request):
    """
    POST /auth/password/reset — يبدّل الكلمة ويُدخل المستخدم مباشرة.

    الدخول الفوري مقصود: من وصل إلى هنا أثبت ملكيته للرقم قبل قليل، وإعادته
    إلى شاشة الدخول ليكتب ما كتبه للتوّ احتكاك بلا فائدة أمنية.
    """
    serializer = ResetPasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        user = recovery.reset_password(
            serializer.validated_data["ticket"],
            serializer.validated_data["new_password"],
        )
    except recovery.RecoveryError as exc:
        return _recovery_error(exc)
    user.touch()
    return Response({"user": UserSerializer(user).data, "tokens": tokens_for(user)})


@extend_schema(summary="تسجيل جهاز لاستقبال الإشعارات", request=DeviceSerializer)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def register_device(request):
    serializer = DeviceSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    device, _ = Device.objects.update_or_create(
        token=data["token"],
        defaults={
            "user": request.user,
            "platform": data.get("platform", Device.Platform.ANDROID),
            "app_version": data.get("app_version", ""),
            "language": data.get("language", request.user.language),
            "is_active": True,
        },
    )
    return Response({"ok": True, "id": device.id}, status=status.HTTP_201_CREATED)


@extend_schema(summary="إلغاء تسجيل الجهاز (تسجيل خروج)")
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request):
    token = request.data.get("device_token")
    if token:
        Device.objects.filter(token=token, user=request.user).update(is_active=False)
    User.objects.filter(pk=request.user.pk).update(last_seen_at=timezone.now())
    return Response({"ok": True})


@extend_schema(summary="التحقّق من توفّر رقم قبل التسجيل")
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def check_phone(request):
    from django.core.exceptions import ValidationError

    from .utils import normalize_phone

    try:
        phone = normalize_phone(request.data.get("phone", ""))
    except ValidationError as exc:
        return Response(
            {"error": {"code": "validation_error", "message": exc.messages[0]}},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response({"available": not User.objects.filter(phone=phone).exists()})


# ------------------------------------------------------------------ حذف الحساب


@extend_schema(summary="حذف الحساب نهائيًا (من داخل التطبيق)")
@api_view(["DELETE", "POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([AuthThrottle])
def delete_my_account(request):
    """
    DELETE /auth/me/delete — المسار داخل التطبيق.

    نطلب كلمة المرور رغم أن المستخدم مسجَّل الدخول: الحذف لا رجعة فيه،
    وجهاز مفتوح في يد غير صاحبه يجب ألّا يكفي لمحو حساب كامل.
    """
    from .deletion import delete_user_account

    password = str(request.data.get("password") or "")
    if not request.user.check_password(password):
        return Response(
            {"error": {"code": "invalid_password", "message": "كلمة المرور غير صحيحة."}},
            status=status.HTTP_400_BAD_REQUEST,
        )
    result = delete_user_account(request.user, reason="user_request")
    return Response(result)


@extend_schema(summary="حذف الحساب من صفحة الويب العامة")
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def delete_account_web(request):
    """
    POST /auth/delete-account — المسار العام الذي تشترطه Google Play لمن
    لم يعد التطبيق مثبَّتًا عنده. الهوية تُثبت بالرقم وكلمة المرور، فلا
    يستطيع أحد حذف حساب غيره.
    """
    from .deletion import delete_user_account

    serializer = LoginSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data["user"]
    result = delete_user_account(user, reason="web_request")
    return Response(result)


# ------------------------------------------------------------------ حظر المعلنين


@extend_schema(summary="قائمة المحظورين / حظر معلن")
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def blocks(request):
    """
    GET  /auth/blocks            قائمة من حظرتهم
    POST /auth/blocks {user_id}  حظر
    """
    from .models import Block

    if request.method == "GET":
        rows = (
            Block.objects.filter(blocker=request.user)
            .select_related("blocked")
            .order_by("-created_at")
        )
        return Response({
            "results": [
                {"user_id": row.blocked_id, "name": row.blocked.name,
                 "initial": row.blocked.initial, "created_at": row.created_at}
                for row in rows
            ]
        })

    try:
        target_id = int(request.data.get("user_id"))
    except (TypeError, ValueError):
        return Response(
            {"error": {"code": "validation_error", "message": "رقم المستخدم مطلوب."}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if target_id == request.user.pk:
        return Response(
            {"error": {"code": "validation_error", "message": "لا يمكنك حظر نفسك."}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not User.objects.filter(pk=target_id).exists():
        return Response(
            {"error": {"code": "not_found", "message": "المستخدم غير موجود."}},
            status=status.HTTP_404_NOT_FOUND,
        )
    Block.objects.get_or_create(blocker=request.user, blocked_id=target_id)
    return Response({"blocked": True})


@extend_schema(summary="رفع الحظر عن معلن")
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def unblock(request, user_id: int):
    """DELETE /auth/blocks/{user_id} — رقم المستخدم في المسار لا في الجسم، لأن
    جسم طلب DELETE لا تنقله كل العملاء والوسائط بشكل موثوق."""
    from .models import Block

    Block.objects.filter(blocker=request.user, blocked_id=user_id).delete()
    return Response({"blocked": False})
