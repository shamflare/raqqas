"""
ضغط مقاطع الفيديو المرفوعة — واحدًا تلو الآخر.

    python manage.py process_videos

يشغّله مؤقّت systemd كل نصف دقيقة على الخادم (deploy/16-video.sh). والمؤقّت لا
يبدأ نسخة ثانية ما دامت الأولى تعمل، فلا يتزاحم ffmpeg على معالج الخادم.

ما يفشل ضغطه يبقى معروضًا بملفه الأصلي ويُعلَّم `failed` — فلا يُعاد كل دورة.
"""

import os
import tempfile
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand

from apps.core.videos import transcode
from apps.listings.models import ListingMedia


class Command(BaseCommand):
    help = "ضغط فيديوهات الإعلانات المنتظرة إلى 720p"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=20,
                            help="أقصى عدد مقاطع في الدورة الواحدة")

    def handle(self, *args, limit, **options):
        # أولوية منخفضة: الضغط ينتظر، أما طلبات التطبيق فلا
        if hasattr(os, "nice"):
            os.nice(10)

        pending = ListingMedia.objects.filter(
            kind=ListingMedia.Kind.VIDEO, video_state=ListingMedia.VideoState.PENDING,
        ).order_by("id")[:limit]

        for media in pending:
            self._process(media)

    def _process(self, media: ListingMedia):
        original = media.video
        with tempfile.TemporaryDirectory() as workdir:
            target = Path(workdir) / "out.mp4"
            try:
                transcode(original.path, str(target))
            except Exception as exc:  # noqa: BLE001 — أي عطل يُسجَّل ولا يوقف الدورة
                ListingMedia.objects.filter(pk=media.pk).update(
                    video_state=ListingMedia.VideoState.FAILED
                )
                self.stderr.write(f"✖ فيديو #{media.pk}: {exc}")
                return

            # حُذف الإعلان أو المقطع أثناء الضغط؟ لا نكتب ملفًا يتيمًا
            if not ListingMedia.objects.filter(pk=media.pk).exists():
                return

            before = original.size
            old_name = original.name
            stem = Path(old_name).stem
            with target.open("rb") as handle:
                media.video.save(f"{stem}-720.mp4", File(handle), save=False)
            media.video_state = ListingMedia.VideoState.READY
            media.save(update_fields=["video", "video_state"])
            media.video.storage.delete(old_name)

            after = media.video.size
            self.stdout.write(
                f"✓ فيديو #{media.pk}: {before / 1048576:.1f} → {after / 1048576:.1f} ميغابايت"
            )
