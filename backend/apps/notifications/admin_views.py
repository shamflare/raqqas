"""
شاشة واتساب في لوحة الإدارة — ربط الرقم ومتابعته.

**لماذا في اللوحة لا في الطرفية:** ربط الرقم يحتاج هاتفًا في يد صاحبه ليمسح
رمز QR. ومن يملك الرقم ليس بالضرورة من يملك مفتاح SSH ولا من يعرف systemd.
وحين ينقطع الربط — والانقطاع وارد على هذا المسار غير الرسمي — يجب أن تكون
إعادته ضغطةَ زرّ لا جلسةَ طرفية في الثالثة فجرًا.

الخادم هنا **وسيط فقط**: البوت يُصغي على `127.0.0.1` ولا يصله أحد من
الإنترنت، واللوحة تكلّم Django وDjango يكلّم البوت.
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.core.permissions import IsStaffRole

from .whatsapp import WhatsAppError, bot_logout, bot_status, get_sender


def _unavailable(exc: WhatsAppError) -> Response:
    return Response(
        {"error": {"code": "whatsapp_unavailable", "message": str(exc)}},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


@extend_schema(summary="حالة ربط واتساب (ورمز QR إن لم يكن مربوطًا)")
@api_view(["GET"])
@permission_classes([IsStaffRole])
def whatsapp_status(request):
    """
    GET /admin/whatsapp

    اللوحة تستدعيه كل ثانيتين وهي تعرض رمز QR: الرمز يتجدّد عند واتساب كل
    نحو عشرين ثانية، فعرض رمز قديم يعني مسحًا لا ينجح ومستخدمًا يظنّ العطب
    في هاتفه.
    """
    provider = get_sender().name
    if provider != "bot":
        # مزوّد آخر (السحابة) أو لا مزوّد — لا معنى لشاشة ربط QR أصلًا
        return Response({"provider": provider, "manageable": False})

    try:
        state = bot_status()
    except WhatsAppError as exc:
        return _unavailable(exc)
    return Response({"provider": provider, "manageable": True, **state})


@extend_schema(summary="فكّ ربط رقم واتساب")
@api_view(["POST"])
@permission_classes([IsStaffRole])
def whatsapp_logout(request):
    """
    POST /admin/whatsapp/logout — لتبديل الرقم، أو حين يُحظر الحالي.

    يُبلغ واتساب بفكّ الربط ثم يمحو الجلسة، فيعود البوت بعرض رمز جديد فورًا.
    """
    try:
        bot_logout()
    except WhatsAppError as exc:
        return _unavailable(exc)
    return Response({"ok": True})


@extend_schema(summary="إرسال رسالة تجريبية للتأكّد من عمل الربط")
@api_view(["POST"])
@permission_classes([IsStaffRole])
def whatsapp_test(request):
    """
    POST /admin/whatsapp/test {phone}

    الفرق بين «مربوط» و«يرسل فعلًا» ليس نظريًا: الجلسة قد تكون مفتوحة والرقم
    محظورًا من المراسلة. زرّ واحد يحسم الأمر قبل أن يكتشفه مستخدم نسي كلمته.
    """
    from django.core.exceptions import ValidationError

    from apps.accounts.utils import normalize_phone

    try:
        phone = normalize_phone(request.data.get("phone", ""))
    except ValidationError as exc:
        return Response(
            {"error": {"code": "validation_error", "message": exc.messages[0]}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        get_sender().send(
            phone,
            "رسالة تجريبية من لوحة إدارة سوق الرقة ✅\n"
            "وصولها يعني أن استعادة كلمة المرور تعمل.",
        )
    except WhatsAppError as exc:
        return _unavailable(exc)
    return Response({"sent": True, "to": phone})
