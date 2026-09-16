from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Device, User
from .utils import normalize_phone


class PhoneField(serializers.CharField):
    """
    يقبل الرقم بأي صيغة ويخزّنه E.164.

    التطبيق يرسله دوليًّا كاملًا بعد أن يختار المستخدم دولته، لكن لوحة الإدارة
    وصفحة حذف الحساب على الويب ما زالت تقبل `0994…` عاريًا — فيبقى الافتراض
    السوري عاملًا لمن لم يختر دولة.
    """

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        try:
            return normalize_phone(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)


class UserSerializer(serializers.ModelSerializer):
    """الملف الشخصي — لصاحبه فقط."""

    phone_display = serializers.CharField(source="display_phone", read_only=True)
    whatsapp_number = PhoneField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = [
            "id", "name", "phone", "phone_display", "whatsapp_number",
            "role", "status", "language", "phone_verified",
            "listings_approved_count", "created_at", "last_seen_at",
        ]
        read_only_fields = [
            "id", "phone", "role", "status", "phone_verified",
            "listings_approved_count", "created_at", "last_seen_at",
        ]

    def validate_language(self, value):
        if value not in {"ar", "tr", "en"}:
            raise serializers.ValidationError("اللغات المدعومة: ar, tr, en.")
        return value


class PublicSellerSerializer(serializers.ModelSerializer):
    """
    ما يراه الزائر عن البائع — بلا أي رقم هاتف.

    ⚠️ قرار 17: الأرقام لا تُرسل في أي رد عام. من يريد التواصل يسجّل الدخول
    ويطلب /listings/{id}/contact — فيُحمى الرقم من السحب الآلي أيضًا.
    """

    initial = serializers.CharField(read_only=True)
    joined_year = serializers.IntegerField(read_only=True)
    listings_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "name", "initial", "joined_year", "phone_verified", "listings_count"]

    def get_listings_count(self, obj) -> int:
        cached = getattr(obj, "published_listings_count", None)
        if cached is not None:
            return cached
        return obj.listings.filter(status="published").count()


class RegisterSerializer(serializers.ModelSerializer):
    phone = PhoneField()
    # إجباري الآن: عليه يصل رمز استعادة كلمة المرور. التطبيق يهيّئه مسبقًا
    # برقم الحساب لأن ذلك هو الغالب، فلا يزيد على المستخدم ضغطة.
    whatsapp_number = PhoneField()
    password = serializers.CharField(write_only=True, min_length=6, style={"input_type": "password"})

    class Meta:
        model = User
        fields = ["name", "phone", "whatsapp_number", "password", "language"]

    def validate_name(self, value):
        value = " ".join(value.split())
        if len(value) < 2:
            raise serializers.ValidationError("الاسم قصير جدًا.")
        return value

    def validate_phone(self, value):
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError(
                "هذا الرقم مسجّل مسبقًا. جرّب تسجيل الدخول."
            )
        return value

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)


class LoginSerializer(serializers.Serializer):
    phone = PhoneField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"),
            username=attrs["phone"],
            password=attrs["password"],
        )
        if user is None:
            # رسالة واحدة للحالتين — لا نكشف أي الأرقام مسجّل
            raise serializers.ValidationError(
                {"detail": "رقم الهاتف أو كلمة المرور غير صحيحة."}
            )
        if user.status == User.Status.BANNED:
            raise serializers.ValidationError({"detail": "هذا الحساب محظور."})
        if user.status == User.Status.SUSPENDED:
            raise serializers.ValidationError(
                {"detail": f"هذا الحساب موقوف. {user.suspension_reason}".strip()}
            )
        attrs["user"] = user
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=6)

    def validate_current_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("كلمة المرور الحالية غير صحيحة.")
        return value

    def validate_new_password(self, value):
        try:
            validate_password(value, self.context["request"].user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value


# ------------------------------------------------------- استعادة كلمة المرور


class ForgotPasswordSerializer(serializers.Serializer):
    """الخطوة ①: الرقم وحده."""

    phone = PhoneField()


class VerifyResetCodeSerializer(serializers.Serializer):
    """الخطوة ②: الرقم والرمز."""

    phone = PhoneField()
    code = serializers.CharField(min_length=4, max_length=8, trim_whitespace=True)

    def validate_code(self, value):
        # المستخدم ينسخ الرمز من واتساب فيلتصق معه فراغ أو محرف اتجاه
        return "".join(ch for ch in value if ch.isdigit())


class ResetPasswordSerializer(serializers.Serializer):
    """
    الخطوة ③: التذكرة وكلمة المرور الجديدة.

    التذكرة لا الرمز: الرمز استُهلك في الخطوة ② فلا يصحّ التحقق منه ثانيةً،
    ولا نريده يسافر في طلب ثالث.
    """

    ticket = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=6)

    def validate_new_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ["token", "platform", "app_version", "language"]


def tokens_for(user: User) -> dict:
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}
