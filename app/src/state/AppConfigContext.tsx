import AsyncStorage from '@react-native-async-storage/async-storage';
import { AppState } from 'react-native';
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { api } from '../api/client';
import type { AppConfig, Lang } from '../api/types';
import { APP_VERSION, CAN_DOWNLOAD_APK, STORAGE } from '../config';
import { formatAmount, formatApprox } from '../lib/money';
import { DARK, LIGHT, RADIUS } from '../theme/tokens';

/**
 * إعدادات التطبيق — تصل من الخادم وتُخزَّن محليًا.
 *
 * تسلسل الإقلاع المقصود (plan2 §4.2):
 *   1. القيم المدمجة  ← التطبيق يفتح فورًا وبشكل صحيح حتى بلا إنترنت
 *   2. آخر نسخة محفوظة على الجهاز
 *   3. الطلب من الخادم بـ ETag ← إن لم تتغيّر النسخة يعود 304 بلا جسم
 *
 * لا شاشة انتظار في أي من الخطوات — المستخدم لا ينتظر الإعدادات ليرى شيئًا.
 */

export const FALLBACK_CONFIG: AppConfig = {
  version: 0,
  // اسم فارغ عمدًا: الترويسة تقع عندها على نصّ الترجمة بلغة المستخدم،
  // وهو أصحّ من فرض العربية على واجهة تركية قبل وصول الإعدادات.
  brand: { name: '', names: { ar: '', tr: '', en: '' }, mark: '', logo: null, launcher_icon: null },
  theme: {
    light: LIGHT,
    dark: DARK,
    font: { family: 'Cairo', scale: 1 },
    radius: RADIUS,
    shadows: 'soft',
    density: 'normal',
    darkModeEnabled: true,
  },
  currency: {
    base: 'USD',
    default: 'USD',
    enabled: ['USD', 'SYP', 'TRY', 'EUR'],
    catalogue: [
      { code: 'USD', symbol: '$', symbols: { ar: '$', tr: '$', en: '$' },
        name: 'دولار أمريكي', names: { ar: 'دولار أمريكي', tr: 'Amerikan doları', en: 'US dollar' },
        decimals: 0 },
      { code: 'SYP', symbol: 'ل.س', symbols: { ar: 'ل.س', tr: 'SYP', en: 'SYP' },
        name: 'ليرة سورية', names: { ar: 'ليرة سورية', tr: 'Suriye lirası', en: 'Syrian pound' },
        decimals: 0 },
      { code: 'TRY', symbol: 'ل.ت', symbols: { ar: 'ل.ت', tr: '₺', en: '₺' },
        name: 'ليرة تركية', names: { ar: 'ليرة تركية', tr: 'Türk lirası', en: 'Turkish lira' },
        decimals: 0 },
      { code: 'EUR', symbol: '€', symbols: { ar: '€', tr: '€', en: '€' },
        name: 'يورو', names: { ar: 'يورو', tr: 'Euro', en: 'Euro' }, decimals: 0 },
    ],
    // فارغ عمدًا: قبل أن يضبط الأدمن الأسعار لا نعرض تحويلًا مخترعًا
    rates: {},
    rates_updated_at: null,
  },
  languages: { supported: ['ar', 'tr', 'en'], default: 'ar', rtl: ['ar'] },
  landing: {
    ar: { headline: '', subline: '', body: '', cta: '', features: [] },
    tr: { headline: '', subline: '', body: '', cta: '', features: [] },
    en: { headline: '', subline: '', body: '', cta: '', features: [] },
    image: null,
  },
  app: {
    latest_version: APP_VERSION ?? '1.0.0',
    min_version: '1.0.0',
    store_url: '',
    apk_url: '',
    apk_sha256: '',
    apk_size_mb: 0,
    update_message: '',
  },
  features: {
    chat_enabled: false,
    whatsapp_enabled: true,
    featured_enabled: false,
    ratings_enabled: false,
    guest_browsing: true,
    guest_favorites: true,
    phone_verification: false,
    show_view_counts: true,
    show_listing_counts: true,
  },
  limits: {
    listing_expiry_days: 60,
    daily_listing_limit: 5,
    max_photos_per_listing: 10,
    max_video_seconds: 60,
    max_video_mb: 100,
    min_description_length: 10,
  },
  support: { whatsapp: '', email: '' },
  legal: { privacy: '', terms: '', delete_account: '' },
};

type UpdateState = 'none' | 'available' | 'required';

type AppConfigValue = {
  config: AppConfig;
  loaded: boolean;
  online: boolean;
  updateState: UpdateState;
  refresh: () => Promise<void>;
  /** مبلغ مجرّد بعملة القراءة — للمرشّحات لا لأسعار الإعلانات. */
  money: (amount: number | null, lang: Lang) => string;
  /** سعر إعلان: `main` بعملة البائع، و`approx` تقدير بعملة القارئ أو null. */
  price: (
    amount: number | null,
    listingCurrency: string,
    lang: Lang,
  ) => { main: string; approx: string | null };
  /** العملة التي يقرأ بها المستخدم الآن. */
  currency: string;
  setCurrency: (code: string) => Promise<void>;
};

const AppConfigContext = createContext<AppConfigValue | null>(null);

/** يقارن «1.2.0» بـ «1.10.0» بشكل صحيح — المقارنة النصّية تخطئ هنا. */
export function compareVersions(a: string, b: string): number {
  const pa = a.split('.').map((n) => parseInt(n, 10) || 0);
  const pb = b.split('.').map((n) => parseInt(n, 10) || 0);
  for (let i = 0; i < Math.max(pa.length, pb.length); i += 1) {
    const diff = (pa[i] ?? 0) - (pb[i] ?? 0);
    if (diff !== 0) return diff < 0 ? -1 : 1;
  }
  return 0;
}

export function AppConfigProvider({ children }: { children: React.ReactNode }) {
  const [config, setConfig] = useState<AppConfig>(FALLBACK_CONFIG);
  const [loaded, setLoaded] = useState(false);
  const [online, setOnline] = useState(true);
  const [chosenCurrency, setChosenCurrency] = useState<string | null>(null);

  const applyStored = useCallback(async () => {
    const saved = await AsyncStorage.getItem(STORAGE.currency);
    if (saved) setChosenCurrency(saved);
    const raw = await AsyncStorage.getItem(STORAGE.appConfig);
    if (raw) {
      try {
        setConfig(mergeWithFallback(JSON.parse(raw) as AppConfig));
      } catch {
        /* بيانات تالفة — نبقى على القيم المدمجة */
      }
    }
  }, []);

  const refresh = useCallback(async () => {
    try {
      const etag = await AsyncStorage.getItem(STORAGE.appConfigEtag);
      const result = await api.getAppConfig(etag);
      setOnline(true);
      if (!result) return; // 304 — لا شيء تغيّر
      const next = mergeWithFallback(result.data as AppConfig);
      setConfig(next);
      await AsyncStorage.multiSet([
        [STORAGE.appConfig, JSON.stringify(next)],
        [STORAGE.appConfigEtag, result.etag],
      ]);
    } catch {
      setOnline(false);
    }
  }, []);

  useEffect(() => {
    (async () => {
      await applyStored();
      setLoaded(true);
      await refresh();
    })();
  }, [applyStored, refresh]);

  /**
   * إعادة جلب الإعدادات عند عودة التطبيق إلى الواجهة.
   *
   * بلا هذا لا تصل تعديلات الأدمن إلا بعد **إقلاع بارد** — ومن يُبقي التطبيق
   * في الخلفية أسبوعًا يبقى على إعدادات أسبوع مضى. وهذا ليس تجميلًا: أسعار
   * الصرف تُضبط من اللوحة، ومستخدمٌ يحمل جدولًا قديمًا يقرأ مبالغ خاطئة بلا
   * أن يعرف. والطلب رخيص لأن الخادم يردّ 304 حين لا يتغيّر شيء.
   */
  useEffect(() => {
    const subscription = AppState.addEventListener('change', (state) => {
      if (state === 'active') void refresh();
    });
    return () => subscription.remove();
  }, [refresh]);

  const updateState: UpdateState = useMemo(() => {
    // نسخة المتجر تحدّث نفسها عبر Google Play، ونسخة الموقع عبر ملف APK.
    // فإن غاب سبيل التحديث المناسب للقناة، لا معنى لإخبار المستخدم بشيء.
    const hasChannel = CAN_DOWNLOAD_APK ? Boolean(config.app.apk_url) : true;
    if (!hasChannel) return 'none';
    // إصدار مجهول ⇒ لا نحجب ولا نُلحّ. الحجب بناءً على تخمين يقفل التطبيق على
    // من يحمل أحدث نسخة أصلًا، ولا مخرج له من الشاشة.
    if (!APP_VERSION) return 'none';
    if (compareVersions(APP_VERSION, config.app.min_version) < 0) return 'required';
    if (compareVersions(APP_VERSION, config.app.latest_version) < 0) return 'available';
    return 'none';
  }, [config.app]);

  /**
   * عملة القراءة — اختيار المستخدم، لا عملة الإعلان.
   *
   * تُحفظ على الجهاز فيجدها كما تركها، وتعود إلى الافتراضية إن لم تعد
   * ضمن العملات المتاحة (قد يوقفها الأدمن بعد أن اختارها المستخدم).
   */
  const currency = useMemo(() => {
    // الكتالوج شبكة أمان: خادم قديم قد يرسل `enabled` فارغة، وقائمة فارغة
    // كانت تعني رفض كل اختيار والعودة إلى الافتراضية دائمًا — أي زرّ عملة
    // لا يفعل شيئًا، وهو أسوأ من زرّ غائب.
    const enabled = config.currency.enabled?.length
      ? config.currency.enabled
      : config.currency.catalogue.map((c) => c.code);
    if (chosenCurrency && enabled.includes(chosenCurrency)) return chosenCurrency;
    return config.currency.default;
  }, [chosenCurrency, config.currency]);

  const setCurrency = useCallback(async (code: string) => {
    setChosenCurrency(code);
    await AsyncStorage.setItem(STORAGE.currency, code);
  }, []);

  /** مبلغ مجرّد بعملة القراءة — للمرشّحات وحقول البحث لا لأسعار الإعلانات. */
  const money = useCallback(
    (amount: number | null, lang: Lang) => formatAmount(amount, currency, config, lang),
    [config, currency],
  );

  /**
   * سعر إعلان: سطر البائع، وتحته التقدير بعملة القارئ حين نملك سعر صرف.
   *
   * لم نجعلها تعيد نصًّا واحدًا لأن السطرين مختلفان في الوزن البصري —
   * الأصل بارز، والتقدير باهت وصغير. دمجهما كان سيساوي بينهما.
   */
  const price = useCallback(
    (amount: number | null, listingCurrency: string, lang: Lang) => ({
      main: formatAmount(amount, listingCurrency || config.currency.base, config, lang),
      approx: formatApprox(amount, listingCurrency || config.currency.base, currency, config, lang),
    }),
    [config, currency],
  );

  const value = useMemo<AppConfigValue>(
    () => ({ config, loaded, online, updateState, refresh, money, price, currency, setCurrency }),
    [config, loaded, online, updateState, refresh, money, price, currency, setCurrency],
  );

  return <AppConfigContext.Provider value={value}>{children}</AppConfigContext.Provider>;
}

/** خادم قديم قد لا يرسل مفتاحًا جديدًا — ندمج فوق القيم المدمجة حتى لا ينكسر شيء. */
function mergeWithFallback(incoming: AppConfig): AppConfig {
  return {
    ...FALLBACK_CONFIG,
    ...incoming,
    theme: {
      ...FALLBACK_CONFIG.theme,
      ...incoming.theme,
      light: { ...LIGHT, ...incoming.theme?.light },
      dark: { ...DARK, ...incoming.theme?.dark },
      radius: { ...RADIUS, ...incoming.theme?.radius },
      font: { ...FALLBACK_CONFIG.theme.font, ...incoming.theme?.font },
    },
    currency: { ...FALLBACK_CONFIG.currency, ...incoming.currency },
    languages: { ...FALLBACK_CONFIG.languages, ...incoming.languages },
    features: { ...FALLBACK_CONFIG.features, ...incoming.features },
    limits: { ...FALLBACK_CONFIG.limits, ...incoming.limits },
    app: { ...FALLBACK_CONFIG.app, ...incoming.app },
    support: { ...FALLBACK_CONFIG.support, ...incoming.support },
    brand: { ...FALLBACK_CONFIG.brand, ...incoming.brand },
    landing: { ...FALLBACK_CONFIG.landing, ...incoming.landing },
  };
}

export function useAppConfig(): AppConfigValue {
  const context = useContext(AppConfigContext);
  if (!context) throw new Error('useAppConfig يجب أن يُستخدم داخل AppConfigProvider');
  return context;
}
