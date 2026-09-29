"""
إشعار الإدارة فور وصول إعلان جديد للمراجعة (plan2 §8.6).

سبب استعمال إشارة بدل استدعاء مباشر في الـ view: الإعلان قد يُنشأ من
لوحة Django أو من أمر إداري أيضًا — ونريد التنبيه في كل الحالات.
"""

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Listing, ListingMedia


@receiver(post_save, sender=Listing, dispatch_uid="notify_admins_on_pending_listing")
def on_listing_created(sender, instance: Listing, created: bool, **kwargs):
    if not created or instance.status != Listing.Status.PENDING:
        return
    from apps.notifications.services import notify_admins_new_listing

    notify_admins_new_listing(instance)


@receiver(post_delete, sender=ListingMedia, dispatch_uid="delete_media_files")
def on_media_deleted(sender, instance: ListingMedia, **kwargs):
    """
    Django لا يحذف الملفات مع صفوفها. مع الصور كان ذلك تسرّبًا صغيرًا، ومع
    الفيديو يملأ قرص الخادم. الحذف بعد تثبيت المعاملة: إن تراجعت بقي الملف.
    """
    files = [instance.image, instance.thumb, instance.video]

    def remove():
        for field in files:
            if field and field.name:
                field.storage.delete(field.name)

    transaction.on_commit(remove)
