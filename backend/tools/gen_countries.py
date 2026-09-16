"""
يولّد `app/src/data/countries.ts` — قائمة دول العالم لحقل الهاتف في التطبيق.

    python backend/tools/gen_countries.py

مصدران، كلاهما مرجعي ولا يُكتب بيد:

- **`phonenumbers`** (نقل `libphonenumber` من غوغل) — رموز النداء ومثال رقم
  موبايل لكل دولة. المثال يصير نصًّا إرشاديًا في الحقل، فيرى المستخدم شكل
  الرقم المتوقَّع في بلده لا شكله في سوريا.
- **CLDR عبر `babel`** — أسماء الدول بالعربية والتركية والإنكليزية. هذه بيانات
  يونيكود الرسمية، لا ترجمة نكتبها نحن ونخطئ فيها.

`babel` أداة توليد فقط ولا يحتاجها الخادم في التشغيل — لذلك ليست في
`requirements.txt`. لتشغيل السكربت: `pip install babel`.

العلم **لا يُولَّد هنا**: يُحسب في التطبيق من حرفَي ISO (انظر `flagOf` في
`countries.ts`). إضافته هنا كانت ستُثقل الحزمة بـ245 رمزًا تعبيريًا بلا فائدة.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import phonenumbers
    from babel import Locale
except ImportError as exc:  # pragma: no cover - أداة تطوير
    sys.exit(f"ينقص: {exc.name}. ثبّته بـ: pip install phonenumbers babel")

OUTPUT = Path(__file__).resolve().parents[2] / "app" / "src" / "data" / "countries.ts"

LANGS = ("ar", "tr", "en")

#: الدول التي تتصدّر القائمة قبل الترتيب الأبجدي.
#:
#: مستخدمو سوق الرقة: أهل المدينة، ومن نزح إلى الجوار، ومن استقرّ في أوروبا.
#: هؤلاء تسعة من كل عشرة — ولا معنى لجعلهم يمرّون على 245 صفًا في كل تسجيل.
SUGGESTED = ["SY", "TR", "LB", "JO", "IQ", "EG", "SA", "AE", "DE", "SE"]


def example_national(region: str) -> str:
    """مثال رقم موبايل بصيغته المحلية — نصّ إرشادي في الحقل."""
    number = phonenumbers.example_number_for_type(
        region, phonenumbers.PhoneNumberType.MOBILE
    )
    if number is None:
        return ""
    national = phonenumbers.format_number(
        number, phonenumbers.PhoneNumberFormat.NATIONAL
    )
    # الحقل يأخذ الرقم بلا صفر البادئة المحلية — رمز الدولة يقوم مقامه
    return national.lstrip("0").strip()


def build() -> list[dict]:
    names = {lang: Locale(lang).territories for lang in LANGS}
    rows = []
    for region in sorted(phonenumbers.SUPPORTED_REGIONS):
        english = names["en"].get(region)
        if not english:
            # إقليم بلا اسم في CLDR — لا نعرضه بحرفين مبهمين للمستخدم
            continue
        rows.append({
            "iso": region,
            "dial": str(phonenumbers.country_code_for_region(region)),
            "names": {lang: names[lang].get(region, english) for lang in LANGS},
            "example": example_national(region),
        })
    return rows


def render(rows: list[dict]) -> str:
    def esc(value: str) -> str:
        return value.replace("\\", "\\\\").replace("'", "\\'")

    lines = []
    for row in rows:
        localized = ", ".join(f"{lang}: '{esc(row['names'][lang])}'" for lang in LANGS)
        lines.append(
            f"  {{ iso: '{row['iso']}', dial: '{row['dial']}', "
            f"names: {{ {localized} }}, example: '{esc(row['example'])}' }},"
        )

    suggested = ", ".join(f"'{iso}'" for iso in SUGGESTED)
    body = "\n".join(lines)
    return f"""/**
 * دول العالم لحقل الهاتف — **ملف مولَّد، لا يُحرَّر بيد**.
 *
 * يُعاد توليده بـ: python backend/tools/gen_countries.py
 * المصدر: libphonenumber (رموز النداء والأمثلة) و CLDR (الأسماء بثلاث لغات).
 */

export type Country = {{
  /** حرفا ISO 3166-1 — المفتاح، ومنه يُحسب العلم */
  iso: string;
  /** رمز النداء بلا + */
  dial: string;
  names: {{ ar: string; tr: string; en: string }};
  /** مثال رقم موبايل محلي — نصّ إرشادي في الحقل */
  example: string;
}};

/** الدول التي تتصدّر القائمة — تغطّي الغالبية العظمى من المستخدمين. */
export const SUGGESTED_COUNTRIES = [{suggested}];

/** الدولة المفترضة حين يتعذّر استنتاج غيرها. */
export const DEFAULT_COUNTRY = 'SY';

/**
 * العلم من حرفَي ISO: كل حرف يُزاح إلى رمز «المؤشّر الإقليمي» المقابل،
 * وحرفان متجاوران منهما يرسمهما النظام علمًا. أرخص من تخزين 245 رمزًا.
 */
export function flagOf(iso: string): string {{
  return iso
    .toUpperCase()
    .replace(/./g, (char) => String.fromCodePoint(127397 + char.charCodeAt(0)));
}}

export const COUNTRIES: Country[] = [
{body}
];

const BY_ISO = new Map(COUNTRIES.map((country) => [country.iso, country]));

export function countryOf(iso: string | undefined | null): Country | undefined {{
  return iso ? BY_ISO.get(iso.toUpperCase()) : undefined;
}}
"""


def main() -> None:
    rows = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    # بايت صريح: `write_text` على ويندوز يكتب CRLF فيختلف الملف بلا سبب
    OUTPUT.write_bytes(render(rows).encode("utf-8"))
    print(f"{OUTPUT} — {len(rows)} دولة")


if __name__ == "__main__":
    main()
