/**
 * نصوص الوثائق القانونية — بثلاث لغات.
 *
 * ⚠️ هذه ليست نصوصًا شكلية. Google Play يقرأ سياسة الخصوصية ويقارنها بما
 * يعلنه التطبيق في نموذج «أمان البيانات»، والتناقض بينهما سبب رفض متكرّر.
 * لذلك كل بند هنا يطابق ما يجمعه الكود فعلًا — لا أكثر ولا أقل:
 *
 *   الاسم · رقم الهاتف · رقم واتساب (اختياري) · اللغة   → apps/accounts/models.py
 *   صور الإعلانات ونصوصها · المحافظة والعنوان النصّي     → apps/listings/models.py
 *   رمز الجهاز للإشعارات · إصدار التطبيق                 → accounts.Device
 *
 * وما لا نجمعه مذكور صراحةً لأن غيابه ميزة: لا موقع GPS، ولا جهات اتصال،
 * ولا كاميرا، ولا ميكروفون، ولا أي مكتبة إعلانات أو تحليلات طرف ثالث.
 */

export type Lang = 'ar' | 'tr' | 'en';

export type Section = { h: string; p: string[]; list?: string[] };

export type Doc = {
  title: string;
  updated: string;
  lead: string;
  sections: Section[];
  contact: string;
};

export const LANGS: { code: Lang; label: string; dir: 'rtl' | 'ltr' }[] = [
  { code: 'ar', label: 'العربية', dir: 'rtl' },
  { code: 'tr', label: 'Turkce', dir: 'ltr' },
  { code: 'en', label: 'English', dir: 'ltr' },
];

/**
 * هويّة التطبيق كما تظهر في صفحة Google Play — **حرفيًا**.
 *
 * ⚠️ غوغل رفض تحديثًا في 2026-09-29 لأن السياسة لم تذكر اسم التطبيق في المتجر
 * («سوقنا») ولا اسم المطوّر. المراجع يطابق النصّ بالنصّ: إن غُيّر اسم التطبيق
 * في Store listing أو اسم المطوّر في الكونسول، يُغيَّر هنا في اليوم نفسه.
 */
export const IDENTITY = {
  appName: 'سوقنا',
  appNameLatin: 'Souqna',
  developer: 'lebid hacalaye',
  packageName: 'com.souqraqqa.app',
};

/** تاريخ آخر مراجعة — يُحدَّث يدويًا مع كل تعديل جوهري. */
export const UPDATED = {
  ar: 'آخر تحديث: 29 أيلول 2026',
  tr: 'Son guncelleme: 29 Eylul 2026',
  en: 'Last updated: 29 September 2026',
};

/* ══════════════════════════════════════════════════ سياسة الخصوصية */

export const PRIVACY: Record<Lang, Doc> = {
  ar: {
    title: 'سياسة الخصوصية',
    updated: UPDATED.ar,
    lead:
      `${IDENTITY.appName} (سوق الرقة) تطبيق إعلانات مبوّبة مجاني بالكامل. لا نبيع بياناتك ولا نشاركها مع ` +
      'أي مُعلن أو وسيط، ولا يوجد في التطبيق أي إعلانات طرف ثالث ولا أدوات تتبّع.',
    sections: [
      {
        h: 'من نحن',
        p: [
          'تنطبق هذه السياسة على التطبيق التالي كما هو منشور في متجر Google Play:',
        ],
        list: [
          `اسم التطبيق: ${IDENTITY.appName} (${IDENTITY.appNameLatin})`,
          `المطوّر: ${IDENTITY.developer}`,
          `معرّف الحزمة: ${IDENTITY.packageName}`,
          `المسؤول عن بياناتك (Data controller) هو المطوّر ${IDENTITY.developer}.`,
        ],
      },
      {
        h: 'ما الذي نجمعه',
        p: ['نجمع ما يلزم لتشغيل السوق فقط:'],
        list: [
          'الاسم الذي تختاره لعرضه على إعلاناتك.',
          'رقم هاتفك — وهو معرّف حسابك، ويُستعمل لتسجيل الدخول.',
          'رقم واتساب إن أضفته (اختياري، وإلا استُعمل رقم الحساب).',
          'محتوى إعلاناتك: العنوان والوصف والسعر والصور.',
          'المحافظة والعنوان الذي تكتبه بنفسك — نصًّا تكتبه أنت، لا موقعًا من الجهاز.',
          'لغتك المفضّلة وعملة العرض التي تختارها.',
          'رمز جهاز لإرسال الإشعارات، وإصدار التطبيق لديك.',
          'سجلّات خادم تقنية (عنوان IP ووقت الطلب) تُحفظ مدة قصيرة لأمن الخدمة.',
        ],
      },
      {
        h: 'ما الذي لا نجمعه',
        p: ['نذكر هذا صراحةً لأن غيابه جزء من التصميم:'],
        list: [
          'لا نصل إلى موقعك الجغرافي (GPS) إطلاقًا.',
          'لا نصل إلى جهات اتصالك ولا رسائلك ولا سجلّ مكالماتك.',
          'لا نستعمل الكاميرا ولا الميكروفون — الصور تُختار عبر منتقي صور أندرويد.',
          'لا نستعمل أي مكتبة إعلانات ولا تحليلات ولا معرّف إعلاني.',
          'لا نطلب أي بيانات بنكية — لا يوجد في التطبيق أي عملية دفع.',
        ],
      },
      {
        h: 'من يرى رقم هاتفك',
        p: [
          'رقمك لا يظهر في قوائم الإعلانات ولا لغير المسجّلين. يظهر فقط حين يضغط ' +
            'مستخدم مسجَّل الدخول زرّ التواصل على إعلانك — وهذا هو الغرض من نشر الإعلان.',
          'إن حذفت إعلانك أو حسابك، لم يعد رقمك متاحًا لأحد عبر التطبيق.',
        ],
      },
      {
        h: 'الصور',
        p: [
          'الصور التي ترفعها تُخزَّن على خادمنا وتُعرض ضمن إعلانك للجميع. نزيل بيانات ' +
            'EXIF المرفقة بالصورة عند المعالجة، ومنها بيانات الموقع إن وُجدت.',
        ],
      },
      {
        h: 'أين تُحفظ البيانات',
        p: [
          'على خادم واحد لدى Hetzner في ألمانيا. لا نستعمل خدمات سحابية أخرى، ولا ' +
            'ننقل بياناتك إلى أي جهة ثالثة إلا إذا ألزمنا القانون بذلك.',
        ],
      },
      {
        h: 'مدة الحفظ',
        p: [
          'الإعلان ينتهي تلقائيًا بعد ٦٠ يومًا من نشره. بيانات حسابك تبقى ما دام الحساب ' +
            'قائمًا — وتُحذف كاملة لحظة حذفك له.',
        ],
      },
      {
        h: 'حذف حسابك',
        p: ['يمكنك حذف حسابك في أي وقت، ومن طريقين:'],
        list: [
          'من التطبيق: «حسابي ‹ حذف حسابي».',
          'من الويب بلا تطبيق: صفحة /delete-account على هذا الموقع.',
        ],
      },
      {
        h: 'ماذا يُحذف بالضبط',
        p: ['الحذف نهائي وفوري ولا يمكن التراجع عنه. يُمحى:'],
        list: [
          'حسابك: الاسم والرقم ورقم واتساب وكلمة المرور.',
          'كل إعلاناتك وصورها — من قاعدة البيانات ومن القرص معًا.',
          'مفضلتك وأجهزتك المسجّلة وبلاغاتك وقائمة من حظرتهم.',
        ],
      },
      {
        h: 'الأطفال',
        p: [
          'التطبيق غير موجّه لمن هم دون ١٨ عامًا، ولا نجمع بيانات عنهم عن قصد. إن علمنا ' +
            'بحساب لقاصر حذفناه.',
        ],
      },
      {
        h: 'تغيير هذه السياسة',
        p: [
          'إن غيّرنا شيئًا جوهريًا، سنحدّث تاريخ المراجعة أعلى الصفحة ونعلن ذلك داخل ' +
            'التطبيق قبل أن يسري التغيير.',
        ],
      },
    ],
    contact: 'لأي سؤال عن خصوصيتك أو لطلب نسخة من بياناتك، تواصل معنا:',
  },

  tr: {
    title: 'Gizlilik Politikasi',
    updated: UPDATED.tr,
    lead:
      `${IDENTITY.appNameLatin} (Rakka Carsisi) tamamen ucretsiz bir seri ilan uygulamasidir. Verilerinizi satmiyor, ` +
      'hicbir reklamverenle paylasmiyoruz. Uygulamada ucuncu taraf reklam veya izleme araci yoktur.',
    sections: [
      {
        h: 'Biz kimiz',
        p: ['Bu politika, Google Play magazasinda yayinlanan su uygulama icin gecerlidir:'],
        list: [
          `Uygulama adi: ${IDENTITY.appName} (${IDENTITY.appNameLatin})`,
          `Gelistirici: ${IDENTITY.developer}`,
          `Paket adi: ${IDENTITY.packageName}`,
          `Verilerinizden sorumlu taraf (veri sorumlusu) gelistirici ${IDENTITY.developer}'dir.`,
        ],
      },
      {
        h: 'Topladiklarimiz',
        p: ['Yalnizca pazarin calismasi icin gerekli olanlar:'],
        list: [
          'Ilanlarinizda gorunmesini istediginiz ad.',
          'Telefon numaraniz — hesap kimliginiz ve giris yonteminiz.',
          'Eklerseniz WhatsApp numaraniz (istege bagli).',
          'Ilan iceriginiz: baslik, aciklama, fiyat ve fotograflar.',
          'Il ve kendi yazdiginiz adres metni — cihaz konumu degil.',
          'Tercih ettiginiz dil ve sectiginiz goruntuleme para birimi.',
          'Bildirim icin cihaz anahtari ve uygulama surumunuz.',
          'Guvenlik icin kisa sure saklanan teknik sunucu kayitlari (IP, zaman).',
        ],
      },
      {
        h: 'Toplamadiklarimiz',
        p: ['Bunu acikca yaziyoruz, cunku yoklugu tasarimin parcasi:'],
        list: [
          'Konumunuza (GPS) hic erismiyoruz.',
          'Rehberinize, mesajlariniza veya arama kaydiniza erismiyoruz.',
          'Kamera ve mikrofon kullanmiyoruz — fotograflar Android foto seciciyle secilir.',
          'Hicbir reklam kitapligi, analitik veya reklam kimligi kullanmiyoruz.',
          'Banka bilgisi istemiyoruz — uygulamada hicbir odeme islemi yoktur.',
        ],
      },
      {
        h: 'Numaranizi kim gorur',
        p: [
          'Numaraniz ilan listelerinde ve giris yapmamis kisilere gorunmez. Yalnizca giris ' +
            'yapmis bir kullanici ilaninizdaki iletisim dugmesine bastiginda gorunur.',
          'Ilaninizi veya hesabinizi silerseniz numaraniz uygulama uzerinden erisilemez olur.',
        ],
      },
      {
        h: 'Fotograflar',
        p: [
          'Yukledigsiniz fotograflar sunucumuzda saklanir ve ilaninizla birlikte herkese ' +
            'gosterilir. Isleme sirasinda konum dahil EXIF verilerini siliyoruz.',
        ],
      },
      {
        h: 'Veriler nerede tutulur',
        p: [
          'Almanya’da Hetzner’deki tek bir sunucuda. Baska bulut hizmeti kullanmiyor, ' +
            'yasal zorunluluk disinda hicbir ucuncu tarafa aktarmiyoruz.',
        ],
      },
      {
        h: 'Saklama suresi',
        p: [
          'Ilan yayindan 60 gun sonra otomatik sona erer. Hesap verileriniz hesap durdukca ' +
            'saklanir ve sildiginiz anda tamamen yok edilir.',
        ],
      },
      {
        h: 'Hesabinizi silme',
        p: ['Hesabinizi istediginiz an, iki yoldan silebilirsiniz:'],
        list: [
          'Uygulamadan: «Hesabim › Hesabimi sil».',
          'Uygulama olmadan web’den: bu sitedeki /delete-account sayfasi.',
        ],
      },
      {
        h: 'Tam olarak ne silinir',
        p: ['Silme kalici, aninda ve geri alinamazdir. Yok edilenler:'],
        list: [
          'Hesabiniz: ad, numara, WhatsApp numarasi ve sifre.',
          'Tum ilanlariniz ve fotograflari — hem veritabanindan hem diskten.',
          'Favorileriniz, kayitli cihazlariniz, sikayetleriniz ve engel listeniz.',
        ],
      },
      {
        h: 'Cocuklar',
        p: [
          'Uygulama 18 yas altina yonelik degildir ve bilerek onlardan veri toplamayiz. ' +
            'Resit olmayan bir hesabi ogrenirsek sileriz.',
        ],
      },
      {
        h: 'Bu politikanin degismesi',
        p: [
          'Esasli bir degisiklik olursa sayfanin ustundeki tarihi guncelleriz ve yururluge ' +
            'girmeden once uygulama icinde duyururuz.',
        ],
      },
    ],
    contact: 'Gizlilikle ilgili her soru veya veri kopyasi talebi icin:',
  },

  en: {
    title: 'Privacy Policy',
    updated: UPDATED.en,
    lead:
      `${IDENTITY.appName} (${IDENTITY.appNameLatin}, also known as Souq Raqqa) is a completely free classified-ads app. We do not sell your data or ` +
      'share it with any advertiser. The app contains no third-party ads and no tracking tools.',
    sections: [
      {
        h: 'Who we are',
        p: ['This policy applies to the following app, as published on Google Play:'],
        list: [
          `App name: ${IDENTITY.appName} (${IDENTITY.appNameLatin})`,
          `Developer: ${IDENTITY.developer}`,
          `Package name: ${IDENTITY.packageName}`,
          `The data controller responsible for your data is the developer, ${IDENTITY.developer}.`,
        ],
      },
      {
        h: 'What we collect',
        p: ['Only what the marketplace needs to work:'],
        list: [
          'The name you choose to show on your listings.',
          'Your phone number — your account identifier and the way you sign in.',
          'Your WhatsApp number, if you add one (optional).',
          'Your listing content: title, description, price and photos.',
          'The province and the address text you type yourself — not a device location.',
          'Your preferred language and the display currency you pick.',
          'A device token for notifications, and your app version.',
          'Technical server logs (IP address, request time) kept briefly for security.',
        ],
      },
      {
        h: 'What we do not collect',
        p: ['We state this explicitly because its absence is part of the design:'],
        list: [
          'We never access your GPS location.',
          'We never access your contacts, messages or call log.',
          'We use no camera and no microphone — photos come from the Android photo picker.',
          'We use no ad library, no analytics and no advertising ID.',
          'We ask for no banking details — the app contains no payment of any kind.',
        ],
      },
      {
        h: 'Who sees your phone number',
        p: [
          'Your number never appears in listing feeds or to signed-out visitors. It is shown ' +
            'only when a signed-in user taps the contact button on your listing.',
          'If you delete your listing or your account, your number is no longer reachable through the app.',
        ],
      },
      {
        h: 'Photos',
        p: [
          'Photos you upload are stored on our server and shown publicly with your listing. ' +
            'We strip EXIF metadata during processing, including any location data.',
        ],
      },
      {
        h: 'Where data is stored',
        p: [
          'On a single server at Hetzner in Germany. We use no other cloud services and ' +
            'transfer your data to no third party unless legally required.',
        ],
      },
      {
        h: 'How long we keep it',
        p: [
          'A listing expires automatically 60 days after publication. Your account data is ' +
            'kept as long as the account exists, and is destroyed entirely the moment you delete it.',
        ],
      },
      {
        h: 'Deleting your account',
        p: ['You can delete your account at any time, in two ways:'],
        list: [
          'In the app: Account › Delete my account.',
          'On the web without the app: the /delete-account page on this site.',
        ],
      },
      {
        h: 'Exactly what is deleted',
        p: ['Deletion is permanent, immediate and irreversible. We erase:'],
        list: [
          'Your account: name, number, WhatsApp number and password.',
          'All your listings and their photos — from the database and from disk.',
          'Your favourites, registered devices, reports and block list.',
        ],
      },
      {
        h: 'Children',
        p: [
          'The app is not directed at anyone under 18 and we do not knowingly collect their ' +
            'data. If we learn of a minor’s account we delete it.',
        ],
      },
      {
        h: 'Changes to this policy',
        p: [
          'If we change anything material we will update the date at the top of this page ' +
            'and announce it in the app before the change takes effect.',
        ],
      },
    ],
    contact: 'For any privacy question, or to request a copy of your data, contact us:',
  },
};
