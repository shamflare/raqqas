"""
إرسال رسائل واتساب — طبقة واحدة يختار مزوّدها متغيّر بيئة واحد.

    WHATSAPP_PROVIDER = bot | cloud | log

| القيمة | المزوّد | متى |
|---|---|---|
| `bot`   | خدمة Node جانبية على الخادم (Baileys) | الإنتاج اليوم |
| `cloud` | Meta WhatsApp Cloud API الرسمي | يوم يصير للتطبيق دخل يستحقّ |
| `log`   | يكتب الرسالة في سجلّ الخادم | التطوير والاختبار (الافتراضي) |

الفصل ليس ترفًا معماريًا: مسار البوت **غير رسمي** وقد يُحظر رقمه بلا إنذار،
والانتقال إلى الرسمي يجب أن يكون تبديل متغيّر بيئة لا إعادة كتابة تحت الضغط.

الاتصال بـ`urllib` من المكتبة القياسية لا بـ`requests`: طلبان بسيطان لا
يستحقّان اعتمادًا جديدًا على خادم يُحدَّث يدويًا.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

#: مهلة قصيرة عمدًا: الإرسال يقع داخل طلب HTTP ينتظره المستخدم أمام شاشته.
#: خدمة بوت ساقطة يجب أن تُعلن سقوطها بسرعة لا أن تُجمّد الشاشة.
TIMEOUT = 10


class WhatsAppError(Exception):
    """تعذّر الإرسال. المنادي يُبلغ المستخدم ولا يدّعي أن الرسالة وصلت."""


# ---------------------------------------------------------------- المزوّدون


class Sender:
    name = "base"

    @property
    def configured(self) -> bool:
        return True

    def send(self, to: str, text: str) -> None:  # pragma: no cover - واجهة
        raise NotImplementedError


class LogSender(Sender):
    """لا يرسل شيئًا — يكتب في السجلّ. للتطوير والاختبارات."""

    name = "log"

    def send(self, to: str, text: str) -> None:
        logger.warning("واتساب (غير مفعَّل) → %s :: %s", to, text)


class BotSender(Sender):
    """
    خدمة Node محلية تتكلّم بروتوكول واتساب مباشرة (`deploy/wa-bot`).

    تُصغي على `127.0.0.1` وحدها — لا منفذ مكشوف على الإنترنت — وتطلب رمزًا
    مشتركًا في الترويسة. التفاصيل والتحذيرات في `deploy/WHATSAPP.md`.
    """

    name = "bot"

    @property
    def configured(self) -> bool:
        return bool(settings.WHATSAPP_BOT_URL and settings.WHATSAPP_BOT_TOKEN)

    def send(self, to: str, text: str) -> None:
        _post_json(
            f"{settings.WHATSAPP_BOT_URL.rstrip('/')}/send",
            {"to": to.lstrip("+"), "text": text},
            {"X-Bot-Token": settings.WHATSAPP_BOT_TOKEN},
        )


class CloudSender(Sender):
    """
    Meta WhatsApp Cloud API — المسار الرسمي.

    يرسل **قالبًا** لا نصًّا حرًّا: رسالة يبدأها العمل خارج نافذة الأربع
    والعشرين ساعة لا تمرّ إلا بقالب معتمَد. اسم القالب ولغته في متغيّرات
    البيئة، والرمز يُمرَّر معاملًا في جسم القالب وزرّه.
    """

    name = "cloud"

    @property
    def configured(self) -> bool:
        return bool(settings.WHATSAPP_CLOUD_TOKEN and settings.WHATSAPP_CLOUD_PHONE_ID)

    def send(self, to: str, text: str) -> None:
        _post_json(
            f"https://graph.facebook.com/v21.0/{settings.WHATSAPP_CLOUD_PHONE_ID}/messages",
            {
                "messaging_product": "whatsapp",
                "to": to.lstrip("+"),
                "type": "template",
                "template": {
                    "name": settings.WHATSAPP_CLOUD_TEMPLATE,
                    "language": {"code": settings.WHATSAPP_CLOUD_TEMPLATE_LANG},
                    "components": [
                        {"type": "body", "parameters": [{"type": "text", "text": text}]},
                        {
                            "type": "button",
                            "sub_type": "url",
                            "index": "0",
                            "parameters": [{"type": "text", "text": text}],
                        },
                    ],
                },
            },
            {"Authorization": f"Bearer {settings.WHATSAPP_CLOUD_TOKEN}"},
        )


PROVIDERS = {"log": LogSender, "bot": BotSender, "cloud": CloudSender}


def get_sender() -> Sender:
    """
    المزوّد المُعلَن. مزوّد مُعلَن وغير مضبوط يسقط إلى السجلّ **مع تحذير**
    لا بصمت: خادم يظنّ أنه يرسل وهو لا يرسل أسوأ من خادم يعلن أنه لا يرسل.
    """
    key = (settings.WHATSAPP_PROVIDER or "log").strip().lower()
    sender = PROVIDERS.get(key, LogSender)()
    if not sender.configured:
        logger.error("مزوّد واتساب «%s» مُعلَن لكن مفاتيحه ناقصة — لا إرسال.", key)
        return LogSender()
    return sender


# ---------------------------------------------------------------- الرسائل


def _post_json(url: str, payload: dict, headers: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:300]
        logger.error("واتساب %s ← %s %s", url, exc.code, body)
        raise WhatsAppError(f"HTTP {exc.code}") from exc
    except Exception as exc:
        logger.error("واتساب %s ← %s", url, exc)
        raise WhatsAppError(str(exc)) from exc


# ---------------------------------------------------------------- إدارة البوت


def _bot_request(path: str, method: str = "GET", payload: dict | None = None) -> dict:
    """نداء إداري للخدمة الجانبية — الحالة وفكّ الربط."""
    if not settings.WHATSAPP_BOT_URL or not settings.WHATSAPP_BOT_TOKEN:
        raise WhatsAppError("خدمة واتساب غير مضبوطة على الخادم.")
    url = f"{settings.WHATSAPP_BOT_URL.rstrip('/')}{path}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload or {}).encode("utf-8") if method == "POST" else None,
        headers={
            "Content-Type": "application/json",
            "X-Bot-Token": settings.WHATSAPP_BOT_TOKEN,
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(response.read() or b"{}")
    except urllib.error.URLError as exc:
        # الخدمة موقوفة أو لم تُنصَّب — حالة عادية لا خطأ برمجي
        raise WhatsAppError("خدمة واتساب لا تستجيب — تأكّد أنها تعمل.") from exc
    except Exception as exc:
        logger.error("واتساب (إدارة) %s ← %s", url, exc)
        raise WhatsAppError(str(exc)) from exc


def bot_status() -> dict:
    """
    حالة الربط كما تعرضها لوحة الإدارة: متصل؟ بأي رقم؟ وإلا فرمز QR للمسح.

    يُعاد رمز QR صورةً جاهزة (data URL) لا نصًّا: توليد الصورة في البوت يعني
    أن اللوحة لا تحتاج مكتبة QR ولا يحتاج المتصفّح تحميل شيء من الخارج.
    """
    return _bot_request("/status")


def bot_logout() -> dict:
    """فكّ الربط ومسح الجلسة — يعود البوت فيعرض رمزًا جديدًا."""
    return _bot_request("/logout", method="POST")


#: نصّ رسالة الرمز بثلاث لغات.
#:
#: قصيرة وبلا أي رابط عمدًا — الروابط أكثر ما يُشعل الحظر الآلي على أرقام
#: البوتات، والرمز وحده يكفي. وسطر «إن لم تطلبه» ليس تزيينًا: من يصله رمز لم
#: يطلبه يجب أن يعرف فورًا أنه ليس مطالَبًا بشيء.
RESET_MESSAGE = {
    "ar": "رمز استعادة كلمة المرور في سوق الرقة: {code}\n"
          "صالح {minutes} دقائق. لا تشاركه مع أحد.\n"
          "إن لم تطلبه فتجاهل هذه الرسالة.",
    "tr": "Souq Raqqa şifre sıfırlama kodunuz: {code}\n"
          "{minutes} dakika geçerlidir. Kimseyle paylaşmayın.\n"
          "Bu isteği siz yapmadıysanız yok sayın.",
    "en": "Your Souq Raqqa password reset code: {code}\n"
          "Valid for {minutes} minutes. Do not share it with anyone.\n"
          "If you did not request it, ignore this message.",
}


def send_reset_code(to: str, code: str, *, minutes: int, lang: str = "ar") -> str:
    """
    يرسل رمز الاستعادة ويعيد اسم المزوّد الذي أرسله.

    يرفع `WhatsAppError` إن تعذّر الإرسال — والمنادي **يجب** أن يُبلغ المستخدم
    بالفشل لا أن يقول له «أرسلنا الرمز» وهو لم يُرسل.
    """
    sender = get_sender()
    template = RESET_MESSAGE.get(lang, RESET_MESSAGE["ar"])
    sender.send(to, template.format(code=code, minutes=minutes))
    return sender.name
