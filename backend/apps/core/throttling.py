"""
محدِّدات المعدّل.

⚠️ **لماذا لا نستعمل `ScopedRateThrottle`** — وقد كان المشروع كلّه يستعملها:

```python
# rest_framework/throttling.py
class ScopedRateThrottle(SimpleRateThrottle):
    scope_attr = "throttle_scope"

    def allow_request(self, request, view):
        self.scope = getattr(view, self.scope_attr, None)   # ← يدوس على قيمتنا
        if not self.scope:
            return True                                     # ← بلا أي حدّ
```

هي تقرأ النطاق من **العرض** (`view.throttle_scope`) لا من الصنف. فكتابة
`scope = "auth"` في صنف يرث منها لا أثر لها إطلاقًا: تُمحى عند أول طلب، ثم
يُسمح بالطلب دائمًا. والعروض الدالّيّة (`@api_view`) لا تحمل `throttle_scope`
أصلًا — فكان كل محدِّد في المشروع يُرجع True: الدخول والتسجيل وكشف الأرقام
والنشر والبلاغات، كلّها بلا حدّ، **بلا خطأ ولا تحذير ولا أثر في أي سجلّ**.

هنا النطاق ثابت في الصنف كما يُتوقَّع، و`SimpleRateThrottle.__init__` يقرأ
معدّله من `DEFAULT_THROTTLE_RATES` مباشرة.

**ملاحظة تشغيلية:** العدّ يجري في `django.core.cache`. مع `LocMemCache` وثلاثة
عمّال gunicorn يصير لكل عامل عدّاده، فالحدّ الفعلي ثلاثة أضعاف المكتوب. لهذا
يضبط `03-deploy.sh` مخزنًا مشتركًا في الإنتاج.
"""

from __future__ import annotations

from rest_framework.throttling import SimpleRateThrottle


class FixedScopeThrottle(SimpleRateThrottle):
    """نطاق ثابت — يُعلَن في الصنف الوارث ويبقى كما أُعلن."""

    def get_cache_key(self, request, view):
        # المستخدم المسجَّل يُعدّ بحسابه لا بعنوانه: حدٌّ بالعنوان وحده كان
        # سيجمع كل من خلف نفس مزوّد الإنترنت في عدّاد واحد — وهو الحال الغالب
        # في سوريا حيث تخرج أحياء كاملة من عنوان واحد.
        user = getattr(request, "user", None)
        ident = (
            user.pk
            if user is not None and user.is_authenticated
            else self.get_ident(request)
        )
        return self.cache_format % {"scope": self.scope, "ident": ident}
