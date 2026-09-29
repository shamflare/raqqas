#!/usr/bin/env bash
#
# سوق الرقة — فيديو الإعلانات
#
#   الاستعمال:  bash 16-video.sh
#
# يُنفَّذ مرة واحدة بعد نشر الخلفية التي تدعم الفيديو (03-deploy.sh). إعادته آمنة.
#
# يفعل شيئين:
#   ١. يوسّع حدّ الرفع في nginx لمسار الفيديو وحده (الحدّ العام 15M يبقى للصور)
#   ٢. مؤقّت systemd يضغط الفيديوهات المرفوعة كل نصف دقيقة (manage.py process_videos)
#
# ffmpeg لا يحتاج تثبيتًا: يأتي داخل البيئة من حزمة imageio-ffmpeg (requirements.txt).
#
set -euo pipefail

APP_DIR="/srv/souq"
BACKEND="$APP_DIR/backend"
VENV="$APP_DIR/venv"

# ---------------------------------------------------------------- ffmpeg

echo "▶ التحقّق من ffmpeg…"
sudo -u souq "$VENV/bin/python" -c "import imageio_ffmpeg, subprocess; \
exe = imageio_ffmpeg.get_ffmpeg_exe(); \
print('   ', subprocess.run([exe, '-version'], capture_output=True, text=True).stdout.splitlines()[0])"

# ---------------------------------------------------------------- nginx

# ⚠️ لا نعيد تشغيل 04-nginx.sh: ذاك يكتب الملف من الصفر فيمحو ما أضافه certbot.
#    نُدخل موقع الفيديو قبل `location /api/` في الملفات الموجودة، مرة واحدة.
#
# 150M فوق الافتراضي في لوحة التحكم (100) بهامش. إن رفعتَ «أقصى حجم للفيديو»
# في اللوحة فوق 150 فارفع هذا الرقم أيضًا، وإلا ردّ nginx بخطأ 413 قبل Django.
echo "▶ حدّ رفع الفيديو في nginx…"
python3 - <<'PY'
import pathlib

block = """    # رفع فيديو الإعلان — الحدّ العام لا يتّسع لمقطع دقيقة من جوال (16-video.sh)
    location ~ ^/api/v1/listings/[0-9]+/video$ {
        client_max_body_size 150M;
        client_body_timeout 300s;
        proxy_pass http://souq_app;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_read_timeout 120s;
    }

"""

for name in ("souq", "souq-ip"):
    path = pathlib.Path("/etc/nginx/sites-available") / name
    if not path.exists():
        continue
    text = path.read_text()
    if "/video$" in text:
        print(f"   ✓ {name}: موجود")
        continue
    anchor = "    location /api/ {"
    count = text.count(anchor)
    if count == 0:
        print(f"   ✖ {name}: لم أجد location /api/ — أضف الموقع يدويًا")
        continue
    # certbot قد يُبقي كتلة server للمنفذ 80 بلا /api/ — نُدخل في كل كتلة فيها /api/
    text = text.replace(anchor, block + anchor)
    path.write_text(text)
    print(f"   ✓ {name}: أُضيف ({count})")
PY

nginx -t
systemctl reload nginx

# ---------------------------------------------------------------- المؤقّت

echo "▶ خدمة ضغط الفيديو…"
cat > /etc/systemd/system/souq-video.service <<SERVICE
[Unit]
Description=سوق الرقة — ضغط فيديو الإعلانات
After=network.target postgresql.service

[Service]
Type=oneshot
User=souq
Group=souq
WorkingDirectory=$BACKEND
Environment=PYTHONUNBUFFERED=1
ExecStart=$VENV/bin/python manage.py process_videos
# المعالج مشترك مع خادم التطبيق: لا نأخذ منه أكثر من نواة ونصف
CPUQuota=150%
TimeoutStartSec=3600

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
ReadWritePaths=$APP_DIR/media
SERVICE

# OnUnitInactiveSec يُحسب من انتهاء الدورة السابقة — فلا تتداخل دورتان أبدًا
cat > /etc/systemd/system/souq-video.timer <<'TIMER'
[Unit]
Description=سوق الرقة — تشغيل ضغط الفيديو كل نصف دقيقة

[Timer]
OnBootSec=1min
OnUnitInactiveSec=30s
AccuracySec=5s

[Install]
WantedBy=timers.target
TIMER

systemctl daemon-reload
systemctl enable --now souq-video.timer >/dev/null

echo
echo "✅ الفيديو مفعّل"
systemctl list-timers souq-video.timer --no-pager | head -3
echo
echo "   السجلّ:  journalctl -u souq-video.service -n 30 --no-pager"
