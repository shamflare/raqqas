"""
إبطال الجلسات القديمة عند تغيير كلمة المرور.

**لماذا يلزم أصلًا:** رمز التجديد يعيش تسعين يومًا (`SIMPLE_JWT`). فمن سُرق
هاتفه أو تسرّبت كلمته واستعاد حسابه، يبقى السارق داخلًا ثلاثة أشهر — واستعادة
لا تُخرج السارق ليست استعادة. وهذا أهمّ ما في مسار «نسيت كلمة المرور»: لولاه
لكان المسار بابًا يفتحه صاحب الحساب على نفسه.

**لماذا بهذه الطريقة:** رموز JWT بلا حالة على الخادم. الطريق المعتاد هو تطبيق
`token_blacklist` بجدولَيه، وفيه عيب قاتل هنا: لا يسجّل إلا الرموز الصادرة
**بعد** تنصيبه، فكل رمز في يد مستخدم اليوم يبقى خارج متناوله إلى الأبد. وهذا
تحديدًا الرموز التي نريد إبطالها.

فنقارن `iat` (لحظة إصدار الرمز) بـ`password_changed_at`. ختمٌ واحد على صفّ
المستخدم يُبطل كل ما صدر قبله دفعةً واحدة — القديم والجديد، بلا جدول ولا ترحيل
ولا استعلام إضافي (المستخدم محمَّل أصلًا).
"""

from __future__ import annotations

# ⚠️ لا تستورد هنا أي شيء من `rest_framework.views` أو
# `rest_framework_simplejwt.views`: هذا الملف يُحمَّل من
# `REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]`، و`rest_framework.views`
# يقرأ ذلك الإعداد أثناء تحميله هو — فتنشأ دورة استيراد تُسقط الخادم عند
# الإقلاع. لهذا يعيش عرض التجديد في `refresh.py` وحده.
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

STALE_MESSAGE = "تم تغيير كلمة المرور — سجّل الدخول من جديد."


def is_stale(user, payload) -> bool:
    """هل صدر هذا الرمز قبل آخر تغيير لكلمة المرور؟"""
    changed_at = getattr(user, "password_changed_at", None)
    if not changed_at:
        return False
    issued_at = payload.get("iat")
    if issued_at is None:
        # رمز بلا `iat` لا يمكن تأريخه — نرفضه بدل أن نمنحه ثقة لا نستطيع فحصها
        return True
    return int(issued_at) < int(changed_at.timestamp())


class SouqJWTAuthentication(JWTAuthentication):
    """المصادقة الافتراضية — تضيف فحص الختم إلى فحص التوقيع."""

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if is_stale(user, validated_token.payload):
            raise InvalidToken(STALE_MESSAGE)
        return user
