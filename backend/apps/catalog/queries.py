"""
شجرة الأقسام — استعلام واحد تستعمله شاشتا «الرئيسية» و«الأقسام».

كان الاستعلام مكتوبًا مرّتين (`catalog.views.category_tree` و
`listings.views.home_summary`)، فوقع فيهما العطب نفسه ولزم إصلاحه مرّتين.
هنا مكان واحد، فلا يُصلَح أحدهما ويُنسى الآخر.
"""

from __future__ import annotations

from django.db.models import Count, Prefetch, Q

from .models import Category

PUBLISHED = Q(listings__status="published")

#: ترتيب الأقسام كما يحدّده الأدمن في اللوحة، ثم الاسم عند التساوي.
CATEGORY_ORDER = ("sort_order", "name_ar")


def category_tree_queryset():
    """
    الأقسام الرئيسية المفعّلة، مع أبنائها وعدّاد الإعلانات المنشورة لكلٍّ منها.

    ⚠️ `order_by` هنا **ليس تكرارًا** لـ `Category.Meta.ordering` — بل ضرورة.

    `annotate(Count(...))` يولّد `GROUP BY`، ومُصرِّف Django يرمي ترتيب `Meta`
    بصمت متى وُجد `GROUP BY` (`sql/compiler.py`: `if self._meta_ordering:
    order_by = None`). النتيجة كانت أن ترتيب الأدمن لا يصل إلى التطبيق أبدًا:
    «السيارات» ترتيبها ١ وكانت تظهر ثامنة، و«الوظائف» ترتيبها ٩ وتظهر أولى.
    ولا خطأ يُرفع ولا تحذير — ولهذا بقي العطب حيًّا بعد النشر.

    `order_by()` الصريح لا يُرمى. وهو لازم على الأبناء أيضًا: `Prefetch`
    استعلام مستقلّ يصيبه العطب نفسه.
    """
    children = (
        Category.objects.active()
        .annotate(listings_count=Count("listings", filter=PUBLISHED))
        .order_by(*CATEGORY_ORDER)
    )
    return (
        Category.objects.active()
        .roots()
        .annotate(listings_count=Count("listings", filter=PUBLISHED))
        .prefetch_related(Prefetch("children", queryset=children))
        .order_by(*CATEGORY_ORDER)
    )
