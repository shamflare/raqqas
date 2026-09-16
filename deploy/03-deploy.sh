#!/usr/bin/env bash
#
# سوق الرقة — نشر الخلفية
#
# يُنفَّذ بعد رفع الكود إلى /srv/souq/backend. إعادة تشغيله آمنة تمامًا:
# هذا هو أمر «التحديث» أيضًا.
#
set -euo pipefail

APP_DIR="/srv/souq"
BACKEND="$APP_DIR/backend"
VENV="$APP_DIR/venv"
SECRETS_DIR="/etc/souq"
APP_ENV="$SECRETS_DIR/app.env"
SERVER_IP="$(curl -4 -s --max-time 5 ifconfig.me || echo '')"

# ---------------------------------------------------------------- الأسرار

. "$SECRETS_DIR/db.env"

if [ ! -f "$APP_ENV" ]; then
  echo "▶ توليد مفتاح التطبيق السرّي…"
  SECRET_KEY="$(openssl rand -base64 60 | tr -d '\n/+=' | cut -c1-50)"
  cat > "$APP_ENV" <<ENV
SECRET_KEY=$SECRET_KEY
DEBUG=False
ALLOWED_HOSTS=$SERVER_IP,localhost,127.0.0.1
PUBLIC_SITE_URL=http://$SERVER_IP
CORS_ALLOWED_ORIGINS=http://$SERVER_IP
CSRF_TRUSTED_ORIGINS=http://$SERVER_IP
DATABASE_URL=postgres://souq:$DB_PASSWORD@127.0.0.1:5432/souq
MEDIA_ROOT=$APP_DIR/media
TIME_ZONE=Asia/Damascus
SECURE_SSL_REDIRECT=False
FCM_SERVER_KEY=
ENV
  chmod 640 "$APP_ENV"
  chown root:souq "$APP_ENV"
else
  echo "▶ إعدادات التطبيق موجودة — نُبقيها"
fi

# Django يقرأ .env من مجلد المشروع
ln -sfn "$APP_ENV" "$BACKEND/.env"

install -d -o souq -g souq "$APP_DIR/media" "$APP_DIR/static" "$APP_DIR/backups"
chown -R souq:souq "$BACKEND"

# ---------------------------------------------------------------- البيئة

if [ ! -d "$VENV" ]; then
  echo "▶ إنشاء البيئة الافتراضية…"
  python3 -m venv "$VENV"
  chown -R souq:souq "$VENV"
fi

echo "▶ تثبيت المتطلبات…"
sudo -u souq "$VENV/bin/pip" install --upgrade pip -q
sudo -u souq "$VENV/bin/pip" install -r "$BACKEND/requirements.txt" -q
sudo -u souq "$VENV/bin/pip" install gunicorn -q

# ---------------------------------------------------------------- قاعدة البيانات

# مخزن مؤقّت مشترك بين العمّال الثلاثة.
#
# الافتراضي `LocMemCache` ذاكرة داخل العملية الواحدة، ومع `--workers 3` يصير
# لكل عامل نسخته: عدّاد حدّ المعدّل يُقسَّم ثلاثًا فيصير الحدّ الفعلي ثلاثة
# أضعاف المكتوب، وإعدادات اللوحة تصل عاملًا ولا تصل الآخرين. جدول في قاعدة
# البيانات يكفي هنا — لا داعي لـRedis على خادم بهذا الحجم.
if ! grep -q '^CACHE_BACKEND=' "$APP_ENV"; then
  echo "▶ تفعيل المخزن المؤقّت المشترك…"
  cat >> "$APP_ENV" <<'CACHE'
CACHE_BACKEND=django.core.cache.backends.db.DatabaseCache
CACHE_LOCATION=souq_cache
CACHE
fi

echo "▶ الترحيلات…"
cd "$BACKEND"
sudo -u souq "$VENV/bin/python" manage.py migrate --noinput
sudo -u souq "$VENV/bin/python" manage.py createcachetable

echo "▶ الملفات الثابتة…"
sudo -u souq STATIC_ROOT="$APP_DIR/static" "$VENV/bin/python" manage.py collectstatic --noinput -v 0

echo "▶ البيانات المرجعية (أقسام · أحياء · أسباب رفض)…"
sudo -u souq "$VENV/bin/python" manage.py seed

# ---------------------------------------------------------------- الخدمة

echo "▶ خدمة gunicorn…"
cat > /etc/systemd/system/souq.socket <<'SOCK'
[Unit]
Description=مقبس سوق الرقة

[Socket]
ListenStream=/run/souq.sock
SocketUser=www-data
SocketMode=660

[Install]
WantedBy=sockets.target
SOCK

cat > /etc/systemd/system/souq.service <<SERVICE
[Unit]
Description=سوق الرقة — خادم التطبيق
Requires=souq.socket
After=network.target postgresql.service

[Service]
Type=notify
User=souq
Group=souq
WorkingDirectory=$BACKEND
Environment=PYTHONUNBUFFERED=1
Environment=STATIC_ROOT=$APP_DIR/static
ExecStart=$VENV/bin/gunicorn souq.wsgi:application \\
    --bind unix:/run/souq.sock \\
    --workers 3 \\
    --threads 2 \\
    --timeout 60 \\
    --graceful-timeout 30 \\
    --access-logfile - \\
    --error-logfile -
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=always
RestartSec=3
KillMode=mixed

# عزل: التطبيق لا يحتاج أكثر من مجلداته
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
ReadWritePaths=$APP_DIR/media $APP_DIR/static

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable souq.socket >/dev/null
systemctl restart souq.socket
systemctl enable souq.service >/dev/null
systemctl restart souq.service

echo
echo "✅ الخلفية تعمل"
sleep 2
systemctl is-active souq.service
