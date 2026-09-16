"""
منطق استعادة كلمة المرور — مفصول عن المسارات ليُختبر وحده.

ثلاث خطوات: طلب رمز ← التحقّق منه مقابل تذكرة ← تبديل الكلمة بالتذكرة.

**القرار الحاكم: لا نكشف أي الأرقام مسجّل.** `request_code` يعيد الردّ نفسه
لرقم مسجّل ولرقم لا وجود له. رسالة «هذا الرقم غير مسجّل» تحوّل نموذج الاستعادة
إلى أداة مجانية لجرد أرقام مستخدمي التطبيق، وهي أرقام أناس حقيقيين في مدينة
صغيرة.
"""

from __future__ import annotations

import logging

from django.core import signing
from django.utils import timezone

from apps.notifications.whatsapp import WhatsAppError, send_reset_code

from .models import PasswordResetCode, User
from .utils import mask_phone

logger = logging.getLogger(__name__)

#: عمر التذكرة بين الخطوتين ② و③ — يكفي لكتابة كلمة مرور، ولا يزيد.
TICKET_TTL = 10 * 60
TICKET_SALT = "souq.password-reset"


class RecoveryError(Exception):
    """فشل يُبلَّغ به المستخدم. `code` يميّز الحالة للتطبيق."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------------------------------------------------------- ① طلب الرمز


def request_code(phone: str, lang: str = "ar") -> dict:
    """
    يولّد رمزًا ويرسله عبر واتساب. يعيد ما يُعرض للمستخدم.

    الردّ واحد في كل الحالات التي لا تكشف شيئًا — رقم غير مسجّل، حساب محظور،
    تجاوز حدّ الإرسال — فلا يستنتج أحد من الشاشة شيئًا عن حساب غيره.
    """
    user = User.objects.filter(phone=phone).first()

    # الردّ المحايد: نفس الشكل ونفس المفاتيح ونفس الرقم المقنَّع الذي أدخله.
    blind = {"sent": True, "masked": mask_phone(phone), "expires_in": int(
        PasswordResetCode.TTL.total_seconds()
    )}

    if user is None or user.status == User.Status.BANNED:
        # الحساب المحظور لا يُستعاد: الاستعادة ليست بابًا خلفيًا حول الحظر
        logger.info("طلب استعادة لرقم غير مؤهَّل — ردّ محايد")
        return blind

    if PasswordResetCode.throttled(user):
        # وصلته ثلاث رسائل في ساعة. لا نرسل رابعة، ولا نقول له إن رقمه مسجّل.
        logger.warning("تجاوز حدّ إرسال رموز الاستعادة: %s", user.pk)
        return blind

    destination = user.contact_number
    row, code = PasswordResetCode.issue(user, sent_to=destination)

    try:
        provider = send_reset_code(
            destination,
            code,
            minutes=int(PasswordResetCode.TTL.total_seconds() // 60),
            lang=user.language or lang,
        )
    except WhatsAppError as exc:
        # لا نكذب: رمز لم يُرسل يجب ألّا يُقال عنه «أُرسل»، وإلا انتظر المستخدم
        # رسالة لن تأتي. ونحرق الرمز فلا يبقى صالحًا بلا أن يعرفه أحد.
        row.consumed_at = timezone.now()
        row.save(update_fields=["consumed_at"])
        logger.error("تعذّر إرسال رمز الاستعادة إلى %s: %s", mask_phone(destination), exc)
        raise RecoveryError(
            "send_failed", "تعذّر إرسال الرمز الآن. حاول بعد قليل."
        ) from exc

    if provider == "log":
        # المزوّد المعطّل ينجح شكليًا ولا يرسل شيئًا — إعلانه في السجلّ يمنع
        # ساعات بحث عن رسالة لم تُرسل أصلًا
        logger.warning("رمز الاستعادة لم يُرسل فعلًا (WHATSAPP_PROVIDER=log)")

    # نعرض **وجهة الإرسال** لا الرقم المُدخَل.
    #
    # مقايضة مقصودة: من واتسابه على رقم آخر يجب أن يعرف على أي هاتف ينتظر، وإلا
    # حدّق في الجهاز الخطأ حتى تنتهي الدقائق الخمس. ثمنها تسريب ضيّق — من يُدخل
    # رقمًا ويرى قناعًا مختلفًا يستنتج أنه مسجّل وأن واتسابه على رقم غيره. لا
    # يمسّ هذا الأغلبية (رقم واحد لكليهما، فالقناع واحد)، ولا يكشف رقمًا كاملًا،
    # ويستلزم معرفة الرقم المستهدَف سلفًا.
    return {**blind, "masked": mask_phone(destination)}


# ---------------------------------------------------------------- ② التحقّق


def verify_code(phone: str, code: str) -> dict:
    """يعيد `{"ticket": …}` أو يرفع `RecoveryError`."""
    invalid = RecoveryError("invalid_code", "الرمز غير صحيح أو انتهت صلاحيته.")

    user = User.objects.filter(phone=phone).first()
    if user is None or user.status == User.Status.BANNED:
        raise invalid

    row = PasswordResetCode.active_for(user)
    if row is None:
        raise invalid

    if not row.verify(code):
        if row.attempts_left == 0:
            raise RecoveryError(
                "too_many_attempts",
                "محاولات كثيرة خاطئة. اطلب رمزًا جديدًا.",
            )
        raise RecoveryError(
            "invalid_code",
            f"الرمز غير صحيح. بقيت لك {row.attempts_left} محاولات.",
        )

    return {
        "ticket": signing.dumps(
            {"user": user.pk, "code": row.pk}, salt=TICKET_SALT
        ),
        "expires_in": TICKET_TTL,
    }


# ---------------------------------------------------------------- ③ التبديل


def reset_password(ticket: str, new_password: str) -> User:
    """يبدّل كلمة المرور ويُخرج كل الأجهزة الأخرى. يعيد المستخدم."""
    expired = RecoveryError("ticket_expired", "انتهت صلاحية الطلب. ابدأ من جديد.")

    try:
        payload = signing.loads(ticket, salt=TICKET_SALT, max_age=TICKET_TTL)
    except signing.BadSignature as exc:
        raise expired from exc

    user = User.objects.filter(pk=payload.get("user")).first()
    if user is None or user.status == User.Status.BANNED:
        raise expired

    # التذكرة مربوطة بصفّ الرمز نفسه، ويجب أن يكون **آخر** رمز صدر للحساب.
    #
    # لا يكفي أن يكون الصفّ مستهلَكًا: من تحقّق من رمزه ثم طلب رمزًا جديدًا يكون
    # قد أعلن أن المحاولة الأولى لم تعد هي المحاولة. إبقاء تذكرتها حيّة عشر
    # دقائق بعد ذلك نافذةٌ لا يحتاجها أحد — وأي نافذة لا يحتاجها أحد تُغلق.
    latest = PasswordResetCode.objects.filter(user=user).order_by("-created_at").first()
    row = PasswordResetCode.objects.filter(
        pk=payload.get("code"), user=user, consumed_at__isnull=False
    ).first()
    if row is None or latest is None or row.pk != latest.pk:
        raise expired

    user.set_password_and_revoke_sessions(new_password)
    logger.info("استُعيدت كلمة مرور الحساب %s", user.pk)
    return user
