import Constants from 'expo-constants';
import { Platform } from 'react-native';

/**
 * عنوان الخلفية.
 *
 * ترتيب الأولوية:
 *   1. متغيّر البيئة EXPO_PUBLIC_API_URL  ← ما نستخدمه في الإنتاج
 *   2. القيمة في app.json → extra.apiUrl
 *   3. عنوان محلّي مناسب لكل منصّة
 *
 * ملاحظة مهمّة: محاكي أندرويد لا يرى `localhost` — لأنه جهاز مستقلّ.
 * العنوان 10.0.2.2 هو جهازك من داخل المحاكي.
 * ولتجربة التطبيق على جوال حقيقي: ضع رقم IP جهازك على الشبكة، مثلًا
 *   EXPO_PUBLIC_API_URL=http://192.168.1.5:8000/api/v1
 */
function localApiUrl(): string {
  if (Platform.OS === 'android') return 'http://10.0.2.2:8000/api/v1';
  return 'http://127.0.0.1:8000/api/v1';
}

/** نسخة الويب المرفوعة بجانب الخلفية على النطاق نفسه. */
function sameOriginApiUrl(): string | null {
  if (Platform.OS !== 'web' || typeof window === 'undefined') return null;
  return `${window.location.origin}/api/v1`;
}

const fromExtra = (Constants.expoConfig?.extra as { apiUrl?: string } | undefined)?.apiUrl;

export const API_URL = (
  // 1) متغيّر البناء — الطريقة المعتمدة للإنتاج
  process.env.EXPO_PUBLIC_API_URL ||
  // 2) التطوير المحلّي
  (__DEV__ ? localApiUrl() : null) ||
  // 3) القيمة المكتوبة في app.json
  fromExtra ||
  // 4) نسخة ويب على نفس نطاق الخادم
  sameOriginApiUrl() ||
  localApiUrl()
).replace(/\/$/, '');

/**
 * إصدار التطبيق — يُقارَن بـ `min_version` و`latest_version` من app-config.
 *
 * مصدران بالترتيب:
 *   1. متغيّر يُحقَن في الحزمة وقت البناء — يبقى صحيحًا مهما جرى بعده.
 *   2. `Constants.expoConfig` — يقرأه الجهاز من الملف المثبَّت، إلا حين يشغّل
 *      حزمة تحديث عن بُعد فيقرأه من بيان التحديث.
 *
 * ⚠️ و`null` حين يتعذّر الاثنان — **ولا نخترع قيمة**. كانت القيمة الاحتياطية
 * `'1.0.0'` أي «افترض أقدم إصدار ممكن»، فحوّلت بيانًا ناقصًا إلى قفل تامّ:
 * تطبيق يظنّ نفسه قديمًا فيطالب بتحديث، ثم يطالب به مرة أخرى بعد تثبيته.
 * الجهل بالإصدار سبب لعدم الحجب لا سبب له.
 */
export const APP_VERSION: string | null =
  process.env.EXPO_PUBLIC_APP_VERSION || Constants.expoConfig?.version || null;

/** مفاتيح التخزين المحلّي. */
export const STORAGE = {
  tokens: 'souq.tokens',
  user: 'souq.user',
  language: 'souq.language',
  currency: 'souq.currency',
  themeMode: 'souq.themeMode',
  appConfig: 'souq.appConfig',
  appConfigEtag: 'souq.appConfigEtag',
  guestFavorites: 'souq.guestFavorites',
  cache: 'souq.cache.',
} as const;

/** مهلة الطلب — الإنترنت في الرقة ضعيف، والانتظار الطويل أسوأ من رسالة خطأ. */
export const REQUEST_TIMEOUT_MS = 20000;

/**
 * مهلة رفع الملفات — أطول بكثير، وعن قصد.
 *
 * الـ 20 ثانية أعلاه مناسبة لطلب JSON صغير: إن تأخّر هذا الوقت فالشبكة مقطوعة
 * فعلًا. لكنها قاتلة لصورة بحجم ميغابايتين ترفعها من جوال في الرقة إلى خادم في
 * ألمانيا — الرفع يقطع في منتصفه، والمستخدم يظنّ أن إعلانه نُشر بصوره.
 */
export const UPLOAD_TIMEOUT_MS = 120000;

/**
 * مهلة رفع الفيديو — ربع ساعة.
 *
 * مقطع دقيقة من جوال حديث قد يقارب 100 ميغابايت، وعلى إنترنت بطيء يحتاج
 * دقائق فعلًا. قطعه عند دقيقتين يعني ألّا يصل فيديو واحد من الرقة.
 */
export const VIDEO_UPLOAD_TIMEOUT_MS = 15 * 60 * 1000;

/**
 * قناة التوزيع — من أين حصل المستخدم على هذه النسخة.
 *
 * لهذا المتغيّر سبب واحد ثقيل: **سياسة Google Play تمنع منعًا باتًّا** أن
 * يحدّث التطبيق نفسه بتنزيل ملف APK من خارج المتجر (Device and Network Abuse).
 * النسخة التي نرفعها إلى المتجر يجب ألّا تحتوي زرّ «حمّل التحديث» أصلًا —
 * لا أن نخفيه بشرط في الخادم، فالمراجع يقرأ الكود لا الإعدادات فقط.
 *
 * لذلك نحقنه وقت البناء:
 *   EXPO_PUBLIC_DISTRIBUTION=play    ← الحزمة المرفوعة إلى Google Play
 *   EXPO_PUBLIC_DISTRIBUTION=direct  ← ملف APK المنشور على موقعنا
 *
 * والقيمة الافتراضية `play` عمدًا: لو نُسي المتغيّر في بناء ما، فالخطأ يقع
 * في الاتجاه الآمن (تطبيق يحيل إلى المتجر) لا في اتجاه المخالفة.
 */
export type Distribution = 'play' | 'direct';

export const DISTRIBUTION: Distribution =
  process.env.EXPO_PUBLIC_DISTRIBUTION === 'direct' ? 'direct' : 'play';

/** هل يُسمح لهذه النسخة بعرض تنزيل APK مباشر؟ */
export const CAN_DOWNLOAD_APK = DISTRIBUTION === 'direct';

/** معرّف الحزمة على أندرويد — منه نبني رابط المتجر حين لا يضبطه الأدمن. */
export const ANDROID_PACKAGE = 'com.souqraqqa.app';

export const PLAY_STORE_URL = `https://play.google.com/store/apps/details?id=${ANDROID_PACKAGE}`;
