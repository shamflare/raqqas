"""
القيم الافتراضية للتصميم — منقولة حرفيًا من design/assets/css/style.css

⚠️ قاعدة ملزمة (plan2 §4): لا يُكتب لون أو قياس في أي مكان آخر من المشروع.
هذه هي المصدر الوحيد، ومنها تبدأ لوحة الإدارة ومنها يقرأ التطبيق.

الإضافة الوحيدة على قائمة style.css: المفتاح `brandText`.

السبب: `--brand` في التصميم يؤدّي دورين متعارضين — مرة **خلفية** (الترويسة،
الأزرار، زر «أضف إعلان») ومرة **نصًّا** (السعر، التبويب النشط، الروابط).
في الوضع النهاري لون واحد يكفي للدورين. في الوضع الليلي لا يكفي:
  · لو أبقيناه داكنًا (#0B7A5D) فالنص عليه مقروء، لكنه كنصّ على البطاقة
    الداكنة يعطي 3.1:1 — والسعر يصير شبه غير مقروء.
  · ولو فتّحناه (#12A87E) صار النص على البطاقة ممتازًا، لكن الأبيض فوقه
    في الترويسة يهبط إلى 3.0:1.
لذلك فصلنا الدورين: `brand` للخلفيات و`brandText` للنصوص. في الوضع النهاري
الاثنان متطابقان، فلا يتغيّر شيء عن التصميم الأصلي إطلاقًا.
"""

# ------------------------------------------------------------------ الألوان

DEFAULT_THEME_LIGHT = {
    # العلامة
    "brand": "#0B7A5D",        # خلفية: الترويسة والأزرار
    "brandText": "#0B7A5D",    # نص: السعر والتبويب النشط والروابط
    "brand600": "#096A51",
    "brand700": "#075642",
    "brand50": "#E6F4EF",
    "brand100": "#C7E7DC",
    # التمييز
    "gold": "#E8940C",
    "gold50": "#FDF3E2",
    # الحالات
    "danger": "#DC2626",
    "danger50": "#FEE9E9",
    "success": "#15803D",
    "success50": "#E7F6EC",
    "info": "#1D4ED8",
    "info50": "#E8EEFC",
    # الأسطح
    "bg": "#F4F6F5",
    "surface": "#FFFFFF",
    "surface2": "#FAFBFB",
    "line": "#E4E8E6",
    # النصوص
    "ink": "#111C18",
    "ink2": "#55605B",
    "ink3": "#8B958F",
    # نص فوق الأسطح الملوّنة
    "onBrand": "#FFFFFF",
    "onGold": "#2A1B00",
}

DEFAULT_THEME_DARK = {
    **DEFAULT_THEME_LIGHT,
    "brand": "#0B7A5D",        # كما في style.css — الأبيض فوقه مقروء (5.2:1)
    "brandText": "#12A87E",    # مفتّح للنصوص فوق الأسطح الداكنة (5.4:1)
    "brand600": "#096A51",
    "brand700": "#075642",
    "brand50": "#12312A",
    "brand100": "#17463B",
    "gold50": "#3A2A0E",
    "danger50": "#3A1A1A",
    "success50": "#12301F",
    "info50": "#16224A",
    "bg": "#0F1513",
    "surface": "#172220",
    "surface2": "#1D2A27",
    "line": "#26332F",
    "ink": "#EAF0ED",
    "ink2": "#A9B5B0",
    "ink3": "#77837E",
}

# مفاتيح الألوان التي تعرضها لوحة الإدارة، مرتّبة في مجموعات
THEME_COLOR_GROUPS = [
    {"key": "brand", "label_ar": "العلامة", "label_tr": "Marka", "label_en": "Brand",
     "keys": ["brand", "brandText", "brand600", "brand700", "brand50", "brand100", "onBrand"]},
    {"key": "accent", "label_ar": "التمييز", "label_tr": "Vurgu", "label_en": "Accent",
     "keys": ["gold", "gold50", "onGold"]},
    {"key": "state", "label_ar": "الحالات", "label_tr": "Durumlar", "label_en": "States",
     "keys": ["danger", "danger50", "success", "success50", "info", "info50"]},
    {"key": "surface", "label_ar": "الأسطح", "label_tr": "Yüzeyler", "label_en": "Surfaces",
     "keys": ["bg", "surface", "surface2", "line"]},
    {"key": "ink", "label_ar": "النصوص", "label_tr": "Metinler", "label_en": "Text",
     "keys": ["ink", "ink2", "ink3"]},
]

# ------------------------------------------------------------------ الأبعاد

DEFAULT_RADIUS = {"sm": 8, "md": 12, "lg": 18, "xl": 24, "full": 999}

SHADOW_PRESETS = ["flat", "soft", "strong"]

DENSITY_PRESETS = ["compact", "normal", "comfortable"]

# الخطوط المحزومة داخل التطبيق (plan2 §7 — لا تنزيل خطوط من الإنترنت)
BUNDLED_FONTS = ["Cairo", "Tajawal", "Almarai", "NotoKufiArabic", "IBMPlexSansArabic"]

# ------------------------------------------------------------------ سمات جاهزة

THEME_PRESETS = [
    {
        "key": "green",
        "name_ar": "الأخضر (الافتراضي)", "name_tr": "Yeşil", "name_en": "Green",
        "light": {"brand": "#0B7A5D", "brandText": "#0B7A5D", "brand600": "#096A51",
                  "brand700": "#075642", "brand50": "#E6F4EF", "brand100": "#C7E7DC"},
        "dark": {"brand": "#0B7A5D", "brandText": "#12A87E", "brand600": "#096A51",
                 "brand700": "#075642", "brand50": "#12312A", "brand100": "#17463B"},
    },
    {
        "key": "blue",
        "name_ar": "الأزرق", "name_tr": "Mavi", "name_en": "Blue",
        "light": {"brand": "#1663B0", "brandText": "#1663B0", "brand600": "#12559A",
                  "brand700": "#0E447C", "brand50": "#E7F0FA", "brand100": "#C6DCF3"},
        "dark": {"brand": "#1663B0", "brandText": "#63AEEF", "brand600": "#12559A",
                 "brand700": "#0E447C", "brand50": "#122437", "brand100": "#16324B"},
    },
    {
        "key": "purple",
        "name_ar": "البنفسجي", "name_tr": "Mor", "name_en": "Purple",
        "light": {"brand": "#6D3BB5", "brandText": "#6D3BB5", "brand600": "#5D319C",
                  "brand700": "#4A2780", "brand50": "#F0E9FA", "brand100": "#DCCBF3"},
        "dark": {"brand": "#6D3BB5", "brandText": "#B48FE8", "brand600": "#5D319C",
                 "brand700": "#4A2780", "brand50": "#241734", "brand100": "#33224A"},
    },
    {
        "key": "darkgold",
        "name_ar": "الذهبي الداكن", "name_tr": "Koyu Altın", "name_en": "Dark Gold",
        "light": {"brand": "#8A6410", "brandText": "#8A6410", "brand600": "#75540D",
                  "brand700": "#5C420A", "brand50": "#F8F1DF", "brand100": "#EEDFB8"},
        "dark": {"brand": "#8A6410", "brandText": "#DDB251", "brand600": "#75540D",
                 "brand700": "#5C420A", "brand50": "#332809", "brand100": "#4A3A11"},
    },
    {
        "key": "maroon",
        "name_ar": "العنّابي", "name_tr": "Bordo", "name_en": "Maroon",
        "light": {"brand": "#98243C", "brandText": "#98243C", "brand600": "#821E33",
                  "brand700": "#68172A", "brand50": "#FAE9EC", "brand100": "#F1C8D0"},
        "dark": {"brand": "#98243C", "brandText": "#E4738B", "brand600": "#821E33",
                 "brand700": "#68172A", "brand50": "#331017", "brand100": "#4A1721"},
    },
]

# ------------------------------------------------------------------ العملة

DEFAULT_CURRENCY = {
    "code": "SYP",
    "symbol": "ل.س",
    "position": "after",   # after | before
    "decimals": 0,
}


# ------------------------------------------------------------------ الصفحة التعريفية

def default_landing(lang: str = "ar") -> dict:
    """نصوص الصفحة التعريفية الأولية — الأدمن يعدّلها من اللوحة."""
    texts = {
        "ar": {
            "headline": "سوق الرقة — بيع واشترِ داخل مدينتك",
            "subline": "كل ما تحتاجه من أهل مدينتك، بلا وسيط وبلا شحن.",
            "body": "حمّل التطبيق وتصفّح آلاف الإعلانات في السيارات والعقارات "
                    "والموبايلات والأثاث… وانشر إعلانك مجانًا خلال دقيقة.",
            "cta": "حمّل التطبيق",
            "features": [
                {"icon": "🔎", "title": "ابحث بسهولة", "text": "أقسام وأحياء ومرشّحات واضحة."},
                {"icon": "📸", "title": "انشر مجانًا", "text": "صور وسعر ووصف — ودقيقة واحدة."},
                {"icon": "💬", "title": "تواصل مباشرة", "text": "راسل البائع على واتساب فورًا."},
            ],
        },
        "tr": {
            "headline": "Rakka Pazarı — Şehrinde al ve sat",
            "subline": "İhtiyacın olan her şey, şehrindeki komşularından.",
            "body": "Uygulamayı indir; araba, emlak, telefon ve mobilya "
                    "ilanlarına göz at, kendi ilanını bir dakikada ücretsiz yayınla.",
            "cta": "Uygulamayı indir",
            "features": [
                {"icon": "🔎", "title": "Kolay arama", "text": "Net kategoriler, mahalleler ve filtreler."},
                {"icon": "📸", "title": "Ücretsiz ilan", "text": "Fotoğraf, fiyat, açıklama — bir dakika."},
                {"icon": "💬", "title": "Doğrudan iletişim", "text": "Satıcıya WhatsApp'tan hemen yaz."},
            ],
        },
        "en": {
            "headline": "Souq Raqqa — Buy and sell in your city",
            "subline": "Everything you need, from people in your own city.",
            "body": "Download the app to browse thousands of listings — cars, "
                    "real estate, phones, furniture — and post your own for free in a minute.",
            "cta": "Download the app",
            "features": [
                {"icon": "🔎", "title": "Search easily", "text": "Clear categories, neighborhoods and filters."},
                {"icon": "📸", "title": "Post for free", "text": "Photos, price, description — one minute."},
                {"icon": "💬", "title": "Contact directly", "text": "Message the seller on WhatsApp instantly."},
            ],
        },
    }
    return texts.get(lang, texts["ar"])


# ------------------------------------------------------------------ المزايا

DEFAULT_FEATURES = {
    "chat_enabled": False,          # المحادثة الداخلية — بعد الإطلاق (plan2 §7.4)
    "whatsapp_enabled": True,       # زر واتساب — النسخة الأولى
    "featured_enabled": False,      # الإعلانات المميزة المدفوعة
    "ratings_enabled": False,       # التقييم ⭐
    "guest_browsing": True,         # التصفّح بلا تسجيل (قرار 17)
    "guest_favorites": True,        # المفضلة محليًا للزائر ثم تُدمج عند الدخول
    "phone_verification": False,    # تحقق الهاتف — طبقة مجرّدة جاهزة (plan2 §9 قرار 7)
    "show_view_counts": True,
    "show_listing_counts": True,
}

# القيم الافتراضية للحدود التشغيلية
DEFAULT_LIMITS = {
    "listing_expiry_days": 60,
    "daily_listing_limit": 5,
    "max_photos_per_listing": 10,
    "max_video_seconds": 60,
    "max_video_mb": 100,
    "min_description_length": 10,
}
