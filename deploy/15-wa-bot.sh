#!/usr/bin/env bash
#
# سوق الرقة — خدمة واتساب (إرسال رموز استعادة كلمة المرور)
#
#   الاستعمال:  bash 15-wa-bot.sh
#
# يُنفَّذ بعد رفع مجلد deploy/wa-bot/. إعادة تشغيله = أمر التحديث، ولا تُمسّ
# جلسة واتساب المرتبطة فلا يلزم مسح QR من جديد.
#
# ⚠️ اقرأ deploy/WHATSAPP.md قبل التشغيل: هذا مسار **غير رسمي** وقد تحظر Meta
#    رقم واتساب المستعمَل. استعمل رقمًا مخصّصًا للتطبيق لا رقمًا شخصيًا.
#
set -euo pipefail

SRC="/srv/souq/wa-bot"
SECRETS_DIR="/etc/souq"
BOT_ENV="$SECRETS_DIR/wa-bot.env"
SESSION_DIR="$SECRETS_DIR/wa-session"
APP_ENV="$SECRETS_DIR/app.env"

command -v node >/dev/null || { echo "✖ Node غير مثبّت — شغّل 08-android-toolchain.sh أولًا"; exit 1; }

# ---------------------------------------------------------------- الأسرار

if [ ! -f "$BOT_ENV" ]; then
  echo "▶ توليد رمز الخدمة المشترك…"
  cat > "$BOT_ENV" <<ENV
WA_BOT_TOKEN=$(openssl rand -hex 32)
WA_BOT_HOST=127.0.0.1
WA_BOT_PORT=8787
WA_SESSION_DIR=$SESSION_DIR
ENV
  chmod 640 "$BOT_ENV"
  chown root:souq "$BOT_ENV"
else
  echo "▶ إعدادات البوت موجودة — نُبقيها"
fi

. "$BOT_ENV"

install -d -o souq -g souq -m 700 "$SESSION_DIR"

# ---------------------------------------------------------------- وصل Django

# Django يحتاج الرمز نفسه ليتكلّم مع الخدمة. نكتبه في app.env مرة واحدة،
# ونحدّثه إن تغيّر — بلا تكرار السطر في كل تشغيل.
echo "▶ ربط الخلفية بالخدمة…"
python3 - "$APP_ENV" "$WA_BOT_TOKEN" "$WA_BOT_PORT" <<'PY'
import sys, pathlib

path, token, port = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
wanted = {
    "WHATSAPP_PROVIDER": "bot",
    "WHATSAPP_BOT_URL": f"http://127.0.0.1:{port}",
    "WHATSAPP_BOT_TOKEN": token,
}
lines = path.read_text().splitlines()
kept = [line for line in lines if line.split("=", 1)[0] not in wanted]
kept += [f"{key}={value}" for key, value in wanted.items()]
path.write_text("\n".join(kept) + "\n")
PY

# ---------------------------------------------------------------- التثبيت

echo "▶ تثبيت اعتماديات الخدمة…"
cd "$SRC"
sudo -u souq -H npm install --omit=dev --no-audit --no-fund --silent

echo "▶ خدمة systemd…"
cat > /etc/systemd/system/souq-wa.service <<SERVICE
[Unit]
Description=سوق الرقة — خدمة واتساب
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=souq
Group=souq
WorkingDirectory=$SRC
EnvironmentFile=$BOT_ENV
ExecStart=/usr/bin/node $SRC/index.js
Restart=always
RestartSec=10

# الجلسة سرّ بحجم مفتاح: من نسخها انتحل واتساب الرقم كاملًا
ReadWritePaths=$SESSION_DIR
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable souq-wa >/dev/null
systemctl restart souq-wa
systemctl restart souq   # الخلفية تقرأ المفاتيح الجديدة

# ---------------------------------------------------------------- التقرير

sleep 3
if curl -fs --max-time 5 "http://127.0.0.1:$WA_BOT_PORT/health" >/dev/null 2>&1; then
  echo "✅ الخدمة تعمل ومرتبطة بواتساب."
else
  cat <<'NEXT'

⚠️ الخدمة تعمل لكنها **غير مرتبطة** بواتساب بعد.

اربطها الآن (مرة واحدة فقط):

    systemctl stop souq-wa
    cd /srv/souq/wa-bot && sudo -u souq -H npm run pair

يظهر رمز QR في الطرفية. افتح واتساب على هاتف الرقم المخصّص:
    ⋮ ← الأجهزة المرتبطة ← ربط جهاز ← امسح الرمز

ثم أعد التشغيل:

    systemctl start souq-wa
    curl -s http://127.0.0.1:8787/health

NEXT
fi
