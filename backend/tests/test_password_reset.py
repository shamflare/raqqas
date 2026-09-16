"""
استعادة كلمة المرور — المسار كاملًا وحدوده الأمنية.

أهمّ ما هنا ليس «المسار السعيد» بل الحدود: لا كشف عن الأرقام المسجّلة، ولا
تخمين بلا حدّ، ولا بقاء سارق داخلًا بعد أن استعاد صاحب الحساب حسابه.
"""

from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import PasswordResetCode, User
from apps.notifications.whatsapp import WhatsAppError


class ResetBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            phone="0994123456", password="oldpass1234", name="أحمد",
            whatsapp_number="0994123456",
        )

    def setUp(self):
        self.guest = APIClient()
        # المزوّد الحقيقي لا يُنادى في الاختبارات — نلتقط الرمز من الجدول
        self.sent = []
        patcher = patch(
            "apps.accounts.recovery.send_reset_code",
            side_effect=lambda to, code, **kw: self.sent.append((to, code)) or "bot",
        )
        self.send_mock = patcher.start()
        self.addCleanup(patcher.stop)

    # ------------------------------------------------------------ أدوات

    def request_code(self, phone="0994123456"):
        return self.guest.post(
            "/api/v1/auth/password/forgot", {"phone": phone}, format="json"
        )

    def last_code(self) -> str:
        return self.sent[-1][1]

    def full_reset(self, new_password="brandnew4567"):
        self.request_code()
        verify = self.guest.post(
            "/api/v1/auth/password/verify",
            {"phone": "0994123456", "code": self.last_code()},
            format="json",
        )
        assert verify.status_code == 200, verify.data
        return self.guest.post(
            "/api/v1/auth/password/reset",
            {"ticket": verify.data["ticket"], "new_password": new_password},
            format="json",
        )


class HappyPathTests(ResetBase):
    def test_full_flow_changes_password_and_logs_in(self):
        response = self.full_reset()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("access", response.data["tokens"])

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("brandnew4567"))
        self.assertFalse(self.user.check_password("oldpass1234"))

    def test_code_goes_to_the_whatsapp_number_not_the_account_number(self):
        """القناة واتساب — ورقم الحساب قد لا يكون عليه واتساب أصلًا."""
        self.user.whatsapp_number = "+905551234567"
        self.user.save()
        self.request_code()
        self.assertEqual(self.sent[-1][0], "+905551234567")

    def test_response_masks_the_destination(self):
        response = self.request_code()
        masked = response.data["masked"]
        self.assertIn("•", masked)
        self.assertNotIn("994123456", masked.replace(" ", ""))


class EnumerationTests(ResetBase):
    """نموذج الاستعادة يجب ألّا يخبر أحدًا أي الأرقام مسجّل."""

    def test_unknown_number_gets_the_same_response(self):
        known = self.request_code("0994123456")
        unknown = self.request_code("0999888777")

        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(set(known.data), set(unknown.data))
        self.assertTrue(unknown.data["sent"])

    def test_unknown_number_does_not_trigger_a_message(self):
        self.request_code("0999888777")
        self.assertEqual(self.sent, [])

    def test_banned_account_cannot_be_recovered(self):
        """الاستعادة ليست بابًا خلفيًا حول الحظر."""
        self.user.status = User.Status.BANNED
        self.user.save()

        response = self.request_code()
        self.assertTrue(response.data["sent"])   # الردّ محايد كما لغير المسجّل
        self.assertEqual(self.sent, [])          # ولا رسالة تُرسل فعلًا


class CodeSecurityTests(ResetBase):
    def test_wrong_code_is_refused(self):
        self.request_code()
        response = self.guest.post(
            "/api/v1/auth/password/verify",
            {"phone": "0994123456", "code": "000000"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_code_is_burned_after_five_wrong_attempts(self):
        self.request_code()
        code = self.last_code()
        for _ in range(PasswordResetCode.MAX_ATTEMPTS):
            self.guest.post(
                "/api/v1/auth/password/verify",
                {"phone": "0994123456", "code": "000000"},
                format="json",
            )
        # الرمز الصحيح نفسه لم يعد ينفع — وإلا كان الحدّ زينة
        response = self.guest.post(
            "/api/v1/auth/password/verify",
            {"phone": "0994123456", "code": code},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_code_cannot_be_used_twice(self):
        self.request_code()
        code = self.last_code()
        first = self.guest.post(
            "/api/v1/auth/password/verify",
            {"phone": "0994123456", "code": code}, format="json",
        )
        self.assertEqual(first.status_code, 200)
        second = self.guest.post(
            "/api/v1/auth/password/verify",
            {"phone": "0994123456", "code": code}, format="json",
        )
        self.assertEqual(second.status_code, 400)

    def test_expired_code_is_refused(self):
        self.request_code()
        code = self.last_code()
        PasswordResetCode.objects.filter(user=self.user).update(
            expires_at=timezone.now() - timezone.timedelta(seconds=1)
        )
        response = self.guest.post(
            "/api/v1/auth/password/verify",
            {"phone": "0994123456", "code": code}, format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_new_code_invalidates_the_previous_one(self):
        self.request_code()
        first = self.last_code()
        self.request_code()

        response = self.guest.post(
            "/api/v1/auth/password/verify",
            {"phone": "0994123456", "code": first}, format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_code_is_not_stored_in_clear_text(self):
        self.request_code()
        row = PasswordResetCode.objects.get(user=self.user)
        self.assertNotIn(self.last_code(), row.code_hash)
        self.assertEqual(len(row.code_hash), 64)

    def test_send_limit_stops_the_fourth_request_in_an_hour(self):
        for _ in range(PasswordResetCode.MAX_PER_HOUR):
            self.request_code()
        self.assertEqual(len(self.sent), PasswordResetCode.MAX_PER_HOUR)

        response = self.request_code()
        self.assertTrue(response.data["sent"])                       # ردّ محايد
        self.assertEqual(len(self.sent), PasswordResetCode.MAX_PER_HOUR)  # بلا رسالة


class TicketTests(ResetBase):
    def test_reset_without_a_valid_ticket_is_refused(self):
        response = self.guest.post(
            "/api/v1/auth/password/reset",
            {"ticket": "not-a-real-ticket", "new_password": "brandnew4567"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "ticket_expired")

    def test_ticket_dies_when_a_newer_code_is_requested(self):
        """من طلب رمزًا جديدًا ألغى ما قبله — والتذكرة المبنية عليه معه."""
        self.request_code()
        verify = self.guest.post(
            "/api/v1/auth/password/verify",
            {"phone": "0994123456", "code": self.last_code()}, format="json",
        )
        ticket = verify.data["ticket"]

        self.request_code()  # رمز جديد يُبطل الصفّ السابق

        response = self.guest.post(
            "/api/v1/auth/password/reset",
            {"ticket": ticket, "new_password": "brandnew4567"}, format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_short_password_is_refused(self):
        self.request_code()
        verify = self.guest.post(
            "/api/v1/auth/password/verify",
            {"phone": "0994123456", "code": self.last_code()}, format="json",
        )
        response = self.guest.post(
            "/api/v1/auth/password/reset",
            {"ticket": verify.data["ticket"], "new_password": "123"}, format="json",
        )
        self.assertEqual(response.status_code, 400)


class SessionRevocationTests(ResetBase):
    """من استعاد حسابه يجب أن يَخرج من كان داخلًا عليه."""

    def _login(self):
        response = self.guest.post(
            "/api/v1/auth/login",
            {"phone": "0994123456", "password": "oldpass1234"}, format="json",
        )
        assert response.status_code == 200, response.data
        return response.data["tokens"]

    def test_old_access_token_stops_working_after_reset(self):
        stolen = self._login()
        intruder = APIClient()
        intruder.credentials(HTTP_AUTHORIZATION=f"Bearer {stolen['access']}")
        self.assertEqual(intruder.get("/api/v1/auth/me").status_code, 200)

        self.full_reset()

        self.assertEqual(intruder.get("/api/v1/auth/me").status_code, 401)

    def test_old_refresh_token_cannot_mint_a_new_one(self):
        """
        الثغرة التي يسهل نسيانها: مسار التجديد لا يمرّ بالمصادقة إطلاقًا،
        فرمز تجديد قديم كان سيصكّ رمز وصول جديدًا يتجاوز كل الفحوص.
        """
        stolen = self._login()
        self.full_reset()

        response = self.guest.post(
            "/api/v1/auth/refresh", {"refresh": stolen["refresh"]}, format="json"
        )
        self.assertEqual(response.status_code, 401)

    def test_the_recovering_device_stays_logged_in(self):
        """الرموز الجديدة تصدر بعد الختم لا قبله — وإلا خرج صاحب الحساب فورًا."""
        response = self.full_reset()
        fresh = APIClient()
        fresh.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['tokens']['access']}")
        self.assertEqual(fresh.get("/api/v1/auth/me").status_code, 200)

    def test_changing_password_from_inside_also_revokes(self):
        stolen = self._login()
        intruder = APIClient()
        intruder.credentials(HTTP_AUTHORIZATION=f"Bearer {stolen['access']}")

        owner = APIClient()
        owner.credentials(HTTP_AUTHORIZATION=f"Bearer {self._login()['access']}")
        changed = owner.post(
            "/api/v1/auth/password",
            {"current_password": "oldpass1234", "new_password": "brandnew4567"},
            format="json",
        )
        self.assertEqual(changed.status_code, 200, changed.data)
        self.assertEqual(intruder.get("/api/v1/auth/me").status_code, 401)


class DeliveryFailureTests(ResetBase):
    def test_user_is_told_when_the_message_could_not_be_sent(self):
        """لا نقول «أرسلنا» ورسالة لم تُرسل — المستخدم سينتظر ما لا يأتي."""
        self.send_mock.side_effect = WhatsAppError("البوت غير متصل")
        response = self.request_code()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "send_failed")

    def test_failed_code_is_burned(self):
        """رمز لم يصل صاحبه يجب ألّا يبقى صالحًا في الجدول."""
        self.send_mock.side_effect = WhatsAppError("البوت غير متصل")
        self.request_code()

        self.assertIsNone(PasswordResetCode.active_for(self.user))
