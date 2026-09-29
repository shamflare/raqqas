#!/usr/bin/env bash
#
# سوق الرقة — Nginx
#
# يخدم: /api و /django-admin من Django · /media و /static مباشرة من القرص
#        /  الصفحة التعريفية  ·  /apk  ملف التطبيق
#
set -euo pipefail

APP_DIR="/srv/souq"

install -d -o souq -g souq "$APP_DIR/web" "$APP_DIR/apk"

cat > /etc/nginx/sites-available/souq <<'NGINX'
upstream souq_app {
    server unix:/run/souq.sock fail_timeout=0;
}

server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    root /srv/souq/web;
    index index.html;

    # ملفات كبيرة (صور الإعلانات) وطلبات بطيئة — الإنترنت في الرقة ضعيف
    client_max_body_size 15M;
    client_body_timeout 120s;

    # ضغط كل ما يُضغط — كل كيلوبايت محسوب.
    # داخل server لا http: ملف nginx.conf الأصلي يضبط gzip، وتكراره في نطاقه خطأ.
    gzip_vary on;
    gzip_min_length 512;
    gzip_proxied any;
    gzip_types text/plain text/css text/javascript application/javascript
               application/json application/xml image/svg+xml;

    access_log /var/log/nginx/souq.access.log;
    error_log  /var/log/nginx/souq.error.log;

    # ترويسات أمان أساسية
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options SAMEORIGIN always;
    add_header Referrer-Policy strict-origin-when-cross-origin always;

    # ---------------------------------------------------------- الواجهة البرمجية
    # رفع فيديو الإعلان — الحدّ العام لا يتّسع لمقطع دقيقة من جوال (16-video.sh)
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

    location /api/ {
        proxy_pass http://souq_app;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_read_timeout 60s;
    }

    location /django-admin/ {
        proxy_pass http://souq_app;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # ---------------------------------------------------------- الملفات
    # الصور لا تتغيّر بعد رفعها — نخزّنها في المتصفّح طويلًا
    location /media/ {
        alias /srv/souq/media/;
        expires 30d;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    location /static/ {
        alias /srv/souq/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    # حزم التحديث عن بُعد — ملفات ثابتة باسم فيه بصمتها، فلا تتغيّر أبدًا
    location /updates/ {
        alias /srv/souq/updates/;
        expires 365d;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    # ملف التطبيق
    location /apk/ {
        alias /srv/souq/apk/;
        add_header Content-Disposition "attachment";
        types { application/vnd.android.package-archive apk; }
        default_type application/vnd.android.package-archive;
    }

    # ---------------------------------------------------------- الصفحة التعريفية
    location / {
        try_files $uri $uri/ /index.html;
    }
}
NGINX

rm -f /etc/nginx/sites-enabled/default
ln -sfn /etc/nginx/sites-available/souq /etc/nginx/sites-enabled/souq

nginx -t
systemctl reload nginx
systemctl enable nginx >/dev/null

echo "✅ Nginx يعمل"
