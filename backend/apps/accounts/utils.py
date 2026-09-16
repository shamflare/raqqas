"""
تطبيع أرقام الهواتف.

الناس يكتبون الرقم بصيغ كثيرة: 0994123456 · 994 123 456 · +963994123456 · 00963...
نخزّن صيغة واحدة (E.164) وإلا صار للمستخدم الواحد عدة حسابات بلا أن يدري.

التحقّق يقوم على **`phonenumbers`** — نقل بايثون الرسمي لمكتبة `libphonenumber`
من غوغل، وهي نفسها التي تتحقق من الأرقام في أندرويد. كان هنا قبلها جدول يدوي
بخانتين (سوريا وتركيا) يرفض كل ما عداهما، فلم يستطع سوريّ في ألمانيا أو السعودية
أن يسجّل أصلًا. وكتابة جدول عالمي بيدٍ تعني أخطاءً لا تُكتشف إلا حين يعجز مستخدم
في دولة ما عن التسجيل — ولا يخبرنا أحد.
"""

from __future__ import annotations

import phonenumbers
from django.core.exceptions import ValidationError
from phonenumbers import PhoneNumberFormat, PhoneNumberType

#: الدولة المفترضة حين يُكتب الرقم محليًّا بلا رمز دولة (0994…).
DEFAULT_COUNTRY = "SY"

#: ترتيب المحاولة للرقم المحلي العاري. سوريا أولًا ثم تركيا — حيث أهل الرقة.
#: لا يمسّ هذا من يختار دولته من القائمة: اختياره يأتي أولًا دائمًا.
FALLBACK_COUNTRIES = ("SY", "TR")

#: ما نقبله من أنواع الأرقام.
#:
#: الرقم هنا قناة تواصل: زرّ واتساب للمشتري، ورمز استعادة كلمة المرور لصاحبه.
#: الأرضي لا يصلح لواحدة منهما، ورفضه عند التسجيل أرحم من اكتشافه يوم ينسى
#: المستخدم كلمته. و«أرضي أو موبايل» مقبول لأنه ما تقوله المكتبة في دول لا
#: تفصل بينهما في الترقيم — ورفضه كان سيمنع دولًا كاملة.
ACCEPTED_TYPES = frozenset({
    PhoneNumberType.MOBILE,
    PhoneNumberType.FIXED_LINE_OR_MOBILE,
})

_INVALID = "رقم الهاتف غير صحيح — تحقّق من عدد الخانات ومن رمز الدولة."
_NOT_MOBILE = "هذا رقم أرضي. نحتاج رقم موبايل ليصلك رمز التحقق وليتواصل معك المشترون."


def _parse(value: str, region: str | None):
    """يعيد الرقم المُحلَّل أو None — بلا رفع استثناء، فالمنادي يجرّب أكثر من دولة."""
    try:
        return phonenumbers.parse(value, region)
    except phonenumbers.NumberParseException:
        return None


def normalize_phone(raw: str, country: str = DEFAULT_COUNTRY) -> str:
    """
    يعيد الرقم بصيغة E.164 (`+963994123456`) أو يرفع `ValidationError`.

    `country` تلميح لا قيد: يُستعمل حين يُكتب الرقم محليًّا بلا رمز دولة. أما
    الرقم المكتوب بصيغة دولية (`+…` أو `00…`) فدولته من الرقم نفسه.
    """
    if not raw:
        raise ValidationError("رقم الهاتف مطلوب.")

    value = str(raw).strip()
    # «00» بادئة الاتصال الدولي في أوروبا والشرق الأوسط، و«+» ما تفهمه المكتبة
    if value.startswith("00"):
        value = "+" + value[2:]

    if value.startswith("+"):
        candidates = [None]
    else:
        # اختيار المستخدم أولًا، ثم الافتراضات — بلا تكرار لو كان اختياره منها
        candidates = [country] + [c for c in FALLBACK_COUNTRIES if c != country]

    parsed = None
    for region in candidates:
        attempt = _parse(value, region)
        if attempt and phonenumbers.is_valid_number(attempt):
            parsed = attempt
            break

    if parsed is None:
        raise ValidationError(_INVALID)

    # الأرضي **رقم صحيح** عند المكتبة، فلا يُلتقط إلا هنا برسالته الخاصة —
    # وهي الرسالة التي تقول للمستخدم ما يفعل، بخلاف «رقم غير صحيح» المبهمة.
    if phonenumbers.number_type(parsed) not in ACCEPTED_TYPES:
        raise ValidationError(_NOT_MOBILE)

    return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)


def display_phone(e164: str) -> str:
    """
    الصيغة التي يعرفها الناس: `0994 123 456` لرقم محلي، وبرمز الدولة لما عداه.

    تظهر في التطبيق ولوحة الإدارة. الرقم خارج سوريا يُعرض دوليًّا
    (`+49 1512 3456789`) لأن صيغته المحلية بلا رمز دولة لا تعني شيئًا لقارئها هنا.
    """
    if not e164:
        return ""
    parsed = _parse(e164, None)
    if parsed is None:
        return e164
    fmt = (
        PhoneNumberFormat.NATIONAL
        if phonenumbers.region_code_for_number(parsed) == DEFAULT_COUNTRY
        else PhoneNumberFormat.INTERNATIONAL
    )
    return phonenumbers.format_number(parsed, fmt)


def mask_phone(e164: str) -> str:
    """
    `+963 99• ••• 456` — يكفي صاحبه ليتعرّف عليه، ولا يكفي غيره لمعرفته.

    تُستعمل في شاشة استعادة كلمة المرور: المستخدم يحتاج أن يطمئن أن الرمز ذهب
    إلى رقمه هو، وعرض الرقم كاملًا لمن يكتب رقم غيره كان سيحوّل الشاشة إلى
    أداة كشف أرقام.
    """
    parsed = _parse(e164, None) if e164 else None
    if parsed is None:
        return ""

    prefix = f"+{parsed.country_code} "
    rest = list(
        phonenumbers.format_number(parsed, PhoneNumberFormat.INTERNATIONAL)
        .removeprefix(prefix)
    )
    # رمز الدولة ظاهر، وأول خانتين وآخر ثلاث — وما بينها نقاط بالتجميع نفسه
    positions = [i for i, ch in enumerate(rest) if ch.isdigit()]
    for index in positions[2:-3]:
        rest[index] = "•"
    return prefix + "".join(rest)


def whatsapp_link(e164: str, message: str = "") -> str:
    """رابط wa.me — بلا + وبلا فراغات، وإلا لم يفتح على بعض الأجهزة."""
    from urllib.parse import quote

    number = (e164 or "").lstrip("+")
    if not number:
        return ""
    base = f"https://wa.me/{number}"
    return f"{base}?text={quote(message)}" if message else base
