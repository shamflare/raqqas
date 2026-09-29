from django.contrib import admin

from .models import AdminLog, AppConfig, DownloadEvent


@admin.register(AppConfig)
class AppConfigAdmin(admin.ModelAdmin):
    """لوحة Django مجرّد شبكة أمان — الواجهة الحقيقية هي لوحة الإدارة (Next.js)."""

    readonly_fields = ("version", "updated_at", "updated_by", "base_currency")
    fieldsets = (
        ("النسخة", {"fields": ("version", "updated_at", "updated_by")}),
        ("التصميم", {"fields": ("theme_light", "theme_dark", "font_family", "font_scale",
                                "radius", "shadows", "density", "dark_mode_enabled")}),
        ("العملات", {"fields": ("base_currency", "default_currency", "enabled_currencies",
                                "rates", "rates_updated_at")}),
        ("اللغات", {"fields": ("default_language", "supported_languages")}),
        ("الصفحة التعريفية", {"fields": ("landing_ar", "landing_tr", "landing_en", "landing_image")}),
        ("التطبيق", {"fields": ("apk_url", "apk_sha256", "apk_size_mb", "latest_version",
                                "min_version", "update_message_ar", "update_message_tr",
                                "update_message_en")}),
        ("التشغيل", {"fields": ("features", "review_mode", "review_threshold",
                                "listing_expiry_days", "daily_listing_limit",
                                "max_photos_per_listing", "max_video_seconds",
                                "max_video_mb")}),
        ("الدعم", {"fields": ("support_whatsapp", "support_email")}),
    )

    def has_add_permission(self, request):
        return not AppConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AdminLog)
class AdminLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "target_type", "target_id")
    list_filter = ("action", "target_type")
    search_fields = ("note",)
    readonly_fields = [f.name for f in AdminLog._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(DownloadEvent)
class DownloadEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "version", "source")
    list_filter = ("version", "source")

    def has_add_permission(self, request):
        return False
