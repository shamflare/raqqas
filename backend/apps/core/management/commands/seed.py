"""
تعبئة البيانات الأولية: المدينة والأحياء والأقسام وأسباب الرفض.

المصدر: design/assets/js/data.js — نفس القوائم التي في النموذج البصري،
مضافًا إليها الترجمة التركية والإنكليزية (plan2 §9 بند 12 و15 — بانتظار مراجعتك).

    python manage.py seed              # البيانات المرجعية فقط
    python manage.py seed --demo       # + مستخدمون وإعلانات تجريبية
    python manage.py seed --reset      # يحذف البيانات المرجعية ويعيد بناءها
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Category, City, Neighborhood
from apps.core.models import AppConfig
from apps.listings.models import Listing, RejectionReason

# المحافظات السورية الأربع عشرة. الرقة أولًا لأنها سوق الإطلاق،
# والباقي بالترتيب الإداري المعروف.
CITIES = [
    {"slug": "raqqa", "ar": "الرقة", "tr": "Rakka", "en": "Raqqa", "order": 1},
    {"slug": "damascus", "ar": "دمشق", "tr": "Şam", "en": "Damascus", "order": 2},
    {"slug": "rif-dimashq", "ar": "ريف دمشق", "tr": "Şam Kırsalı", "en": "Rif Dimashq", "order": 3},
    {"slug": "aleppo", "ar": "حلب", "tr": "Halep", "en": "Aleppo", "order": 4},
    {"slug": "homs", "ar": "حمص", "tr": "Humus", "en": "Homs", "order": 5},
    {"slug": "hama", "ar": "حماة", "tr": "Hama", "en": "Hama", "order": 6},
    {"slug": "latakia", "ar": "اللاذقية", "tr": "Lazkiye", "en": "Latakia", "order": 7},
    {"slug": "tartus", "ar": "طرطوس", "tr": "Tartus", "en": "Tartus", "order": 8},
    {"slug": "idlib", "ar": "إدلب", "tr": "İdlib", "en": "Idlib", "order": 9},
    {"slug": "deir-ez-zor", "ar": "دير الزور", "tr": "Deyrizor", "en": "Deir ez-Zor", "order": 10},
    {"slug": "hasakah", "ar": "الحسكة", "tr": "Haseke", "en": "Al-Hasakah", "order": 11},
    {"slug": "daraa", "ar": "درعا", "tr": "Dera", "en": "Daraa", "order": 12},
    {"slug": "suwayda", "ar": "السويداء", "tr": "Süveyda", "en": "As-Suwayda", "order": 13},
    {"slug": "quneitra", "ar": "القنيطرة", "tr": "Kuneytra", "en": "Quneitra", "order": 14},
]

# أحياء الرقة — من design/assets/js/data.js
NEIGHBORHOODS = [
    ("mashlab", "المشلب", "Meşlab", "Al-Mashlab"),
    ("rumaila", "الرميلة", "Rumeyle", "Al-Rumaila"),
    ("daraiya", "الدرعية", "Dariye", "Al-Daraiya"),
    ("hisham", "هشام بن عبد الملك", "Hişam bin Abdülmelik", "Hisham Bin Abdulmalik"),
    ("firdous", "الفردوس", "Firdevs", "Al-Firdous"),
    ("romaniya", "الرومانية", "Rumaniye", "Al-Romaniya"),
    ("mansour", "المنصور", "Mansur", "Al-Mansour"),
    ("nahda", "النهضة", "Nahda", "Al-Nahda"),
    ("andalus", "الأندلس", "Endülüs", "Al-Andalus"),
    ("tishreen", "تشرين", "Teşrin", "Tishreen"),
    ("sabahiya", "السباهية", "Sebahiye", "Al-Sabahiya"),
    ("wadi", "الوادي", "Vadi", "Al-Wadi"),
    ("thakna", "الثكنة", "Kışla", "Al-Thakna"),
    ("sinaa", "الصناعة", "Sanayi", "Al-Sinaa"),
    ("jazra", "الجزرة", "Cezre", "Al-Jazra"),
    ("falah", "حي الفلاح", "Felah", "Al-Falah"),
    ("muroor", "المرور", "Trafik", "Al-Muroor"),
    ("ameen", "الأمين", "Emin", "Al-Ameen"),
    ("qadisiya", "القادسية", "Kadisiye", "Al-Qadisiya"),
    ("outside", "خارج المدينة", "Şehir dışı", "Outside the city"),
]

# الأقسام — من design/assets/js/data.js
CATEGORIES = [
    {
        "slug": "cars", "icon": "🚗",
        "ar": "السيارات", "tr": "Araçlar", "en": "Vehicles",
        "subs": [
            ("cars-sale", "سيارات للبيع", "Satılık araba", "Cars for sale"),
            ("motorcycles", "دراجات نارية", "Motosiklet", "Motorcycles"),
            ("car-parts", "قطع غيار", "Yedek parça", "Spare parts"),
            ("tires", "إطارات", "Lastik", "Tires"),
            ("trucks", "شاحنات", "Kamyon", "Trucks"),
            ("car-rent", "تأجير سيارات", "Araç kiralama", "Car rental"),
        ],
    },
    {
        "slug": "realestate", "icon": "🏠",
        "ar": "العقارات", "tr": "Emlak", "en": "Real estate",
        "subs": [
            ("houses-sale", "بيوت للبيع", "Satılık ev", "Houses for sale"),
            ("houses-rent", "بيوت للإيجار", "Kiralık ev", "Houses for rent"),
            ("apartments", "شقق", "Daire", "Apartments"),
            ("land", "أراضٍ", "Arsa", "Land"),
            ("shops", "محلات تجارية", "Dükkân", "Shops"),
            ("warehouses", "مستودعات", "Depo", "Warehouses"),
        ],
    },
    {
        "slug": "mobiles", "icon": "📱",
        "ar": "الموبايلات والإلكترونيات", "tr": "Telefon ve elektronik",
        "en": "Phones & electronics",
        "subs": [
            ("phones", "موبايلات", "Cep telefonu", "Mobile phones"),
            ("laptops", "لابتوبات", "Dizüstü bilgisayar", "Laptops"),
            ("tvs", "تلفزيونات", "Televizyon", "TVs"),
            ("accessories", "إكسسوارات", "Aksesuar", "Accessories"),
            ("games", "ألعاب", "Oyun", "Games"),
            ("cameras", "كاميرات", "Kamera", "Cameras"),
        ],
    },
    {
        "slug": "furniture", "icon": "🪑",
        "ar": "الأثاث والمنزل", "tr": "Mobilya ve ev", "en": "Furniture & home",
        "subs": [
            ("bedrooms", "غرف نوم", "Yatak odası", "Bedrooms"),
            ("sofas", "كنبايات", "Koltuk", "Sofas"),
            ("appliances", "أجهزة منزلية", "Beyaz eşya", "Home appliances"),
            ("kitchens", "مطابخ", "Mutfak", "Kitchens"),
            ("decor", "ديكور", "Dekorasyon", "Decor"),
            ("carpets", "سجاد", "Halı", "Carpets"),
        ],
    },
    {
        "slug": "clothes", "icon": "👕",
        "ar": "الملابس", "tr": "Giyim", "en": "Clothing",
        "subs": [
            ("men", "رجالي", "Erkek", "Men"),
            ("women", "نسائي", "Kadın", "Women"),
            ("kids", "أطفال", "Çocuk", "Kids"),
            ("shoes", "أحذية", "Ayakkabı", "Shoes"),
            ("bags", "حقائب", "Çanta", "Bags"),
            ("watches", "ساعات", "Saat", "Watches"),
        ],
    },
    {
        "slug": "animals", "icon": "🐄",
        "ar": "الحيوانات", "tr": "Hayvanlar", "en": "Animals",
        "subs": [
            ("sheep", "أغنام", "Koyun", "Sheep"),
            ("cows", "أبقار", "İnek", "Cattle"),
            ("birds", "طيور", "Kuş", "Birds"),
            ("pets", "حيوانات أليفة", "Evcil hayvan", "Pets"),
            ("feed", "أعلاف", "Yem", "Animal feed"),
        ],
    },
    {
        "slug": "tools", "icon": "🛠️",
        "ar": "الأدوات والمعدات", "tr": "Alet ve ekipman", "en": "Tools & equipment",
        "subs": [
            ("farm-equipment", "معدات زراعية", "Tarım ekipmanı", "Farm equipment"),
            ("hand-tools", "عدد يدوية", "El aleti", "Hand tools"),
            ("generators", "مولدات", "Jeneratör", "Generators"),
            ("pumps", "مضخات", "Pompa", "Pumps"),
            ("construction", "معدات بناء", "İnşaat ekipmanı", "Construction equipment"),
        ],
    },
    {
        "slug": "jobs", "icon": "💼",
        "ar": "الوظائف", "tr": "İş ilanları", "en": "Jobs",
        "subs": [
            ("hiring", "مطلوب موظف", "Eleman aranıyor", "Hiring"),
            ("seeking", "أبحث عن عمل", "İş arıyorum", "Seeking work"),
            ("remote", "عمل عن بعد", "Uzaktan çalışma", "Remote work"),
            ("training", "تدريب", "Staj", "Training"),
        ],
    },
    {
        "slug": "food", "icon": "🛒",
        "ar": "المواد الغذائية", "tr": "Gıda", "en": "Food",
        "subs": [
            ("produce", "خضار وفواكه", "Sebze ve meyve", "Fruit & vegetables"),
            ("groceries", "مواد تموينية", "Bakkaliye", "Groceries"),
            ("homemade", "منتجات بيت", "Ev ürünleri", "Homemade products"),
            ("sweets", "حلويات", "Tatlı", "Sweets"),
            ("meat", "لحوم", "Et", "Meat"),
        ],
    },
    {
        "slug": "services", "icon": "🔧",
        "ar": "الخدمات", "tr": "Hizmetler", "en": "Services",
        "subs": [
            ("maintenance", "صيانة", "Tamir", "Maintenance"),
            ("moving", "نقل وشحن", "Nakliye", "Moving & shipping"),
            ("tutoring", "تعليم وتدريس", "Eğitim", "Tutoring"),
            ("crafts", "حرف ومهن", "Zanaat", "Crafts & trades"),
            ("cleaning", "تنظيف", "Temizlik", "Cleaning"),
            ("design", "تصميم", "Tasarım", "Design"),
        ],
    },
    {
        "slug": "other", "icon": "📦",
        "ar": "أخرى", "tr": "Diğer", "en": "Other",
        "subs": [("misc", "متنوّع", "Çeşitli", "Miscellaneous")],
    },
]

REJECTION_REASONS = [
    ("الصور غير واضحة — أعد رفع صور أوضح للمنتج.",
     "Fotoğraflar net değil — daha net fotoğraflar yükleyin.",
     "Photos are unclear — please upload clearer photos."),
    ("الوصف ناقص — أضف تفاصيل المنتج وحالته.",
     "Açıklama eksik — ürün detaylarını ekleyin.",
     "Description is incomplete — add product details."),
    ("القسم غير مناسب للمنتج المعروض.",
     "Kategori ürünle uyuşmuyor.",
     "The category doesn't match the item."),
    ("السعر غير منطقي أو مضلّل.",
     "Fiyat gerçekçi değil veya yanıltıcı.",
     "The price is unrealistic or misleading."),
    ("المنتج ممنوع نشره على المنصّة.",
     "Bu ürünün yayınlanması yasak.",
     "This item is not allowed on the platform."),
    ("الإعلان مكرّر — لديك إعلان مطابق منشور.",
     "İlan tekrarlanmış.",
     "Duplicate listing — you already have an identical one."),
    ("معلومات التواصل مكتوبة داخل الصور أو الوصف.",
     "İletişim bilgileri fotoğraf veya açıklamada yazılmış.",
     "Contact details written inside the photos or description."),
]


class Command(BaseCommand):
    help = "تعبئة البيانات الأولية (المدن والأحياء والأقسام وأسباب الرفض)"

    def add_arguments(self, parser):
        parser.add_argument("--demo", action="store_true", help="إضافة بيانات تجريبية")
        parser.add_argument("--reset", action="store_true", help="حذف البيانات المرجعية أولًا")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            self.stdout.write("حذف البيانات المرجعية…")
            Listing.objects.all().delete()
            Category.objects.all().delete()
            Neighborhood.objects.all().delete()
            City.objects.all().delete()
            RejectionReason.objects.all().delete()

        config = AppConfig.get_solo()
        self.stdout.write(self.style.SUCCESS(f"✓ الإعدادات (نسخة {config.version})"))

        # أسعار صرف تجريبية — للتطوير فقط.
        #
        # لا نضعها في القيم الافتراضية للنموذج عمدًا: خادم إنتاج جديد يجب أن
        # يبدأ **بلا أسعار** فلا يعرض تحويلًا مبنيًا على أرقام لم يكتبها أحد.
        # هنا، وفي أمر التعبئة التجريبية وحده، نضع أرقامًا ليُرى أثر الميزة.
        if options["demo"] and not config.rates:
            config.rates = {"SYP": 13000, "TRY": 42, "EUR": 0.92}
            config.rates_updated_at = timezone.now()
            config.save()
            self.stdout.write(self.style.WARNING(
                "  ⚠️ أسعار صرف تجريبية — غيّرها من اللوحة قبل الإطلاق"
            ))

        city = self._seed_cities()
        # الأحياء لم تعد تُستخدم في الإعلانات (صار: محافظة + عنوان يكتبه صاحبه)،
        # لكنها تبقى مُعبّأة لأن إعلانات ما قبل التحويل ما تزال تشير إليها.
        self._seed_neighborhoods(city)
        self._seed_categories()
        self._seed_rejection_reasons()

        if options["demo"]:
            self._seed_demo(city)

        self.stdout.write(self.style.SUCCESS("\n✅ اكتملت التعبئة."))

    # ------------------------------------------------------------------

    def _seed_cities(self) -> City:
        """يعيد الرقة تحديدًا — لا آخر محافظة في القائمة — لأنها مدينة العروض التجريبية."""
        cities = {}
        for row in CITIES:
            city, created = City.objects.get_or_create(
                slug=row["slug"],
                defaults={
                    "name_ar": row["ar"], "name_tr": row["tr"], "name_en": row["en"],
                    "sort_order": row["order"], "is_active": True,
                },
            )
            cities[row["slug"]] = city
            self.stdout.write(f"  {'+' if created else '·'} محافظة: {city.name_ar}")
        return cities["raqqa"]

    def _seed_neighborhoods(self, city: City):
        for order, (slug, ar, tr, en) in enumerate(NEIGHBORHOODS, start=1):
            Neighborhood.objects.get_or_create(
                city=city, slug=slug,
                defaults={"name_ar": ar, "name_tr": tr, "name_en": en,
                          "sort_order": order, "is_active": True},
            )
        self.stdout.write(f"  ✓ {len(NEIGHBORHOODS)} حيًّا")

    def _seed_categories(self):
        """
        ينشئ الناقص فقط — **ولا يلمس قسمًا موجودًا**.

        ⚠️ كان هنا `update_or_create`، و`03-deploy.sh` ينادي `seed` مع **كل
        تحديث للخادم**. فكان كل تحديث يمحو عمل الأدمن كاملًا: الترتيب الذي
        رتّبه، والأسماء التي كتبها بثلاث لغات، والأيقونات التي اختارها —
        بل ويعيد إظهار أقسام أخفاها عمدًا.

        وهذا نصف السبب في أن «ترتيب الأقسام لا يظهر»: النصف الأول أن الـAPI
        كان يرمي الترتيب (`catalog/queries.py`)، والنصف الثاني أن قاعدة
        البيانات نفسها كانت تفقده عند كل نشر.

        القاعدة الآن: **البيانات المرجعية بذرةٌ أولى لا مصدر حقيقة.** ما يكتبه
        الأدمن يفوز دائمًا. وثمنها أن تعديل اسم افتراضي هنا لا يصل الخوادم
        القائمة — وهو ثمن زهيد مقابل ألّا يُمحى عمل بشري.
        """
        subs_total = 0
        created_total = 0
        for order, row in enumerate(CATEGORIES, start=1):
            parent, created = Category.objects.get_or_create(
                slug=row["slug"],
                defaults={
                    "name_ar": row["ar"], "name_tr": row["tr"], "name_en": row["en"],
                    "icon": row["icon"], "sort_order": order,
                    "is_active": True, "parent": None,
                },
            )
            created_total += created
            for sub_order, (slug, ar, tr, en) in enumerate(row["subs"], start=1):
                _, sub_created = Category.objects.get_or_create(
                    slug=slug,
                    defaults={
                        "name_ar": ar, "name_tr": tr, "name_en": en,
                        "parent": parent, "sort_order": sub_order,
                        "icon": "", "is_active": True,
                    },
                )
                created_total += sub_created
                subs_total += 1
        self.stdout.write(
            f"  ✓ {len(CATEGORIES)} قسمًا رئيسيًا و {subs_total} قسمًا فرعيًا "
            f"({created_total} أُنشئ الآن، والباقي كما تركه الأدمن)"
        )

    def _seed_rejection_reasons(self):
        for order, (ar, tr, en) in enumerate(REJECTION_REASONS, start=1):
            RejectionReason.objects.get_or_create(
                name_ar=ar,
                defaults={"name_tr": tr, "name_en": en, "sort_order": order, "is_active": True},
            )
        self.stdout.write(f"  ✓ {len(REJECTION_REASONS)} سبب رفض جاهز")

    # ------------------------------------------------------------------

    def _seed_demo(self, city: City):
        """بيانات تجريبية مطابقة لما في design/assets/js/data.js."""
        from apps.accounts.models import User

        demo_users = [
            ("أحمد الحسن", "0994123456"),
            ("محمد العلي", "0991887220"),
            ("فاطمة خالد", "0995331907"),
            ("معرض النخبة", "0996220441"),
            ("أبو خالد", "0993550118"),
        ]
        users = []
        for name, phone in demo_users:
            user, created = User.objects.get_or_create(
                phone=f"+963{phone[1:]}", defaults={"name": name}
            )
            if created:
                user.set_password("demo1234")
                user.save()
            users.append(user)

        admin, created = User.objects.get_or_create(
            phone="+963900000000",
            defaults={"name": "المدير", "role": User.Role.ADMIN},
        )
        if created:
            admin.set_password("admin1234")
            admin.save()
            self.stdout.write(self.style.WARNING(
                "  ⚠️ حساب مدير تجريبي: 0900000000 / admin1234 — غيّر كلمة المرور فورًا"
            ))

        # العملة جزء من كل عيّنة عمدًا: السوق الحقيقي مختلط — السيارات
        # والعقارات بالدولار، والأجهزة والأثاث بالليرة. البيانات التجريبية
        # التي تستعمل عملة واحدة تخفي أخطاء التحويل بدل أن تكشفها.
        samples = [
            ("iPhone 15 Pro — 256 جيجا — بحالة ممتازة", 1000000, "SYP", "phones", "mashlab", "used", True),
            ("كيا ريو 2015 — فحص كامل — أوتوماتيك", 8500, "USD", "cars-sale", "firdous", "used", True),
            ("بيت عربي للبيع — 200 متر — حي الرميلة", 45000, "USD", "houses-sale", "rumaila", "used", True),
            ("غسالة سامسونغ أوتوماتيك 7 كيلو", 450000, "SYP", "appliances", "daraiya", "used", False),
            ("لابتوب Dell i7 الجيل العاشر — 16GB RAM", 620, "USD", "laptops", "mansour", "used", False),
            ("غرفة نوم كاملة خشب زان — جديدة", 3200000, "SYP", "bedrooms", "hisham", "new", False),
            ("مطلوب محاسب لشركة تجارية — دوام كامل", None, "USD", "hiring", "sinaa", "new", False),
            ("20 رأس غنم عواس — للبيع جملة", 4500, "USD", "sheep", "outside", "new", False),
            ("مولدة كهرباء 5 كيلو ديزل — صينية", 950, "USD", "generators", "jazra", "used", False),
            ("خدمة نقل أثاث داخل وخارج الرقة", None, "USD", "moving", "muroor", "new", False),
            ("تلفزيون LG سمارت 55 إنش 4K", 780000, "SYP", "tvs", "nahda", "used", False),
            ("دراجة نارية هوندا 150 — موديل 2021", 45000, "TRY", "motorcycles", "wadi", "used", False),
        ]

        created_count = 0
        for index, (title, price, currency, category_slug, hood_slug, condition, featured) in enumerate(samples):
            if Listing.objects.filter(title=title).exists():
                continue
            category = Category.objects.filter(slug=category_slug).first()
            hood = Neighborhood.objects.filter(slug=hood_slug, city=city).first()
            if not category:
                continue
            listing = Listing.objects.create(
                user=users[index % len(users)],
                category=category,
                city=city,
                address=hood.name_ar if hood else "",
                title=title,
                description=(
                    "إعلان تجريبي لغرض الاختبار — يُحذف قبل الإطلاق.\n"
                    "المعاينة في الرقة، والسعر قابل للتفاوض البسيط."
                ),
                price=price,
                price_currency=currency,
                condition=condition,
                is_featured=featured,
                status=Listing.Status.PUBLISHED,
                published_at=timezone.now() - timezone.timedelta(hours=index * 5),
                expires_at=timezone.now() + timezone.timedelta(days=60),
                views_count=100 + index * 37,
            )
            created_count += 1

        self.stdout.write(f"  ✓ {created_count} إعلانًا تجريبيًا · {len(users)} مستخدمًا")
