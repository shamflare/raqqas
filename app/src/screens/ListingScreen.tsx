import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { Image } from 'expo-image';
import React, { useCallback, useRef, useState } from 'react';
import {
  Alert,
  Dimensions,
  FlatList,
  Linking,
  Platform,
  Pressable,
  ScrollView,
  Share,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { api, ApiError } from '../api/client';
import type { Contact, Listing } from '../api/types';
import { Field, TextArea } from '../components/Field';
import { OptionList, Sheet } from '../components/Sheet';
import { SubHeader } from '../components/Header';
import { useToast } from '../components/Toast';
import { Avatar, Badge, Button, Card, Empty, IconButton, Loader, Notice, Txt } from '../components/ui';
import { formatDuration, VideoPlayerModal } from '../components/Video';
import { CAN_DOWNLOAD_APK, PLAY_STORE_URL } from '../config';
import { useResource } from '../hooks/useResource';
import { useI18n } from '../i18n';
import type { RootStackParamList } from '../navigation/types';
import { useAppConfig } from '../state/AppConfigContext';
import { useAuth } from '../state/AuthContext';
import { useFavorites } from '../state/FavoritesContext';
import { useTheme } from '../theme/ThemeProvider';

type Props = NativeStackScreenProps<RootStackParamList, 'Listing'>;

const REPORT_REASONS = [
  { value: 'fraud', icon: '⚠️' },
  { value: 'fake', icon: '🎭' },
  { value: 'violation', icon: '🚫' },
  { value: 'banned_item', icon: '⛔' },
  { value: 'other', icon: '✍️' },
] as const;

export function ListingScreen({ navigation, route }: Props) {
  const t = useTheme();
  const { t: text, tp, lang } = useI18n();
  const { config, price } = useAppConfig();
  const { requireAuth } = useAuth();
  const favorites = useFavorites();
  const toast = useToast();
  const insets = useSafeAreaInsets();

  const [photoIndex, setPhotoIndex] = useState(0);
  const [playing, setPlaying] = useState<string | null>(null);
  const [reportOpen, setReportOpen] = useState(false);
  const [reportReason, setReportReason] = useState<string>('fraud');
  const [reportNote, setReportNote] = useState('');
  const [contacting, setContacting] = useState(false);

  const { data: listing, loading, error, refresh } = useResource<Listing>(
    `/listings/${route.params.id}`,
    { cacheKey: `listing:${route.params.id}` },
  );

  // العودة من شاشة التعديل تعني أن ما نعرضه صار قديمًا — نحدّثه بلا أن يطلب أحد.
  // نتخطّى أول ظهور: `useResource` جلب البيانات لتوّه، وطلب ثانٍ فورًا هدر
  // محسوس على إنترنت ضعيف.
  const firstFocus = useRef(true);
  useFocusEffect(
    useCallback(() => {
      if (firstFocus.current) {
        firstFocus.current = false;
        return;
      }
      void refresh();
    }, [refresh]),
  );

  const width = Dimensions.get('window').width;

  if (loading && !listing) {
    return (
      <View style={{ flex: 1, backgroundColor: t.colors.bg }}>
        <SubHeader title="" onBack={() => navigation.goBack()} />
        <Loader />
      </View>
    );
  }

  if (!listing) {
    return (
      <View style={{ flex: 1, backgroundColor: t.colors.bg }}>
        <SubHeader title={text.listing.notFound} onBack={() => navigation.goBack()} />
        <Empty
          icon="🔍"
          title={text.listing.notFound}
          text={error ? text.errors.offlineEmpty : undefined}
          action={text.common.retry}
          onAction={refresh}
        />
      </View>
    );
  }

  const isFavorite = favorites.isFavorite(listing.id);

  /**
   * التواصل — البوابة الوحيدة التي يظهر عندها رقم البائع (قرار 17).
   * بعد تسجيل الدخول يُستأنف الإجراء تلقائيًا فيفتح واتساب مباشرة.
   */
  const contactSeller = () =>
    requireAuth('contact', async () => {
      setContacting(true);
      try {
        const contact = await api.get<Contact>(`/listings/${listing.id}/contact`);
        const opened = await Linking.canOpenURL(contact.whatsapp_url);
        if (opened) await Linking.openURL(contact.whatsapp_url);
        else toast.show(contact.phone_display);
      } catch (caught) {
        toast.show(caught instanceof ApiError ? caught.message : text.errors.generic);
      } finally {
        setContacting(false);
      }
    });

  const callSeller = () =>
    requireAuth('contact', async () => {
      try {
        const contact = await api.get<Contact>(`/listings/${listing.id}/contact`);
        await Linking.openURL(`tel:${contact.phone}`);
      } catch (caught) {
        toast.show(caught instanceof ApiError ? caught.message : text.errors.generic);
      }
    });

  const submitReport = async () => {
    try {
      const result = await api.post<{ already_reported: boolean }>(
        `/listings/${listing.id}/report`,
        { reason: reportReason, note: reportNote },
      );
      setReportOpen(false);
      setReportNote('');
      toast.show(result.already_reported ? text.listing.reportAlready : text.listing.reportDone);
    } catch (caught) {
      toast.show(caught instanceof ApiError ? caught.message : text.errors.generic);
    }
  };

  /**
   * حظر المعلن — يخفي كل إعلاناته عن هذا المستخدم وحده.
   *
   * سياسة المحتوى من المستخدمين لدى Google Play تشترط أن يملك المستخدم وسيلة
   * لحجب شخص بعينه، لا الاكتفاء بالإبلاغ عن منشور واحد. وبعد الحظر يختفي
   * الإعلان من الخادم نفسه، فنعود للخلف بدل إبقاء شاشة بلا محتوى.
   */
  const priceText = price(listing.price, listing.price_currency, lang);

  const blockSeller = () => {
    const seller = listing.seller;
    if (!seller) return;
    requireAuth('block', () => confirmBlock(seller.id, seller.name));
  };

  const confirmBlock = (sellerId: number, sellerName: string) => {
    Alert.alert(text.listing.blockTitle, tp(text.listing.blockText, { name: sellerName }), [
      { text: text.common.cancel, style: 'cancel' },
      {
        text: text.listing.block,
        style: 'destructive',
        onPress: async () => {
          try {
            await api.post('/auth/blocks', { user_id: sellerId });
            toast.show(text.listing.blockDone);
            navigation.goBack();
          } catch (caught) {
            toast.show(caught instanceof ApiError ? caught.message : text.errors.generic);
          }
        },
      },
    ]);
  };

  const share = async () => {
    // نسخة المتجر تشارك صفحة التطبيق في Google Play، ونسخة الموقع تشارك ملف
    // APK. مشاركة رابط تثبيت مباشر من تطبيق منشور في المتجر مخالفة سياسة.
    const appLink = CAN_DOWNLOAD_APK
      ? config.app.apk_url
      : config.app.store_url || PLAY_STORE_URL;
    try {
      await Share.share({
        message: `${listing.title}\n${listing.price_text}\n${appLink || ''}`.trim(),
      });
    } catch {
      /* ألغى المستخدم المشاركة */
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: t.colors.bg }}>
      <SubHeader
        title={listing.category?.name ?? ''}
        onBack={() => navigation.goBack()}
        right={<IconButton icon="↗" onPress={share} />}
      />

      <ScrollView contentContainerStyle={{ paddingBottom: 110 }}>
        {/* المعرض */}
        <View style={{ backgroundColor: '#000000' }}>
          {listing.media.length > 0 ? (
            <>
              <FlatList
                horizontal
                pagingEnabled
                inverted={t.isRTL}
                showsHorizontalScrollIndicator={false}
                data={listing.media}
                keyExtractor={(item) => String(item.id)}
                onMomentumScrollEnd={(event) =>
                  setPhotoIndex(Math.round(event.nativeEvent.contentOffset.x / width))
                }
                renderItem={({ item }) =>
                  item.kind === 'video' && item.video_url ? (
                    // الغلاف وحده حتى يطلب المشاهد التشغيل — لا تنزيل لفيديو لم يُطلب
                    <Pressable onPress={() => setPlaying(item.video_url ?? null)}>
                      <Image
                        source={{ uri: item.url }}
                        style={{ width, aspectRatio: 4 / 3 }}
                        contentFit="cover"
                        transition={150}
                      />
                      <View
                        style={{
                          position: 'absolute',
                          inset: 0,
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: 8,
                        }}
                      >
                        <View
                          style={{
                            width: 68,
                            height: 68,
                            borderRadius: 34,
                            backgroundColor: 'rgba(0,0,0,0.6)',
                            alignItems: 'center',
                            justifyContent: 'center',
                          }}
                        >
                          <Txt size={28} color="#FFFFFF">▶</Txt>
                        </View>
                        <Txt size={13} weight={800} color="#FFFFFF">
                          {text.listing.playVideo} · {formatDuration(item.duration ?? 0)}
                        </Txt>
                      </View>
                    </Pressable>
                  ) : (
                    <Image
                      source={{ uri: item.url }}
                      style={{ width, aspectRatio: 4 / 3 }}
                      contentFit="cover"
                      transition={150}
                    />
                  )
                }
              />
              {listing.media.length > 1 ? (
                <View
                  style={{
                    position: 'absolute',
                    bottom: 12,
                    [t.isRTL ? 'left' : 'right']: 12,
                    backgroundColor: 'rgba(0,0,0,0.65)',
                    borderRadius: t.radius.full,
                    paddingHorizontal: 11,
                    paddingVertical: 4,
                  }}
                >
                  <Txt size={12} weight={700} color="#FFFFFF">
                    {tp(text.listing.photosOf, {
                      current: photoIndex + 1,
                      total: listing.media.length,
                    })}
                  </Txt>
                </View>
              ) : null}
            </>
          ) : (
            <View
              style={{
                width,
                aspectRatio: 4 / 3,
                backgroundColor: t.colors.brand50,
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Txt size={64} style={{ opacity: 0.6 }}>
                {listing.category?.parent?.icon || listing.category?.icon || '📦'}
              </Txt>
            </View>
          )}
        </View>

        <View style={{ padding: 14, gap: 12 }}>
          {/* حالة الإعلان لصاحبه */}
          {listing.can_edit && listing.status !== 'published' ? (
            <Notice tone={listing.status === 'rejected' ? 'danger' : 'warn'}>
              {listing.status === 'rejected'
                ? tp(text.status.rejectedNote, { reason: listing.rejection_reason })
                : listing.status === 'pending'
                  ? text.status.pendingNote
                  : text.status.expiredNote}
            </Notice>
          ) : null}

          {/* السعر والعنوان */}
          <View>
            <View style={[t.row, { alignItems: 'center', gap: 8 }]}>
              <View>
                <Txt size={25} weight={900} color={t.colors.brandText} align="start">
                  {priceText.main}
                </Txt>
                {priceText.approx ? (
                  <Txt size={13.5} weight={700} muted align="start">
                    {priceText.approx} · {text.listing.approxHint}
                  </Txt>
                ) : null}
              </View>
              {listing.is_featured ? (
                <Badge
                  label={`⭐ ${text.listing.featured}`}
                  background={t.colors.gold}
                  color={t.colors.onGold}
                />
              ) : null}
            </View>
            <Txt size={19} weight={800} align="start" style={{ marginTop: 4, lineHeight: t.fs(28) }}>
              {listing.title}
            </Txt>
            <View style={[t.row, { flexWrap: 'wrap', gap: 14, marginTop: 8 }]}>
              {listing.city ? (
                <Txt size={12.5} weight={600} muted>
                  📍 {listing.address ? `${listing.city.name} · ${listing.address}` : listing.city.name}
                </Txt>
              ) : null}
              <Txt size={12.5} weight={600} muted>
                🕐 {listing.time_text}
              </Txt>
              {config.features.show_view_counts ? (
                <Txt size={12.5} weight={600} muted>
                  👁 {listing.views_count}
                </Txt>
              ) : null}
            </View>
          </View>

          {/* المواصفات */}
          <View style={[t.row, { gap: 10 }]}>
            <Spec
              label={text.listing.condition}
              value={
                listing.condition === 'new' ? text.listing.conditionNew : text.listing.conditionUsed
              }
            />
            <Spec label={text.listing.category} value={listing.category?.name ?? '—'} />
          </View>

          {/* الوصف */}
          <Card>
            <Txt size={14.5} weight={800} align="start" style={{ marginBottom: 10 }}>
              📝 {text.listing.description}
            </Txt>
            <Txt size={14} color={t.colors.ink2} align="start" style={{ lineHeight: t.fs(27) }}>
              {listing.description}
            </Txt>
          </Card>

          {/* البائع */}
          <Card>
            <View style={[t.row, { alignItems: 'center', gap: 11 }]}>
              <Avatar initial={listing.seller.initial} />
              <View style={{ flex: 1 }}>
                <View style={[t.row, { alignItems: 'center', gap: 6 }]}>
                  <Txt size={15} weight={800} align="start">
                    {listing.seller.name}
                  </Txt>
                  {listing.seller.phone_verified ? (
                    <Txt size={13} color={t.colors.info}>
                      ✔
                    </Txt>
                  ) : null}
                </View>
                <Txt size={11.5} weight={600} muted align="start">
                  {tp(text.listing.memberSince, { year: listing.seller.joined_year })} ·{' '}
                  {tp(text.listing.sellerListings, { count: listing.seller.listings_count })}
                </Txt>
              </View>
            </View>
          </Card>

          {/* الإبلاغ عن الإعلان · وحظر صاحبه — كلاهما مطلوب في سياسة UGC */}
          <View style={[t.row, { justifyContent: 'center', gap: 18 }]}>
            <Pressable onPress={() => setReportOpen(true)} style={{ paddingVertical: 8 }}>
              <Txt size={13} weight={700} color={t.colors.ink3} align="center">
                🚩 {text.listing.report}
              </Txt>
            </Pressable>
            {listing.can_edit ? null : (
              <Pressable onPress={blockSeller} style={{ paddingVertical: 8 }}>
                <Txt size={13} weight={700} color={t.colors.ink3} align="center">
                  🚫 {text.listing.block}
                </Txt>
              </Pressable>
            )}
          </View>
        </View>
      </ScrollView>

      {/* شريط المالك — كان صاحب الإعلان يرى شريطًا فارغًا وبلا أي طريق للتعديل */}
      {listing.can_edit ? (
        <View
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: t.colors.surface,
            borderTopWidth: 1,
            borderTopColor: t.colors.line,
            padding: 10,
            paddingBottom: 10 + insets.bottom,
            ...t.shadow('lg'),
          }}
        >
          <View style={[t.row, { gap: 10, alignItems: 'center' }]}>
            <Txt size={12} weight={700} muted style={{ flex: 1 }} align="start">
              👤 {text.listing.yours}
            </Txt>
            <Button
              title={text.listing.edit}
              icon="✏️"
              onPress={() => navigation.navigate('EditListing', { id: listing.id })}
            />
          </View>
        </View>
      ) : null}

      {/* شريط الإجراءات السفلي */}
      {listing.status === 'published' && !listing.can_edit ? (
        <View
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: t.colors.surface,
            borderTopWidth: 1,
            borderTopColor: t.colors.line,
            padding: 10,
            paddingBottom: 10 + insets.bottom,
            ...t.shadow('lg'),
          }}
        >
          <View style={[t.row, { gap: 8, alignItems: 'center' }]}>
            <IconButton
              icon={isFavorite ? '❤' : '♡'}
              size={46}
              color={isFavorite ? t.colors.danger : t.colors.ink2}
              background={isFavorite ? t.colors.danger50 : t.colors.surface}
              style={{
                borderWidth: 1,
                borderColor: isFavorite ? t.colors.danger : t.colors.line,
                borderRadius: t.radius.md,
              }}
              onPress={async () => {
                try {
                  const added = await favorites.toggle(listing.id);
                  toast.show(added ? text.favorites.added : text.favorites.removed);
                } catch (caught) {
                  toast.show((caught as Error).message);
                }
              }}
            />
            <IconButton
              icon="📞"
              size={46}
              style={{
                borderWidth: 1,
                borderColor: t.colors.line,
                borderRadius: t.radius.md,
              }}
              onPress={callSeller}
            />
            {config.features.whatsapp_enabled ? (
              <Button
                title={text.listing.contactWhatsapp}
                icon="💬"
                loading={contacting}
                style={{ flex: 1 }}
                onPress={contactSeller}
              />
            ) : null}
          </View>
        </View>
      ) : null}

      <VideoPlayerModal url={playing} onClose={() => setPlaying(null)} />

      {/* الإبلاغ */}
      <Sheet
        visible={reportOpen}
        title={text.listing.reportTitle}
        onClose={() => setReportOpen(false)}
        footer={
          <>
            <Button
              title={text.common.cancel}
              variant="ghost"
              style={{ flex: 1 }}
              onPress={() => setReportOpen(false)}
            />
            <Button title={text.listing.reportSend} variant="danger" style={{ flex: 1 }} onPress={submitReport} />
          </>
        }
      >
        <OptionList
          options={REPORT_REASONS.map((reason) => ({
            value: reason.value,
            label: `${reason.icon}  ${reasonLabel(reason.value, lang)}`,
          }))}
          value={reportReason}
          onChange={setReportReason}
        />
        <View style={{ marginTop: 16 }}>
          <Field label={text.listing.reportNote}>
            <TextArea value={reportNote} onChangeText={setReportNote} maxLength={1000} />
          </Field>
        </View>
      </Sheet>
    </View>
  );
}

function Spec({ label, value }: { label: string; value: string }) {
  const t = useTheme();
  return (
    <View
      style={{
        flex: 1,
        backgroundColor: t.colors.surface2,
        borderWidth: 1,
        borderColor: t.colors.line,
        borderRadius: t.radius.sm,
        paddingHorizontal: 11,
        paddingVertical: 9,
      }}
    >
      <Txt size={11} weight={700} muted align="start">
        {label}
      </Txt>
      <Txt size={13.5} weight={800} align="start">
        {value}
      </Txt>
    </View>
  );
}

function reasonLabel(value: string, lang: 'ar' | 'tr' | 'en'): string {
  const labels: Record<string, Record<string, string>> = {
    fraud: { ar: 'احتيال', tr: 'Dolandırıcılık', en: 'Fraud' },
    fake: { ar: 'إعلان مزيف', tr: 'Sahte ilan', en: 'Fake listing' },
    violation: { ar: 'محتوى مخالف', tr: 'Uygunsuz içerik', en: 'Inappropriate content' },
    banned_item: { ar: 'منتج ممنوع', tr: 'Yasaklı ürün', en: 'Banned item' },
    other: { ar: 'سبب آخر', tr: 'Diğer', en: 'Other' },
  };
  return labels[value]?.[lang] ?? value;
}
