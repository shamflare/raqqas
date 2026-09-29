"""
فيديو الإعلان (مقطع واحد، مدة محدودة، ضغط لاحق) · وتعيين الإدارة كلمة مرور لعميل.

اختبارات الفيديو تصنع مقاطع حقيقية بـ ffmpeg — لا ملفات وهمية — لأن الخطر
الحقيقي في قراءة الترويسة واستخراج الغلاف، لا في منطق العرض.
"""

import io
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import override_settings

from apps.core.models import AdminLog, AppConfig
from apps.core.videos import ffmpeg_binary
from apps.listings.models import ListingMedia

from .test_access_rules import BaseAPITest


def make_video(seconds: float, size: str = "320x240") -> bytes:
    with tempfile.TemporaryDirectory() as workdir:
        out = Path(workdir) / "clip.mp4"
        subprocess.run(
            [ffmpeg_binary(), "-hide_banner", "-loglevel", "error", "-y",
             "-f", "lavfi", "-i", f"testsrc=duration={seconds}:size={size}:rate=15",
             "-f", "lavfi", "-i", f"sine=duration={seconds}",
             "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest",
             str(out)],
            check=True, capture_output=True,
        )
        return out.read_bytes()


class VideoUploadTests(BaseAPITest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.short_clip = make_video(3)

    def setUp(self):
        super().setUp()
        self.media_dir = tempfile.mkdtemp()
        override = override_settings(MEDIA_ROOT=self.media_dir)
        override.enable()
        self.addCleanup(override.disable)
        self.addCleanup(shutil.rmtree, self.media_dir, ignore_errors=True)
        self.seller_client = self.as_user(self.seller)

    def upload(self, data: bytes, client=None, name="clip.mp4"):
        return (client or self.seller_client).post(
            f"/api/v1/listings/{self.listing.id}/video",
            {"video": SimpleUploadedFile(name, data, content_type="video/mp4")},
            format="multipart",
        )

    def test_upload_creates_video_with_poster_and_is_playable_immediately(self):
        response = self.upload(self.short_clip)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["kind"], "video")
        self.assertEqual(response.data["duration"], 3)
        self.assertTrue(response.data["url"].endswith(".jpg"))      # الغلاف للتطبيق القديم
        self.assertIn(".mp4", response.data["video_url"])

        media = ListingMedia.objects.get(pk=response.data["id"])
        self.assertEqual(media.video_state, ListingMedia.VideoState.PENDING)
        self.assertFalse(media.is_main)

        detail = self.guest.get(f"/api/v1/listings/{self.listing.id}").data
        self.assertTrue(detail["has_video"])

    def test_only_one_video_per_listing(self):
        self.assertEqual(self.upload(self.short_clip).status_code, 201)
        second = self.upload(self.short_clip)
        self.assertEqual(second.status_code, 400)

    def test_too_long_video_is_rejected(self):
        config = AppConfig.get_solo()
        config.max_video_seconds = 1     # + ثانية السماح = 2 < 3
        config.save()
        response = self.upload(self.short_clip)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ListingMedia.objects.filter(kind="video").exists())

    def test_admin_can_disable_video(self):
        config = AppConfig.get_solo()
        config.max_video_seconds = 0
        config.save()
        self.assertEqual(self.upload(self.short_clip).status_code, 400)

    def test_not_a_video_is_rejected(self):
        response = self.upload(b"definitely not a video" * 100)
        self.assertEqual(response.status_code, 400)

    def test_other_user_cannot_upload(self):
        response = self.upload(self.short_clip, client=self.as_user(self.buyer))
        self.assertEqual(response.status_code, 403)

    def test_video_does_not_count_against_photo_quota(self):
        self.upload(self.short_clip)
        config = AppConfig.get_solo()
        config.max_photos_per_listing = 1
        config.save()
        from PIL import Image
        buffer = io.BytesIO()
        Image.new("RGB", (50, 50), "red").save(buffer, format="JPEG")
        response = self.seller_client.post(
            f"/api/v1/listings/{self.listing.id}/media",
            {"images": SimpleUploadedFile("p.jpg", buffer.getvalue(), content_type="image/jpeg")},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data[0]["is_main"])     # الصورة لا الغلاف

    def test_process_videos_transcodes_and_removes_original(self):
        media_id = self.upload(self.short_clip, name="big.mov").data["id"]
        original = Path(ListingMedia.objects.get(pk=media_id).video.path)
        self.assertTrue(original.exists())

        call_command("process_videos", stdout=io.StringIO())

        media = ListingMedia.objects.get(pk=media_id)
        self.assertEqual(media.video_state, ListingMedia.VideoState.READY)
        self.assertTrue(media.video.name.endswith("-720.mp4"))
        self.assertTrue(Path(media.video.path).exists())
        self.assertFalse(original.exists())

    def test_deleting_video_removes_its_files(self):
        media_id = self.upload(self.short_clip).data["id"]
        media = ListingMedia.objects.get(pk=media_id)
        paths = [Path(media.video.path), Path(media.image.path), Path(media.thumb.path)]
        with self.captureOnCommitCallbacks(execute=True):
            response = self.seller_client.delete(
                f"/api/v1/listings/{self.listing.id}/media/{media_id}"
            )
        self.assertEqual(response.status_code, 204)
        for path in paths:
            self.assertFalse(path.exists(), path)


class AdminSetPasswordTests(BaseAPITest):
    def url(self, user):
        return f"/api/v1/admin/users/{user.id}/password"

    def test_admin_sets_password_and_user_logs_in_with_it(self):
        old_client = self.as_user(self.seller)
        # ختم الإلغاء بدقّة الثانية (apps/accounts/tokens.py): رمز صدر في ثانية
        # التغيير نفسها ينجو. نتجاوز الثانية كي يكون الفحص حتميًا لا محظوظًا.
        time.sleep(1.1)
        response = self.as_user(self.admin).post(
            self.url(self.seller), {"new_password": "raqa2468"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)

        login = self.guest.post(
            "/api/v1/auth/login", {"phone": self.seller.phone, "password": "raqa2468"},
            format="json",
        )
        self.assertEqual(login.status_code, 200)
        # الأجهزة القديمة خرجت
        self.assertEqual(old_client.get("/api/v1/auth/me").status_code, 401)

        log = AdminLog.objects.get(action="user_password")
        self.assertEqual(log.target_id, self.seller.id)
        self.assertNotIn("raqa2468", log.note + str(log.meta))

    def test_weak_password_is_rejected(self):
        response = self.as_user(self.admin).post(
            self.url(self.seller), {"new_password": "12345678"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_moderator_cannot_set_passwords(self):
        from apps.accounts.models import User
        moderator = User.objects.create_user(
            phone="0933333333", password="test1234", name="مشرف", role=User.Role.MODERATOR
        )
        response = self.as_user(moderator).post(
            self.url(self.seller), {"new_password": "raqa2468"}, format="json"
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_accounts_are_protected(self):
        from apps.accounts.models import User
        other_admin = User.objects.create_user(
            phone="0944444444", password="test1234", name="مدير آخر", role=User.Role.ADMIN
        )
        response = self.as_user(self.admin).post(
            self.url(other_admin), {"new_password": "raqa2468"}, format="json"
        )
        self.assertEqual(response.status_code, 403)
