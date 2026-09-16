"""
تجديد رمز الدخول — بفحص ختم كلمة المرور.

مفصول عن `tokens.py` لأن ذاك يُحمَّل مع إعدادات DRF نفسها، واستيراد
`rest_framework_simplejwt.views` من داخله يخلق دورة استيراد تمنع الخادم من
الإقلاع أصلًا. هنا يُستورد بأمان: `urls.py` يُحمَّل بعد اكتمال الإعدادات.
"""

from __future__ import annotations

from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .tokens import STALE_MESSAGE, is_stale


class SouqTokenRefreshSerializer(TokenRefreshSerializer):
    """
    التجديد يحتاج فحص الختم مثل المصادقة — وإلا فُتِح باب خلفي.

    `TokenRefreshView` لا يمرّ بالمصادقة إطلاقًا: يتحقق من توقيع رمز التجديد
    ويصكّ رمز وصول جديدًا. فرمز تجديد قديم في يد سارق كان سيصكّ رمز وصول
    بـ`iat` جديد يتجاوز فحص `SouqJWTAuthentication` — أي أن الاستعادة لا تُخرجه.
    """

    def validate(self, attrs):
        from django.contrib.auth import get_user_model

        refresh = RefreshToken(attrs["refresh"])
        user = (
            get_user_model()
            .objects.filter(pk=refresh.payload.get("user_id"))
            .only("id", "password_changed_at")
            .first()
        )
        if user and is_stale(user, refresh.payload):
            raise InvalidToken(STALE_MESSAGE)
        return super().validate(attrs)


class SouqTokenRefreshView(TokenRefreshView):
    serializer_class = SouqTokenRefreshSerializer
