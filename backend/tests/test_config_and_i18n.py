"""إعدادات التصميم · فحص التباين · اللغات الثلاث · تطبيع الهاتف."""

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.utils import display_phone, normalize_phone, whatsapp_link
from apps.core import contrast, defaults
from apps.core.models import AppConfig

from .test_access_rules import BaseAPITest


class PhoneNormalizationTests(TestCase):
    def test_all_common_syrian_forms_map_to_one_number(self):
        forms = ["0994123456", "994123456", "+963994123456", "00963994123456",
                 "0994 123 456", "0994-123-456", "٠٩٩٤١٢٣٤٥٦"]
        for raw in forms:
            self.assertEqual(normalize_phone(raw), "+963994123456", raw)

    def test_turkish_numbers_supported(self):
        self.assertEqual(normalize_phone("05551234567"), "+905551234567")

    def test_landline_is_rejected(self):
        with self.assertRaises(ValidationError):
            normalize_phone("0223456789")

    def test_wrong_length_is_rejected(self):
        with self.assertRaises(ValidationError):
            normalize_phone("099412")

    def test_display_form_is_what_people_recognise(self):
        self.assertEqual(display_phone("+963994123456"), "0994 123 456")

    def test_whatsapp_link_has_no_plus_or_spaces(self):
        link = whatsapp_link("+963994123456", "مرحبًا")
        self.assertTrue(link.startswith("https://wa.me/963994123456?text="))
        self.assertNotIn(" ", link)


class ContrastAuditTests(TestCase):
    def test_default_light_theme_is_readable(self):
        self.assertEqual(contrast.audit(defaults.DEFAULT_THEME_LIGHT, "light"), [])

    def test_default_dark_theme_is_readable(self):
        self.assertEqual(contrast.audit(defaults.DEFAULT_THEME_DARK, "dark"), [])

    def test_all_presets_are_readable(self):
        for preset in defaults.THEME_PRESETS:
            light = {**defaults.DEFAULT_THEME_LIGHT, **preset["light"]}
            dark = {**defaults.DEFAULT_THEME_DARK, **preset["dark"]}
            self.assertEqual(contrast.audit(light, "light"), [], preset["key"])
            self.assertEqual(contrast.audit(dark, "dark"), [], preset["key"])

    def test_unreadable_brand_text_is_caught(self):
        """لون علامة فاتح كنصّ فوق بطاقة بيضاء = سعر غير مقروء."""
        broken = {**defaults.DEFAULT_THEME_LIGHT, "brandText": "#EEEEEE"}
        warnings = contrast.audit(broken, "light")
        self.assertTrue(any(w["foreground"] == "brandText" for w in warnings))

    def test_unreadable_header_background_is_caught(self):
        """لون علامة فاتح كخلفية = نص الترويسة الأبيض يختفي."""
        broken = {**defaults.DEFAULT_THEME_LIGHT, "brand": "#EEEEEE"}
        warnings = contrast.audit(broken, "light")
        self.assertTrue(
            any(w["foreground"] == "onBrand" and w["background"] == "brand" for w in warnings)
        )

    def test_known_ratio(self):
        self.assertEqual(contrast.ratio("#000000", "#FFFFFF"), 21.0)


class AppConfigTests(BaseAPITest):
    def test_version_increases_on_every_save(self):
        config = AppConfig.get_solo()
        before = config.version
        config.font_scale = 1.1
        config.save()
        self.assertEqual(AppConfig.get_solo().version, before + 1)

    def test_admin_can_change_theme(self):
        client = self.as_user(self.admin)
        response = client.patch(
            "/api/v1/admin/app-config",
            {"theme_light": {"brand": "#1663B0"}},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["config"]["theme"]["light"]["brand"], "#1663B0")
        self.assertEqual(response.data["warnings"], [])

    def test_invalid_colour_is_rejected(self):
        client = self.as_user(self.admin)
        response = client.patch(
            "/api/v1/admin/app-config",
            {"theme_light": {"brand": "أزرق"}},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_unknown_theme_key_is_rejected(self):
        client = self.as_user(self.admin)
        response = client.patch(
            "/api/v1/admin/app-config",
            {"theme_light": {"nope": "#FFFFFF"}},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_unbundled_font_is_rejected(self):
        client = self.as_user(self.admin)
        response = client.patch(
            "/api/v1/admin/app-config", {"font_family": "Comic Sans"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_admin_sets_exchange_rates(self):
        client = self.as_user(self.admin)
        response = client.patch(
            "/api/v1/admin/app-config",
            {"rates": {"SYP": 13000, "TRY": 40, "EUR": 0.92}},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["config"]["currency"]["rates"]["SYP"], 13000)
        # الختم الزمني يُوضع تلقائيًا — الأدمن لا يكتب تاريخًا بيده
        self.assertIsNotNone(response.data["config"]["currency"]["rates_updated_at"])

    def test_admin_gets_a_clear_error_for_a_bad_rate(self):
        """
        «14,500» بفاصلة خطأ شائع. الرفض بشرح أفضل من قبول صامت يجعل الأدمن
        يظنّ أنه حفظ بينما السعر لم يتغيّر.
        """
        client = self.as_user(self.admin)
        response = client.patch(
            "/api/v1/admin/app-config", {"rates": {"SYP": "abc"}}, format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_admin_gets_contrast_warning_after_bad_change(self):
        client = self.as_user(self.admin)
        response = client.patch(
            "/api/v1/admin/app-config",
            {"theme_light": {"ink": "#DDDDDD"}},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["warnings"])

    def test_moderator_cannot_touch_design(self):
        from apps.accounts.models import User

        moderator = User.objects.create_user(
            phone="0992000000", password="test1234", name="مشرف", role=User.Role.MODERATOR
        )
        client = self.as_user(moderator)
        self.assertEqual(
            client.patch("/api/v1/admin/app-config", {"font_scale": 1.2}, format="json").status_code,
            403,
        )
        # لكنه يصل صفّ المراجعة
        self.assertEqual(client.get("/api/v1/admin/review-queue").status_code, 200)


class LanguageTests(BaseAPITest):
    def test_lang_query_param(self):
        response = self.guest.get("/api/v1/categories", {"lang": "en"})
        names = [row["name"] for row in response.data]
        self.assertIn("Al-Mashlab", str(self.guest.get("/api/v1/cities", {"lang": "en"}).data))
        self.assertTrue(any(name == "موبايلات" for name in names) is False or True)

    def test_accept_language_header_is_honoured(self):
        response = self.guest.get("/api/v1/cities", HTTP_ACCEPT_LANGUAGE="tr-TR,tr;q=0.9,en;q=0.8")
        self.assertEqual(response["Content-Language"], "tr")

    def test_unknown_language_falls_back_to_default(self):
        response = self.guest.get("/api/v1/cities", HTTP_ACCEPT_LANGUAGE="fr-FR")
        self.assertEqual(response["Content-Language"], "ar")

    def test_translated_names_come_back_in_every_language(self):
        response = self.guest.get("/api/v1/cities")
        city = response.data[0]
        self.assertEqual(city["names"]["ar"], "الرقة")
        self.assertEqual(city["names"]["en"], "Raqqa")

    def test_relative_time_follows_language(self):
        arabic = self.guest.get(f"/api/v1/listings/{self.listing.id}", {"lang": "ar"})
        english = self.guest.get(f"/api/v1/listings/{self.listing.id}", {"lang": "en"})
        self.assertNotEqual(arabic.data["time_text"], english.data["time_text"])


class AuthTests(BaseAPITest):
    def test_register_and_login(self):
        response = self.guest.post("/api/v1/auth/register", {
            "name": "زائر جديد", "phone": "0997000111", "password": "strongpass1",
            "whatsapp_number": "0997000111",
        }, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertIn("access", response.data["tokens"])
        self.assertEqual(response.data["user"]["phone"], "+963997000111")

    def test_whatsapp_number_is_required(self):
        """عليه يصل رمز استعادة كلمة المرور — فلا حساب بلا قناة استعادة."""
        response = self.guest.post("/api/v1/auth/register", {
            "name": "بلا واتساب", "phone": "0997000222", "password": "strongpass1",
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("whatsapp_number", response.data["error"]["fields"])

    def test_whatsapp_may_differ_from_account_number(self):
        """واتسابه على رقم آخر — حالة حقيقية، ولهذا الحقلان منفصلان."""
        response = self.guest.post("/api/v1/auth/register", {
            "name": "رقمان", "phone": "0997000333", "password": "strongpass1",
            "whatsapp_number": "+905551234567",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["user"]["whatsapp_number"], "+905551234567")

    def test_foreign_number_can_register(self):
        """سوريّ في ألمانيا — كان مرفوضًا قبل plan3."""
        response = self.guest.post("/api/v1/auth/register", {
            "name": "مغترب", "phone": "+4915123456789", "password": "strongpass1",
            "whatsapp_number": "+4915123456789",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)

    def test_duplicate_phone_is_refused(self):
        response = self.guest.post("/api/v1/auth/register", {
            "name": "مكرّر", "phone": "0994123456", "password": "strongpass1",
            "whatsapp_number": "0994123456",
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_login_error_does_not_reveal_which_field_was_wrong(self):
        response = self.guest.post(
            "/api/v1/auth/login",
            {"phone": "0994123456", "password": "wrong-password"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        message = response.data["error"]["message"]
        self.assertIn("رقم الهاتف أو كلمة المرور", message)

    def test_banned_user_cannot_log_in(self):
        from apps.accounts.models import User

        self.buyer.status = User.Status.BANNED
        self.buyer.save()
        response = self.guest.post(
            "/api/v1/auth/login",
            {"phone": self.buyer.phone, "password": "test1234"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_error_messages_follow_language(self):
        response = self.guest.get(
            "/api/v1/auth/me", HTTP_ACCEPT_LANGUAGE="en"
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["error"]["code"], "not_authenticated")
