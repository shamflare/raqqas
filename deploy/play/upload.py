#!/usr/bin/env python
"""
رفع حزمة .aab إلى Google Play عبر Play Developer API.

لماذا سكربت بايثون لا fastlane؟ لأن fastlane يحتاج Ruby ومنظومتها كاملة على
خادم بذاكرة 4 جيجا يبني أندرويد أصلًا. وهنا نحتاج أربعة نداءات HTTP لا أكثر،
وبايثون مثبَّت للخلفية على أي حال.

═══ كيف يعمل رفع Play؟ ═══

Play لا يقبل «ارفع هذا الملف» في نداء واحد. العملية معاملة (transaction) من
أربع خطوات، وأي خطأ قبل الأخيرة يترك كل شيء كما كان:

    edits.insert          افتح مسودّة تعديل
    edits.bundles.upload  ارفع الحزمة داخلها
    edits.tracks.update   عيّنها لمسار (internal / production …)
    edits.commit          ثبّت — وهنا فقط يصير التغيير واقعًا

هذا التصميم في صالحنا: لو فشل الرفع في منتصفه لا يبقى في حسابك إصدار نصف
مرفوع، بل لا شيء إطلاقًا.

الاستعمال:
    python upload.py --aab /srv/souq/aab/souq-raqqa-latest.aab \\
                     --track internal --notes "إصلاح لوحة المفاتيح"

    python upload.py --status          # ما هو منشور الآن في كل مسار
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PACKAGE = "com.souqraqqa.app"
CREDENTIALS = "/etc/souq/play-service-account.json"

# المسارات كما تسمّيها واجهة Play — وليست كما تظهر في الكونسول بالعربية
TRACKS = {
    "internal": "الاختبار الداخلي — فوري، حتى 100 مختبِر، بلا مراجعة",
    "alpha": "الاختبار المغلق",
    "beta": "الاختبار المفتوح",
    "production": "الإنتاج — النشر للجميع",
}

# اللغات التي نكتب بها ملاحظات الإصدار. يجب أن تكون مفعّلة في الكونسول،
# وإلا رفضت الواجهة الرد كاملًا برسالة غامضة عن «لغة غير مدعومة».
RELEASE_NOTE_LANGS = ["ar", "tr", "en-US"]


def fail(message: str, hint: str = "") -> None:
    print(f"❌ {message}", file=sys.stderr)
    if hint:
        print(f"   {hint}", file=sys.stderr)
    sys.exit(1)


def build_service(credentials_path: str):
    """يبني عميل الواجهة، ويشرح كل سبب فشل شائع بدل رمي أثر استدعاء خام."""
    try:
        from google.oauth2 import service_account  # type: ignore
        from googleapiclient.discovery import build  # type: ignore
    except ImportError:
        fail(
            "مكتبة عميل Google غير مثبَّتة.",
            "ثبّتها مرة واحدة:\n"
            "   /srv/souq/venv/bin/pip install google-api-python-client google-auth",
        )

    path = Path(credentials_path)
    if not path.exists():
        fail(
            f"ملف حساب الخدمة غير موجود: {credentials_path}",
            "أنشئه من Google Cloud Console وانقله إلى الخادم — الخطوات في deploy/PLAY.md §3.2",
        )

    try:
        creds = service_account.Credentials.from_service_account_file(
            str(path), scopes=["https://www.googleapis.com/auth/androidpublisher"]
        )
    except (ValueError, KeyError) as exc:
        fail(f"ملف حساب الخدمة غير صالح: {exc}")

    return build("androidpublisher", "v3", credentials=creds, cache_discovery=False)


def explain_http_error(exc) -> None:
    """يترجم أخطاء Play الشائعة إلى ما يجب فعله."""
    status = getattr(getattr(exc, "resp", None), "status", None)
    body = getattr(exc, "content", b"")
    text = body.decode("utf-8", "replace") if isinstance(body, bytes) else str(body)

    hints = {
        401: "حساب الخدمة غير مصرَّح له. تأكّد من دعوته في Play Console ‹ Users and permissions.",
        403: "حساب الخدمة مدعوّ لكن بلا صلاحية على هذا التطبيق، أو الـAPI غير مفعّل في Google Cloud.",
        404: (
            "التطبيق غير موجود في الكونسول بهذا المعرّف، أو لم يُنشأ له أي إصدار بعد.\n"
            "   أول إصدار يجب أن يُرفع يدويًا بسحب الملف — التفصيل في deploy/PLAY.md §3.3"
        ),
    }
    if "apkUpgradeVersionConflict" in text or "versionCode" in text:
        fail(
            "رقم versionCode مستعمَل من قبل.",
            "Play يرفض رقمًا سبق رفعه ولو أُلغي إصداره. ارفع الرقم في app/app.json وابنِ من جديد.",
        )
    fail(f"رفضت واجهة Play الطلب (HTTP {status}).", hints.get(status, text[:500]))


def show_status(service, package: str) -> None:
    """يطبع ما هو منشور الآن في كل مسار — بلا تعديل أي شيء."""
    from googleapiclient.errors import HttpError  # type: ignore

    try:
        edit = service.edits().insert(body={}, packageName=package).execute()
        edit_id = edit["id"]
        result = service.edits().tracks().list(editId=edit_id, packageName=package).execute()
    except HttpError as exc:
        explain_http_error(exc)
        return

    print(f"التطبيق: {package}\n")
    for track in result.get("tracks", []):
        name = track["track"]
        print(f"▶ {name} — {TRACKS.get(name, '')}")
        releases = track.get("releases", [])
        if not releases:
            print("   (لا إصدار)")
        for release in releases:
            codes = ", ".join(str(c) for c in release.get("versionCodes", []))
            print(
                f"   الإصدار {release.get('name', '؟')} · versionCode {codes or '—'} "
                f"· الحالة: {release.get('status')}"
            )
        print()

    # المسودّة تُترك بلا commit عمدًا: القراءة يجب ألّا تغيّر شيئًا
    service.edits().delete(editId=edit_id, packageName=package).execute()


def upload(
    service, package: str, aab: Path | None, track: str, notes: str, rollout: float | None,
    existing_code: int | None = None,
) -> None:
    from googleapiclient.errors import HttpError  # type: ignore

    print(f"▶ فتح مسودّة تعديل…")
    try:
        edit_id = service.edits().insert(body={}, packageName=package).execute()["id"]
    except HttpError as exc:
        explain_http_error(exc)
        return

    try:
        if existing_code is not None:
            # ترقية: الحزمة مرفوعة من قبل (إلى internal مثلًا). رفعها ثانية يُرفض
            # لأن versionCode مستعمَل — فنعيّن الرقم نفسه للمسار الجديد فقط.
            version_code = existing_code
            print(f"▶ ترقية versionCode {version_code} المرفوع سابقًا — بلا رفع جديد")
        else:
            print(f"▶ رفع الحزمة ({round(aab.stat().st_size / 1048576, 1)} ميغابايت)…")
            bundle = (
                service.edits()
                .bundles()
                .upload(editId=edit_id, packageName=package, media_body=str(aab), media_mime_type="application/octet-stream")
                .execute()
            )
            version_code = bundle["versionCode"]
            print(f"   ✓ رُفعت — versionCode {version_code}")

        release: dict = {
            "versionCodes": [str(version_code)],
            "status": "completed",
            "releaseNotes": [
                {"language": lang, "text": notes} for lang in RELEASE_NOTE_LANGS
            ],
        }
        # الطرح التدريجي: نصف المستخدمين اليوم والباقي غدًا. مفيد في الإنتاج
        # لأن خطأً يظهر عند 10% أرخص بكثير من خطأ يظهر عند الجميع.
        if rollout is not None:
            release["status"] = "inProgress"
            release["userFraction"] = rollout

        print(f"▶ تعيينها للمسار «{track}»…")
        service.edits().tracks().update(
            editId=edit_id,
            packageName=package,
            track=track,
            body={"track": track, "releases": [release]},
        ).execute()

        print("▶ تثبيت التعديل…")
        service.edits().commit(editId=edit_id, packageName=package).execute()

    except HttpError as exc:
        # نحذف المسودّة فلا تتراكم مسودّات معلّقة تمنع التعديل التالي
        try:
            service.edits().delete(editId=edit_id, packageName=package).execute()
        except Exception:  # pragma: no cover
            pass
        explain_http_error(exc)
        return

    print()
    print("════════════════════════════════════════════════════")
    print("✅ رُفعت الحزمة إلى Google Play")
    print("════════════════════════════════════════════════════")
    print(f"المسار:       {track} — {TRACKS.get(track, '')}")
    print(f"versionCode:  {version_code}")
    if rollout is not None:
        print(f"الطرح:        {int(rollout * 100)}% من المستخدمين")
    print()
    print("تابعها هنا:")
    print(f"  https://play.google.com/console/u/0/developers/app/{package}/tracks/{track}")
    if track == "production":
        print()
        print("⚠️ المراجعة قد تستغرق ساعات إلى أيام قبل أن يراها الناس.")


def main() -> None:
    parser = argparse.ArgumentParser(description="رفع حزمة إلى Google Play")
    parser.add_argument("--aab", default="/srv/souq/aab/souq-raqqa-latest.aab")
    parser.add_argument("--track", default="internal", choices=sorted(TRACKS))
    parser.add_argument("--notes", default="تحسينات وإصلاحات.")
    parser.add_argument("--package", default=PACKAGE)
    parser.add_argument("--credentials", default=CREDENTIALS)
    parser.add_argument(
        "--rollout",
        type=float,
        default=None,
        help="طرح تدريجي: 0.1 = عُشر المستخدمين. بلا هذا يصل الجميع دفعة واحدة.",
    )
    parser.add_argument("--status", action="store_true", help="اعرض ما هو منشور ولا ترفع شيئًا")
    parser.add_argument(
        "--version-code",
        type=int,
        default=None,
        help="ترقية حزمة مرفوعة سابقًا إلى هذا المسار بلا رفع جديد (مثلًا من internal إلى production)",
    )
    args = parser.parse_args()

    service = build_service(args.credentials)

    if args.status:
        show_status(service, args.package)
        return

    if args.version_code is not None:
        if args.rollout is not None and not (0 < args.rollout <= 1):
            fail("قيمة --rollout يجب أن تكون بين 0 و 1 (مثلًا 0.1 لعُشر المستخدمين).")
        upload(service, args.package, None, args.track, args.notes, args.rollout, args.version_code)
        return

    aab = Path(args.aab).resolve()
    if not aab.exists():
        fail(f"الحزمة غير موجودة: {aab}", "ابنِها أولًا: bash 12-build-aab.sh https://souq.syrz1.com")
    if aab.suffix != ".aab":
        fail(f"الملف ليس حزمة .aab: {aab}", "Play يرفض ملفات APK للتطبيقات الجديدة.")
    if args.rollout is not None and not (0 < args.rollout <= 1):
        fail("قيمة --rollout يجب أن تكون بين 0 و 1 (مثلًا 0.1 لعُشر المستخدمين).")

    upload(service, args.package, aab, args.track, args.notes, args.rollout)


if __name__ == "__main__":
    main()
