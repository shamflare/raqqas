import type { ColorTokens, Density, RadiusTokens, ShadowLevel } from '../theme/tokens';

export type Lang = 'ar' | 'tr' | 'en';

export type Translated = { ar: string; tr: string; en: string };

export type CurrencyInfo = {
  code: string;
  symbol: string;
  symbols: Translated;
  name: string;
  names: Translated;
  decimals: number;
};

export type AppConfig = {
  version: number;
  /** الاسم والشعار من لوحة الإدارة — يسبقان النصّ المدمج في ملفات الترجمة. */
  brand: {
    name: string;
    names: Translated;
    mark: string;
    logo: string | null;
    launcher_icon: string | null;
  };
  theme: {
    light: ColorTokens;
    dark: ColorTokens;
    font: { family: string; scale: number };
    radius: RadiusTokens;
    shadows: ShadowLevel;
    density: Density;
    darkModeEnabled: boolean;
  };
  currency: {
    /** محور التحويل — كل الأسعار تُكتب بصيغة «1 دولار = كم». */
    base: string;
    /** ما يقرأ به المستخدم قبل أن يختار. */
    default: string;
    enabled: string[];
    catalogue: CurrencyInfo[];
    /** فارغ = لم يضبط الأدمن الأسعار ⇒ لا يُعرض أي تحويل تقريبي. */
    rates: Record<string, number>;
    rates_updated_at: string | null;
  };
  languages: { supported: Lang[]; default: Lang; rtl: Lang[] };
  landing: { ar: LandingText; tr: LandingText; en: LandingText; image: string | null };
  app: {
    latest_version: string;
    min_version: string;
    store_url: string;
    apk_url: string;
    apk_sha256: string;
    apk_size_mb: number;
    update_message: string;
  };
  features: {
    chat_enabled: boolean;
    whatsapp_enabled: boolean;
    featured_enabled: boolean;
    ratings_enabled: boolean;
    guest_browsing: boolean;
    guest_favorites: boolean;
    phone_verification: boolean;
    show_view_counts: boolean;
    show_listing_counts: boolean;
  };
  limits: {
    listing_expiry_days: number;
    daily_listing_limit: number;
    max_photos_per_listing: number;
    /** صفر = رفع الفيديو متوقّف. */
    max_video_seconds: number;
    max_video_mb: number;
    min_description_length: number;
  };
  support: { whatsapp: string; email: string };
  /** روابط الوثائق التي يشترط Google Play الوصول إليها من داخل التطبيق. */
  legal: { privacy: string; terms: string; delete_account: string };
};

export type LandingText = {
  headline: string;
  subline: string;
  body: string;
  cta: string;
  features: { icon: string; title: string; text: string }[];
};

export type Category = {
  id: number;
  slug: string;
  name: string;
  names: Translated;
  icon: string;
  sort_order: number;
  listings_count: number;
  children?: Category[];
};

export type Neighborhood = {
  id: number;
  slug: string;
  name: string;
  names: Translated;
  city_id: number;
  sort_order: number;
};

export type City = {
  id: number;
  slug: string;
  name: string;
  names: Translated;
  sort_order: number;
  neighborhoods: Neighborhood[];
};

export type Media = {
  id: number;
  kind: 'photo' | 'video';
  /** للفيديو: صورة الغلاف. */
  url: string;
  thumb_url: string;
  /** رابط المقطع نفسه — للفيديو فقط. */
  video_url?: string | null;
  /** مدة الفيديو بالثواني. */
  duration?: number;
  width: number;
  height: number;
  is_main: boolean;
  sort_order: number;
};

export type ListingStatus =
  | 'draft' | 'pending' | 'published' | 'rejected' | 'expired' | 'suspended' | 'deleted';

export type ListingCard = {
  id: number;
  title: string;
  price: number | null;
  price_currency: string;
  price_text: string;
  condition: 'new' | 'used';
  is_featured: boolean;
  status: ListingStatus;
  thumb: string | null;
  photos_count: number;
  has_video: boolean;
  category: {
    id: number; slug: string; name: string; icon: string;
    parent: { id: number; slug: string; name: string; icon: string } | null;
  } | null;
  city: { id: number; slug: string; name: string } | null;
  /** عنوان يكتبه صاحب الإعلان بحرّية — بديل قائمة الأحياء المغلقة. */
  address: string;
  time_text: string;
  views_count: number;
  is_favorited: boolean;
};

export type MyListing = ListingCard & {
  rejection_reason: string;
  published_at: string | null;
  expires_at: string | null;
  created_at: string;
  favorites_count: number;
  contacts_count: number;
};

export type Seller = {
  id: number;
  name: string;
  initial: string;
  joined_year: number;
  phone_verified: boolean;
  listings_count: number;
};

export type Listing = ListingCard & {
  description: string;
  media: Media[];
  seller: Seller;
  favorites_count: number;
  published_at: string | null;
  expires_at: string | null;
  created_at: string;
  rejection_reason: string;
  can_edit: boolean;
};

export type Contact = {
  phone: string;
  phone_display: string;
  whatsapp: string;
  whatsapp_url: string;
  message: string;
};

export type User = {
  id: number;
  name: string;
  phone: string;
  phone_display: string;
  whatsapp_number: string;
  role: 'user' | 'moderator' | 'admin';
  status: 'active' | 'suspended' | 'banned';
  language: Lang;
  phone_verified: boolean;
  listings_approved_count: number;
  created_at: string;
  last_seen_at: string | null;
};

export type Tokens = { access: string; refresh: string };

export type Paginated<T> = {
  count: number;
  pages: number;
  page: number;
  has_next: boolean;
  next: string | null;
  previous: string | null;
  results: T[];
  counts?: Record<string, number>;
  unread?: number;
};

export type HomePayload = {
  categories: Category[];
  featured: ListingCard[];
  latest: ListingCard[];
};

export type NotificationItem = {
  id: number;
  kind: string;
  title: string;
  body: string;
  listing_id: number | null;
  is_read: boolean;
  created_at: string;
  time_text: string;
  data: Record<string, unknown>;
};

export type ApiErrorBody = {
  error: {
    code: string;
    message: string;
    fields?: Record<string, string[]>;
    retry_after?: number;
  };
};
