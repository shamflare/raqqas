from django.urls import path

from . import views
from .refresh import SouqTokenRefreshView

urlpatterns = [
    path("register", views.RegisterView.as_view(), name="register"),
    path("login", views.LoginView.as_view(), name="login"),
    # نسختنا لا نسخة simplejwt: التجديد يجب أن يرفض رمزًا صدر قبل آخر تغيير
    # لكلمة المرور، وإلا صكّ السارق لنفسه رمز وصول جديدًا بعد الاستعادة.
    path("refresh", SouqTokenRefreshView.as_view(), name="token-refresh"),
    path("logout", views.logout, name="logout"),
    path("me", views.MeView.as_view(), name="me"),
    path("password", views.change_password, name="change-password"),

    # استعادة كلمة المرور — ثلاث خطوات (plan3 §3.6)
    path("password/forgot", views.forgot_password, name="password-forgot"),
    path("password/verify", views.verify_reset_code, name="password-verify"),
    path("password/reset", views.reset_password, name="password-reset"),
    path("device", views.register_device, name="register-device"),
    path("check-phone", views.check_phone, name="check-phone"),

    # حذف الحساب — مساران إلزاميان في Google Play: داخل التطبيق وعبر الويب
    path("me/delete", views.delete_my_account, name="delete-my-account"),
    path("delete-account", views.delete_account_web, name="delete-account-web"),

    # حظر المعلنين — متطلّب سياسة المحتوى من المستخدمين
    path("blocks", views.blocks, name="blocks"),
    path("blocks/<int:user_id>", views.unblock, name="unblock"),
]
