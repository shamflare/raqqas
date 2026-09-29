#!/usr/bin/env bash
#
# سوق الرقة — رفع حزمة .aab إلى Google Play
#
#   bash 13-play-upload.sh --track internal --notes "إصلاح لوحة المفاتيح"
#   bash 13-play-upload.sh --track production --notes "..." --rollout 0.1
#   bash 13-play-upload.sh --status        # ما هو منشور الآن، بلا رفع
#   bash 13-play-upload.sh --track production --version-code 7 --notes "..."   # ترقية مرفوع سابقًا
#
# غلاف رقيق حول deploy/play/upload.py: يتحقّق من الشروط أولًا بلغة مفهومة،
# ثم يسلّم العمل لبايثون. الفحص هنا لأن رسالة «الملف غير موجود» أوضح بكثير
# من أثر استدعاء بايثون طوله عشرون سطرًا.
#
set -euo pipefail

UPLOADER="/root/play/upload.py"
CREDENTIALS="/etc/souq/play-service-account.json"
VENV_PY="/srv/souq/venv/bin/python"

if [ ! -f "$UPLOADER" ]; then
  echo "❌ سكربت الرفع غير موجود: $UPLOADER"
  echo "   انسخه من جهازك:"
  echo "   scp -i ~/.ssh/souq_raqqa -r deploy/play root@\$(hostname -I | awk '{print \$1}'):/root/"
  exit 1
fi

if [ ! -f "$CREDENTIALS" ]; then
  echo "❌ ملف حساب الخدمة غير موجود: $CREDENTIALS"
  echo "   بلا هذا الملف لا يوجد رفع آلي إطلاقًا."
  echo "   الخطوات كاملة في deploy/PLAY.md §3.2 — وخلاصتها:"
  echo "     ① فعّل Google Play Android Developer API في Google Cloud"
  echo "     ② أنشئ حساب خدمة ونزّل مفتاحه JSON"
  echo "     ③ ادعُ بريده في Play Console ‹ Users and permissions"
  echo "     ④ انقله إلى $CREDENTIALS بصلاحيات 600"
  exit 1
fi

# صلاحيات الملف: يحمل مفتاحًا خاصًّا يملك حق النشر باسمك.
PERMS="$(stat -c '%a' "$CREDENTIALS")"
if [ "$PERMS" != "600" ]; then
  echo "⚠️  صلاحيات $CREDENTIALS هي $PERMS — نضيّقها إلى 600"
  chmod 600 "$CREDENTIALS"
fi

if ! "$VENV_PY" -c "import googleapiclient, google.oauth2" 2>/dev/null; then
  echo "▶ تثبيت مكتبة عميل Google (مرة واحدة)…"
  "$VENV_PY" -m pip install -q google-api-python-client google-auth
fi

exec "$VENV_PY" "$UPLOADER" --credentials "$CREDENTIALS" "$@"
