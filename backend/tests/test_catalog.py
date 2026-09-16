"""شجرة الأقسام — أهمّها أن عدّاد القسم الرئيسي يشمل أبناءه."""

from apps.catalog.models import Category
from apps.listings.models import Listing

from .test_access_rules import BaseAPITest


class CategoryTreeTests(BaseAPITest):
    def test_root_count_includes_subcategories(self):
        """
        الإعلان الوحيد في بيانات الاختبار منشور في القسم الفرعي «هواتف».
        القسم الرئيسي «موبايلات» يجب أن يعرض 1 لا 0.
        """
        response = self.guest.get("/api/v1/categories")
        root = next(row for row in response.data if row["slug"] == "mobiles")

        self.assertEqual(root["listings_count"], 1)
        child = next(row for row in root["children"] if row["slug"] == "phones")
        self.assertEqual(child["listings_count"], 1)

    def test_count_grows_with_a_second_subcategory(self):
        accessories = Category.objects.create(
            slug="accessories", name_ar="إكسسوارات", parent=self.parent
        )
        listing = Listing.objects.create(
            user=self.seller, category=accessories, city=self.city,
            title="جراب هاتف بحالة جيدة", description="جراب أصلي بلا خدوش.",
            price=15000,
        )
        listing.publish()

        response = self.guest.get("/api/v1/categories")
        root = next(row for row in response.data if row["slug"] == "mobiles")
        self.assertEqual(root["listings_count"], 2)

    def test_pending_listings_are_not_counted(self):
        Listing.objects.create(
            user=self.seller, category=self.category, city=self.city,
            title="هاتف قيد المراجعة الآن", description="لم يُنشر بعد إطلاقًا.",
            price=1000, status=Listing.Status.PENDING,
        )
        response = self.guest.get("/api/v1/categories")
        root = next(row for row in response.data if row["slug"] == "mobiles")
        self.assertEqual(root["listings_count"], 1)

    def test_home_returns_same_tree(self):
        response = self.guest.get("/api/v1/home")
        root = next(row for row in response.data["categories"] if row["slug"] == "mobiles")
        self.assertEqual(root["listings_count"], 1)

    def test_inactive_category_is_hidden(self):
        self.parent.is_active = False
        self.parent.save()
        response = self.guest.get("/api/v1/categories")
        self.assertFalse(any(row["slug"] == "mobiles" for row in response.data))


class CategoryOrderTests(BaseAPITest):
    """
    ترتيب `sort_order` الذي يضعه الأدمن يجب أن يصل إلى التطبيق كما هو.

    هذا ليس اختبارًا نظريًا: العطب وقع فعلًا على تطبيق منشور. `annotate(Count)`
    يولّد `GROUP BY`، ومُصرِّف Django يرمي `Meta.ordering` بصمت متى وُجد —
    فظهرت «السيارات» (ترتيبها ١) ثامنةً و«الوظائف» (ترتيبها ٩) أولى.

    الأسماء هنا **معكوسة أبجديًا مقابل الترتيب** عمدًا: لو سقط الترتيب إلى
    `name_ar` وحده لظهر الخلل، ولو سقط إلى ترتيب الإدراج كذلك.
    """

    ORDERED = [
        ("cars", "السيارات", 1),
        ("realestate", "العقارات", 2),
        ("jobs", "الوظائف", 3),
    ]

    def setUp(self):
        super().setUp()
        # الإدراج بترتيب مقلوب — فالمخرج الصحيح لا يمكن أن يكون ترتيب الإدراج
        for slug, name, order in reversed(self.ORDERED):
            Category.objects.create(slug=slug, name_ar=name, sort_order=order)

    def _slugs(self, rows, only=None):
        """
        أقسام بيانات الاختبار الأساسية لا تُحذف (إعلان مرتبط بها بـ PROTECT)،
        فنقارن تسلسل أقسامنا داخل الرد — وهو ما يثبت الترتيب بلا ضجيج.
        """
        wanted = only if only is not None else [row[0] for row in self.ORDERED]
        return [row["slug"] for row in rows if row["slug"] in wanted]

    def test_categories_endpoint_respects_sort_order(self):
        response = self.guest.get("/api/v1/categories")
        self.assertEqual(self._slugs(response.data), [row[0] for row in self.ORDERED])

    def test_home_endpoint_respects_sort_order(self):
        response = self.guest.get("/api/v1/home")
        self.assertEqual(
            self._slugs(response.data["categories"]), [row[0] for row in self.ORDERED]
        )

    def test_subcategories_respect_sort_order(self):
        """الأبناء يمرّون بـ `Prefetch` — استعلام مستقلّ يصيبه العطب نفسه."""
        parent = Category.objects.get(slug="cars")
        for slug, name, order in reversed([("used", "مستعملة", 1), ("new", "جديدة", 2)]):
            Category.objects.create(slug=slug, name_ar=name, parent=parent, sort_order=order)

        response = self.guest.get("/api/v1/categories")
        root = next(row for row in response.data if row["slug"] == "cars")
        self.assertEqual(self._slugs(root["children"], ["used", "new"]), ["used", "new"])

    def test_admin_list_respects_sort_order(self):
        admin = self.as_user(self.admin)
        response = admin.get("/api/v1/admin/categories")
        self.assertEqual(self._slugs(response.data), [row[0] for row in self.ORDERED])

    def test_changing_sort_order_changes_app_order(self):
        """ما يفعله الأدمن فعلًا: يغيّر الرقم، فيتغيّر ما يراه المستخدم."""
        admin = self.as_user(self.admin)
        jobs = Category.objects.get(slug="jobs")
        response = admin.patch(
            f"/api/v1/admin/categories/{jobs.id}", {"sort_order": 0}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)

        response = self.guest.get("/api/v1/categories")
        self.assertEqual(self._slugs(response.data), ["jobs", "cars", "realestate"])
