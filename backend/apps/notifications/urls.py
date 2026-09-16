from django.urls import path

from . import admin_views, views

urlpatterns = [
    path("notifications", views.notification_list, name="notifications"),
    path("notifications/unread", views.unread_count, name="notifications-unread"),
    path("notifications/read", views.mark_read, name="notifications-read"),

    # واتساب — ربط الرقم من لوحة الإدارة (plan3 §3.7)
    path("admin/whatsapp", admin_views.whatsapp_status, name="admin-whatsapp"),
    path("admin/whatsapp/logout", admin_views.whatsapp_logout, name="admin-whatsapp-logout"),
    path("admin/whatsapp/test", admin_views.whatsapp_test, name="admin-whatsapp-test"),
]
