from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import admin_views, views

# بلا شرطة مائلة أخيرة: إعادة التوجيه 301 تُسقط جسم الطلب وترويسة المصادقة
# في بعض عملاء HTTP على أندرويد — ولا نريد أخطاء يصعب تفسيرها.
router = DefaultRouter(trailing_slash=False)
router.register("listings", views.ListingViewSet, basename="listing")
router.register("favorites", views.FavoriteViewSet, basename="favorite")

urlpatterns = [
    path("home", views.home_summary, name="home"),
    path("report-reasons", views.report_reasons, name="report-reasons"),
    path("rejection-reasons", views.rejection_reasons, name="rejection-reasons"),

    # لوحة الإدارة
    path("admin/dashboard", admin_views.dashboard, name="admin-dashboard"),
    path("admin/review-queue", admin_views.review_queue, name="admin-review-queue"),
    path("admin/listings", admin_views.admin_listings, name="admin-listings"),
    path("admin/listings/approve", admin_views.approve_listings, name="admin-approve"),
    path("admin/listings/reject", admin_views.reject_listings, name="admin-reject"),
    path("admin/listings/suspend", admin_views.suspend_listings, name="admin-suspend"),
    path("admin/listings/<int:pk>/featured", admin_views.toggle_featured, name="admin-featured"),
    path("admin/reports", admin_views.admin_reports, name="admin-reports"),
    path("admin/reports/<int:pk>/resolve", admin_views.resolve_report, name="admin-resolve-report"),
    path("admin/users", admin_views.admin_users, name="admin-users"),
    path("admin/users/<int:pk>/status", admin_views.set_user_status, name="admin-user-status"),
    path("admin/users/<int:pk>/auto-publish", admin_views.set_user_auto_publish,
         name="admin-user-auto-publish"),
    path("admin/users/<int:pk>/password", admin_views.set_user_password,
         name="admin-user-password"),

    path("", include(router.urls)),
]
