"""
معالجة مقاطع الفيديو المرفوعة.

على مرحلتين، عن قصد:

    عند الرفع (داخل الطلب)   فحص سريع + صورة غلاف        ← أقل من ثانيتين
    لاحقًا (process_videos)   ضغط إلى 720p H.264            ← عشرات الثواني

الضغط لا يجري داخل الطلب لأنه أطول من مهلة gunicorn وnginx (60 ثانية) على
معالج الخادم. وحتى يكتمل يُعرض الملف الأصلي كما هو — فالإعلان لا ينتظر شيئًا.

لماذا نضغط أصلًا؟ دقيقة واحدة من كاميرا جوال حديث قرابة 100 ميغابايت. يرفعها
البائع مرة واحدة، لكن يشاهدها كل زائر على إنترنت الرقة. بعد الضغط: 10–15.

ffmpeg يأتي من حزمة `imageio-ffmpeg` (ملف ثابت داخل البيئة) فلا يحتاج الخادم
ولا جهاز التطوير تثبيت شيء بيده. ويُقدَّم ffmpeg النظام إن وُجد.
"""

from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from PIL import Image

from .images import _as_file, _to_jpeg

PROBE_TIMEOUT = 30
POSTER_TIMEOUT = 30
TRANSCODE_TIMEOUT = 15 * 60


@lru_cache(maxsize=1)
def ffmpeg_binary() -> str:
    configured = getattr(settings, "FFMPEG_BINARY", "")
    if configured:
        return configured
    system = shutil.which("ffmpeg")
    if system:
        return system
    try:
        import imageio_ffmpeg
    except ImportError as exc:  # pragma: no cover — مذكورة في requirements.txt
        raise RuntimeError("ffmpeg غير متاح: ثبّت imageio-ffmpeg") from exc
    return imageio_ffmpeg.get_ffmpeg_exe()


@dataclass
class VideoInfo:
    duration: float
    width: int
    height: int


_DURATION = re.compile(r"Duration:\s*(\d+):(\d{2}):(\d{2}(?:\.\d+)?)")
_VIDEO_STREAM = re.compile(r"Stream #\S+.*?: Video: .*?(\d{2,5})x(\d{2,5})")


def probe(path: str) -> VideoInfo:
    """
    مدة المقطع وأبعاده — من ترويسة الملف دون فكّ ضغطه.

    لا ffprobe في حزمة imageio-ffmpeg، فنقرأ ما يطبعه `ffmpeg -i` على stderr.
    الأمر ينتهي بخطأ «لا ملف إخراج» دائمًا، وهذا متوقَّع.
    """
    try:
        result = subprocess.run(
            [ffmpeg_binary(), "-hide_banner", "-i", path],
            capture_output=True, timeout=PROBE_TIMEOUT,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValidationError("تعذّرت قراءة الفيديو.") from exc

    output = result.stderr.decode("utf-8", "replace")
    duration = _DURATION.search(output)
    stream = _VIDEO_STREAM.search(output)
    if not duration or not stream:
        raise ValidationError("الملف ليس فيديو صالحًا.")

    hours, minutes, seconds = duration.groups()
    return VideoInfo(
        duration=int(hours) * 3600 + int(minutes) * 60 + float(seconds),
        width=int(stream.group(1)),
        height=int(stream.group(2)),
    )


def poster(path: str, duration: float) -> dict:
    """
    صورة الغلاف: إطار من الثانية الأولى، بالمعالجة نفسها التي تمرّ بها الصور.

    الغلاف يُحفظ في حقل `image` — فالتطبيقات القديمة التي لا تعرف الفيديو
    تعرضه صورةً عادية بدل أن تنكسر على رابط mp4.
    """
    at = "1" if duration >= 2 else "0"
    try:
        result = subprocess.run(
            [ffmpeg_binary(), "-hide_banner", "-loglevel", "error",
             "-ss", at, "-i", path, "-frames:v", "1",
             "-f", "image2pipe", "-vcodec", "png", "-"],
            capture_output=True, timeout=POSTER_TIMEOUT,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValidationError("تعذّرت قراءة الفيديو.") from exc
    if result.returncode != 0 or not result.stdout:
        raise ValidationError("تعذّر استخراج صورة من الفيديو.")

    frame = Image.open(io.BytesIO(result.stdout))
    full, width, height = _to_jpeg(frame, settings.IMAGE_MAX_EDGE, settings.IMAGE_QUALITY)
    thumb, _, _ = _to_jpeg(frame, settings.IMAGE_THUMB_EDGE, 78)
    return {
        "full": _as_file(full, "poster.jpg", "image"),
        "thumb": _as_file(thumb, "poster-t.jpg", "thumb"),
        "width": width,
        "height": height,
    }


@contextmanager
def local_path(uploaded_file):
    """
    مسار على القرص للملف المرفوع — ffmpeg يقرأ ملفات لا كائنات بايثون.

    الملفات الكبيرة يكتبها Django على القرص أصلًا فنستعمل مسارها. والصغيرة
    (تحت FILE_UPLOAD_MAX_MEMORY_SIZE) في الذاكرة، فنكتبها في ملف مؤقّت.
    """
    temporary = getattr(uploaded_file, "temporary_file_path", None)
    if temporary:
        yield temporary()
        return

    suffix = Path(getattr(uploaded_file, "name", "") or "video.mp4").suffix or ".mp4"
    handle = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        for chunk in uploaded_file.chunks():
            handle.write(chunk)
        handle.close()
        yield handle.name
    finally:
        uploaded_file.seek(0)
        os.unlink(handle.name)


def inspect_upload(uploaded_file, *, max_seconds: int, max_bytes: int) -> dict:
    """
    يُستدعى داخل طلب الرفع. يعيد: {"duration": int, "poster": {...}}

    يرفض ما يتجاوز المدة أو الحجم قبل أن يُحفظ منه بايت واحد.
    """
    if uploaded_file.size > max_bytes:
        limit = max_bytes // (1024 * 1024)
        raise ValidationError(f"حجم الفيديو يتجاوز الحد المسموح ({limit} ميغابايت).")

    with local_path(uploaded_file) as path:
        info = probe(path)
        # ثانية سماح: الجوال يقصّ عند 60 فيخرج مقطع مدته 60.4
        if info.duration > max_seconds + 1:
            raise ValidationError(
                f"مدة الفيديو {round(info.duration)} ثانية — الحد المسموح {max_seconds} ثانية."
            )
        if info.duration < 1:
            raise ValidationError("الفيديو قصير جدًا.")
        cover = poster(path, info.duration)

    return {"duration": round(info.duration), "poster": cover}


def transcode(source: str, target: str) -> None:
    """
    إلى MP4 يعمل في كل مكان: H.264 + AAC، أطول ضلع 1280، و30 إطارًا كحدّ أعلى.

    `+faststart` يضع فهرس الملف في أوله فيبدأ التشغيل قبل اكتمال التنزيل —
    ضروري على إنترنت بطيء، وإلا انتظر المشاهد الملف كاملًا.
    """
    scale = (
        "scale=w='if(gte(iw,ih),min(1280,iw),-2)':h='if(gte(iw,ih),-2,min(1280,ih))',"
        "pad=ceil(iw/2)*2:ceil(ih/2)*2,format=yuv420p"
    )
    command = [
        ffmpeg_binary(), "-hide_banner", "-loglevel", "error", "-y",
        "-i", source,
        "-map", "0:v:0", "-map", "0:a:0?",
        "-vf", scale, "-fpsmax", "30",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
        "-maxrate", "2M", "-bufsize", "4M",
        "-c:a", "aac", "-b:a", "96k", "-ac", "2",
        "-movflags", "+faststart",
        "-threads", "2",
        target,
    ]
    result = subprocess.run(command, capture_output=True, timeout=TRANSCODE_TIMEOUT)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", "replace")[-800:])
