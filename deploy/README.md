# الخادم — سوق الرقة

خادم الإنتاج: **Hetzner CX23 · Nuremberg 🇩🇪 · Ubuntu 24.04**
`46.224.188.126`

## الدخول

```bash
ssh -i ~/.ssh/souq_raqqa root@46.224.188.126     # للإدارة
ssh -i ~/.ssh/souq_raqqa souq@46.224.188.126     # لتشغيل التطبيق
```

الدخول **بالمفتاح فقط** — كلمات المرور معطّلة تمامًا في SSH.

> ⚠️ الملف `~/.ssh/souq_raqqa` (بلا `.pub`) هو المفتاح الخاص. من يملكه يملك
> الخادم. لا يُرفع إلى Git ولا يُرسل في رسالة. له نسخة احتياطية واحدة في مكان
> آمن، وإلا فقدنا الدخول إلى الخادم نهائيًا.

## ما الذي يعمل عليه

| | |
|---|---|
| `nginx` | الواجهة العامة — يوزّع الطلبات ويخدم الصور والملفات |
| `souq.service` | خادم التطبيق (gunicorn · 3 عمّال) |
| `postgresql` | قاعدة البيانات |
| `fail2ban` | حظر من يحاول تخمين الدخول |
| `ufw` | جدار ناري — المنافذ 22 · 80 · 443 فقط |
| `souq-backup.timer` | نسخة احتياطية يوميًا 3:30 فجرًا |
| `souq-video.timer` | ضغط فيديو الإعلانات المرفوعة إلى 720p — كل نصف دقيقة (`16-video.sh`) |
| `souq-wa.service` | خدمة واتساب — على 127.0.0.1:8787، لا منفذ مكشوف (`WHATSAPP.md`) |

## المسارات

```
/srv/souq/
├── backend/     كود Django
├── venv/        بيئة بايثون
├── media/       صور الإعلانات المرفوعة
├── static/      ملفات Django الثابتة
├── web/         الصفحة التعريفية
├── apk/         ملف التطبيق للتنزيل
└── backups/     النسخ الاحتياطية

/etc/souq/
├── app.env      SECRET_KEY وإعدادات Django   (root:souq · 640)
└── db.env       كلمة مرور قاعدة البيانات      (root:souq · 640)
```

الأسرار **خارج** مجلد الكود عمدًا: رفع الكود لا يمسّها، ولا يمكن أن تُنشر في
Git بالخطأ.

---

## سكربتات الإعداد

تُنفَّذ بالترتيب، وإعادة أيٍّ منها **آمنة** (لا تُتلف بيانات ولا تبدّل كلمات مرور
موجودة):

| السكربت | ماذا يفعل |
|---|---|
| `01-bootstrap.sh` | تحديث · مستخدم `souq` · تقوية SSH · جدار ناري · fail2ban · swap |
| `02-database.sh` | قاعدة PostgreSQL + كلمة مرور عشوائية + ضبط للذاكرة المتاحة |
| `03-deploy.sh` | البيئة · المتطلبات · الترحيلات · البيانات المرجعية · خدمة gunicorn |
| `04-nginx.sh` | إعداد nginx وتوزيع المسارات |
| `05-backups.sh` | النسخ الاحتياطي اليومي |
| `06-ssl.sh` | شهادة Let's Encrypt + تحويل https + تحديث ALLOWED_HOSTS |
| `07-ip-fallback.sh` | إبقاء الوصول برقم IP (تشخيص حجب DNS) |
| `08-android-toolchain.sh` | Java 17 · Node 22 · Android SDK — لبناء APK على الخادم |
| `09-build-apk.sh` | مفتاح التوقيع · prebuild · بناء موقّع · نشر وتسجيل النسخة |
| `10-web.sh` | بناء Next.js + خدمة `souq-web` + ربطها بـ nginx |
| `11-publish-update.sh` | دفع تحديث فوري (OTA) إلى التطبيقات المثبَّتة |
| `12-build-aab.sh` · `13-play-upload.sh` · `14-release.sh` | خطّ الإصدار إلى Google Play |
| `15-wa-bot.sh` | خدمة واتساب لإرسال رموز استعادة كلمة المرور — **اقرأ `WHATSAPP.md` أولًا** |
| `16-video.sh` | فيديو الإعلانات: حدّ رفع أكبر لمساره في nginx + مؤقّت `souq-video.timer` يضغط المقاطع |

## تحديث الكود بعد أي تعديل

```bash
# من مجلد المشروع على جهازك
tar --exclude='.venv' --exclude='__pycache__' --exclude='db.sqlite3' \
    --exclude='media' --exclude='staticfiles' --exclude='.env' \
    -czf - backend | ssh -i ~/.ssh/souq_raqqa root@46.224.188.126 \
    "tar -xzf - -C /srv/souq && bash /root/03-deploy.sh"
```

`03-deploy.sh` هو أمر التحديث نفسه: يثبّت الجديد، يرحّل قاعدة البيانات، ويعيد
تشغيل الخدمة.

## المتابعة والتشخيص

```bash
systemctl status souq.service            # حالة التطبيق
journalctl -u souq.service -f            # السجلّ الحيّ
journalctl -u souq.service -n 100        # آخر 100 سطر
tail -f /var/log/nginx/souq.error.log    # أخطاء nginx
tail -f /var/log/nginx/souq.access.log   # كل الزيارات (مفيد لاختبار سوريا)
fail2ban-client status sshd              # من حاول اقتحام الخادم
systemctl list-timers souq-backup.timer  # موعد النسخة القادمة
/usr/local/bin/souq-backup               # نسخة احتياطية الآن
```

---

## بناء نسخة جديدة من التطبيق

```bash
# 1) ارفع كود التطبيق
tar --exclude='node_modules' --exclude='.expo' --exclude='android' \
    -czf - app | ssh -i ~/.ssh/souq_raqqa root@46.224.188.126 \
    "rm -rf /srv/souq/app && tar -xzf - -C /srv/souq && chown -R souq:souq /srv/souq/app"

# 2) ابنِ ووقّع وانشر
ssh -i ~/.ssh/souq_raqqa root@46.224.188.126 \
    "bash /root/09-build-apk.sh https://souq.syrz1.com"
```

السكربت يرفع `latest_version` و`min_version` و`apk_sha256` في إعدادات التطبيق
تلقائيًا — فتظهر لافتة التحديث للمستخدمين بلا أي خطوة إضافية.

> ⚠️ ارفع رقم `version` في `app/app.json` **قبل** كل بناء جديد، وإلا استُبدل
> الملف القديم بالجديد بالاسم نفسه ولن يعرف أحد أن هناك تحديثًا.

**حجم الملف:** 43 ميغابايت. كان 81 قبل حذف معماريتَي `x86` و`x86_64` — وهما
للمحاكيات فقط ولا يستخدمهما أي هاتف. الأمر مضبوط في `09-build-apk.sh` عبر
`reactNativeArchitectures`.

---

## ⚠️ أمور ناقصة عن قصد

### 1. النطاق مؤقّت

`souq.syrz1.com` نطاق فرعي مُعار. عند شراء النطاق النهائي:
سجلّ `A` جديد (سحابة رمادية) ← `bash /root/06-ssl.sh النطاق البريد` ←
إعادة بناء APK بالعنوان الجديد.

### 2. (سابقًا: لا يوجد نطاق ولا شهادة — تمّ ✅)

الموقع يعمل على `http://` لا `https://`. هذا **مقبول للاختبار فقط**، وغير مقبول
للإطلاق: كلمات المرور تمرّ بلا تشفير، وأندرويد يمنع الاتصال غير المشفّر افتراضيًا
في التطبيقات الحقيقية.

شهادة SSL المجانية (Let's Encrypt) **لا تُصدَر لرقم IP** — تحتاج نطاقًا.
بمجرد شراء النطاق وتوجيهه إلى `46.224.188.126`:

```bash
apt-get install -y certbot python3-certbot-nginx
certbot --nginx -d souqraqqa.com -d www.souqraqqa.com
```

ثم تُحدَّث `ALLOWED_HOSTS` و`PUBLIC_SITE_URL` في `/etc/souq/app.env`.

### 2. النسخ الاحتياطي على الخادم نفسه

نسخة تعيش على الخادم لا تحميك من ضياع الخادم. الخطوة الناقصة: نقلها خارجه —
Hetzner Storage Box (~4 دولار شهريًا) أو نسخ يومي إلى جهازك:

```bash
rsync -avz -e "ssh -i ~/.ssh/souq_raqqa" \
  root@46.224.188.126:/srv/souq/backups/ ./backups/
```

### 3. لا يوجد Cloudflare — وهذا مقصود

`plan2` §7.3 ينصّ صراحة: **لا نضع Cloudflare قبل اختبار الوصول من سوريا**.
قد يضيف طبقة تحدٍّ (CAPTCHA) للزوّار السوريين فينكسر التطبيق بلا سبب ظاهر.
