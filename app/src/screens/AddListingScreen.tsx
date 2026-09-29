import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { Image } from 'expo-image';
import * as ImagePicker from 'expo-image-picker';
import React, { useMemo, useState } from 'react';
import { Platform, Pressable, View } from 'react-native';

import { api, ApiError } from '../api/client';
import { uploadPhotos, uploadVideo, type PickedPhoto, type PickedVideo } from '../api/photos';
import type { Category, City, Listing } from '../api/types';
import { ChoiceGroup, Field, Input, SelectButton, TextArea } from '../components/Field';
import { KeyboardScroll } from '../components/KeyboardScroll';
import { SubHeader } from '../components/Header';
import { OptionList, Sheet } from '../components/Sheet';
import { useToast } from '../components/Toast';
import { Button, Notice, Txt } from '../components/ui';
import { usePickVideo, VideoTile } from '../components/Video';
import { useResource } from '../hooks/useResource';
import { useI18n } from '../i18n';
import type { RootStackParamList } from '../navigation/types';
import { useAppConfig } from '../state/AppConfigContext';
import { useTheme } from '../theme/ThemeProvider';

type Props = NativeStackScreenProps<RootStackParamList, 'Add'>;
type Picked = PickedPhoto;

/** ما بعد الضغط على «نشر»: الإعلان وصل، وحال الصور والفيديو هي ما يحدّد الشاشة التالية. */
type Outcome = {
  listingId: number;
  failed: number;
  total: number;
  message?: string;
  detail?: string;
  /** الفيديو لم يصل — يُعاد وحده، فالإعلان وصوره محفوظة. */
  videoFailed?: boolean;
};

export function AddListingScreen({ navigation }: Props) {
  const t = useTheme();
  const { t: text, tp } = useI18n();
  const { config, currency } = useAppConfig();
  const toast = useToast();

  const { data: categories } = useResource<Category[]>('/categories', { cacheKey: 'categories' });
  const { data: cities } = useResource<City[]>('/cities', { cacheKey: 'cities' });

  const [photos, setPhotos] = useState<Picked[]>([]);
  const [video, setVideo] = useState<PickedVideo | null>(null);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [price, setPrice] = useState('');
  // العملة الافتراضية هي التي يقرأ بها المستخدم الآن — أرجح تخمين، وقابل للتبديل
  const [priceCurrency, setPriceCurrency] = useState(currency);
  const [condition, setCondition] = useState<'new' | 'used'>('used');
  const [parentId, setParentId] = useState<number | null>(null);
  const [categoryId, setCategoryId] = useState<number | null>(null);
  const [cityId, setCityId] = useState<number | null>(null);
  const [address, setAddress] = useState('');

  const [sheet, setSheet] = useState<'parent' | 'child' | 'city' | null>(null);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [uploadingVideo, setUploadingVideo] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [outcome, setOutcome] = useState<Outcome | null>(null);

  const parent = categories?.find((c) => c.id === parentId) ?? null;
  const child = parent?.children?.find((c) => c.id === categoryId) ?? null;
  const city = useMemo(() => cities?.find((c) => c.id === cityId) ?? null, [cities, cityId]);
  const maxPhotos = config.limits.max_photos_per_listing;
  const maxVideoSeconds = config.limits.max_video_seconds;
  const pickVideo = usePickVideo();

  /* ---------------------------------------------------------------- الصور */

  const pickPhotos = async () => {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      toast.show(text.errors.permissionPhotos);
      return;
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      allowsMultipleSelection: true,
      selectionLimit: maxPhotos - photos.length,
      // ضغط قبل الرفع — الإنترنت ضعيف، والخادم يعيد الضغط أيضًا
      quality: 0.75,
    });
    if (result.canceled) return;

    const picked: Picked[] = result.assets.map((asset, index) => ({
      uri: asset.uri,
      name: asset.fileName || `photo-${Date.now()}-${index}.jpg`,
      type: asset.mimeType || 'image/jpeg',
    }));
    setPhotos((current) => [...current, ...picked].slice(0, maxPhotos));
  };

  const removePhoto = (index: number) =>
    setPhotos((current) => current.filter((_, i) => i !== index));

  /* ---------------------------------------------------------------- الإرسال */

  const canSubmit =
    title.trim().length >= 5 &&
    description.trim().length >= config.limits.min_description_length &&
    categoryId !== null &&
    cityId !== null;

  /**
   * رفع الصور ثم الفيديو على إعلان أُنشئ فعلًا — عند النشر وعند إعادة المحاولة.
   *
   * الصور أولًا: هي ما يُعرض في كل مكان، والفيديو إضافة. فإن انقطع الإنترنت
   * أثناء رفع الفيديو الطويل يبقى الإعلان كاملًا بصوره.
   */
  const sendMedia = async (listingId: number, queue: Picked[], clip: PickedVideo | null) => {
    let failed: Picked[] = [];
    let message: string | undefined;
    let detail: string | undefined;

    if (queue.length) {
      setProgress({ done: 0, total: queue.length });
      const result = await uploadPhotos(listingId, queue, (done, total) =>
        setProgress({ done, total }),
      );
      setProgress(null);
      ({ failed, message, detail } = result);
    }
    setPhotos(failed);

    let videoFailed = false;
    if (clip) {
      setUploadingVideo(true);
      const result = await uploadVideo(listingId, clip);
      setUploadingVideo(false);
      if (result.ok) {
        setVideo(null);
      } else {
        videoFailed = true;
        message = message ?? result.message;
        detail = detail ?? result.detail;
      }
    }

    setOutcome({ listingId, failed: failed.length, total: queue.length, message, detail, videoFailed });
  };

  const submit = async () => {
    if (photos.length === 0) {
      toast.show(text.add.needPhoto);
      return;
    }
    setBusy(true);
    setError(null);

    try {
      const listing = await api.post<Listing>('/listings', {
        title: title.trim(),
        description: description.trim(),
        price: price.trim() === '' ? null : Number(price.replace(/\D/g, '')),
        price_currency: priceCurrency,
        condition,
        category: categoryId,
        city: cityId,
        address: address.trim(),
      });

      await sendMedia(listing.id, photos, video);
    } catch (caught) {
      if (caught instanceof ApiError) setError(caught);
      else toast.show(text.errors.generic);
    } finally {
      setBusy(false);
    }
  };

  const retryPhotos = async () => {
    if (!outcome) return;
    setBusy(true);
    try {
      await sendMedia(outcome.listingId, photos, video);
    } finally {
      setBusy(false);
    }
  };

  const goToMyListings = () => {
    navigation.goBack();
    navigation.navigate('MyListings');
  };

  /* ---------------------------------------------------------------- شاشة النتيجة */

  /**
   * لا نعرض «🎉 وصلنا إعلانك» إلا إذا وصلت الصور فعلًا.
   *
   * هذا بالضبط ما كان معطوبًا: الصور تفشل، والشاشة تهنّئ، فيخرج المستخدم واثقًا
   * أن إعلانه كامل. الآن الفشل يظهر بحجمه، ومعه زرّ يعيد المحاولة على ما فشل
   * وحده — لأن الإعلان نفسه محفوظ ولا داعي لكتابته من جديد.
   */
  if (outcome) {
    const allFailed = outcome.failed === outcome.total;
    const anyFailed = outcome.failed > 0 || !!outcome.videoFailed;
    return (
      <View style={{ flex: 1, backgroundColor: t.colors.bg }}>
        <SubHeader title={text.add.title} onBack={goToMyListings} />
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24, gap: 10 }}>
          <Txt size={64}>{anyFailed ? '⚠️' : '🎉'}</Txt>
          <Txt size={20} weight={900} align="center">
            {outcome.failed > 0
              ? text.add.photosFailedTitle
              : outcome.videoFailed
                ? text.add.videoFailedTitle
                : text.add.successTitle}
          </Txt>
          <Txt size={14} muted align="center" style={{ lineHeight: t.fs(24), marginBottom: 12 }}>
            {outcome.failed === 0
              ? outcome.videoFailed
                ? text.add.videoFailedText
                : text.add.successText
              : allFailed
                ? tp(text.add.photosFailedText, { count: outcome.failed })
                : tp(text.add.photosPartialText, {
                    done: outcome.total - outcome.failed,
                    total: outcome.total,
                  })}
          </Txt>

          {anyFailed ? (
            <View style={{ alignSelf: 'stretch', gap: 10, marginBottom: 4 }}>
              {outcome.message ? <Notice tone="danger">{outcome.message}</Notice> : null}
              {outcome.detail ? (
                <Txt size={10.5} muted align="center">
                  {outcome.detail}
                </Txt>
              ) : null}
              <Button
                title={outcome.failed > 0 ? text.add.retryPhotos : text.add.retryVideo}
                icon="↻"
                block
                loading={busy}
                onPress={retryPhotos}
              />
            </View>
          ) : null}

          <Button
            title={anyFailed ? text.add.skipPhotos : text.add.successCta}
            variant={anyFailed ? 'ghost' : 'primary'}
            onPress={goToMyListings}
          />
        </View>
      </View>
    );
  }

  /* ---------------------------------------------------------------- النموذج */

  return (
    <View style={{ flex: 1, backgroundColor: t.colors.bg }}>
      <SubHeader title={text.add.title} onBack={() => navigation.goBack()} />

      <KeyboardScroll contentContainerStyle={{ padding: 14, paddingBottom: 40 }}>
        {error && !error.fields ? (
          <View style={{ marginBottom: 16 }}>
            <Notice tone="danger">{error.message}</Notice>
          </View>
        ) : null}

        {/* الصور */}
        <Field
          label={`📸 ${text.add.photos}`}
          required
          hint={tp(text.add.photosHint, { max: maxPhotos })}
        >
          <View style={[t.row, { flexWrap: 'wrap', gap: 8 }]}>
            {photos.map((photo, index) => (
              <View
                key={photo.uri}
                style={{
                  width: 76,
                  height: 76,
                  borderRadius: t.radius.sm,
                  overflow: 'hidden',
                  backgroundColor: t.colors.surface2,
                }}
              >
                <Image source={{ uri: photo.uri }} style={{ width: '100%', height: '100%' }} contentFit="cover" />
                <Pressable
                  onPress={() => removePhoto(index)}
                  hitSlop={6}
                  style={{
                    position: 'absolute',
                    top: 3,
                    [t.isRTL ? 'left' : 'right']: 3,
                    width: 22,
                    height: 22,
                    borderRadius: t.radius.full,
                    backgroundColor: 'rgba(0,0,0,0.6)',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <Txt size={12} color="#FFFFFF">
                    ✕
                  </Txt>
                </Pressable>
                {index === 0 ? (
                  <View
                    style={{
                      position: 'absolute',
                      bottom: 0,
                      left: 0,
                      right: 0,
                      backgroundColor: t.colors.brand,
                      paddingVertical: 2,
                    }}
                  >
                    <Txt size={9.5} weight={800} color={t.colors.onBrand} align="center">
                      {text.add.mainPhoto}
                    </Txt>
                  </View>
                ) : null}
              </View>
            ))}

            {photos.length < maxPhotos ? (
              <Pressable
                onPress={pickPhotos}
                style={({ pressed }) => ({
                  width: 76,
                  height: 76,
                  borderRadius: t.radius.sm,
                  borderWidth: 1.5,
                  borderStyle: 'dashed',
                  borderColor: t.colors.brand100,
                  backgroundColor: t.colors.brand50,
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 2,
                  opacity: pressed ? 0.7 : 1,
                })}
              >
                <Txt size={20} color={t.colors.brandText}>
                  ＋
                </Txt>
                <Txt size={10} weight={700} color={t.colors.brandText}>
                  {text.add.addPhoto}
                </Txt>
              </Pressable>
            ) : null}
          </View>
        </Field>

        {maxVideoSeconds > 0 ? (
          <Field
            label={`🎬 ${text.add.video}`}
            hint={tp(text.add.videoHint, { seconds: maxVideoSeconds })}
          >
            <VideoTile
              picked={video}
              onAdd={async () => {
                const clip = await pickVideo();
                if (clip) setVideo(clip);
              }}
              onRemove={() => setVideo(null)}
            />
          </Field>
        ) : null}

        <Field
          label={text.add.listingTitle}
          required
          hint={text.add.listingTitleHint}
          error={error?.fieldError('title')}
        >
          <Input
            value={title}
            onChangeText={setTitle}
            placeholder={text.add.listingTitlePlaceholder}
            maxLength={120}
          />
        </Field>

        <Field label={text.add.category} required error={error?.fieldError('category')}>
          <View style={{ gap: 8 }}>
            <SelectButton
              value={parent?.name}
              placeholder={text.add.chooseCategory}
              icon={parent?.icon}
              onPress={() => setSheet('parent')}
            />
            {parent?.children?.length ? (
              <SelectButton
                value={child?.name}
                placeholder={text.add.chooseSubcategory}
                onPress={() => setSheet('child')}
              />
            ) : null}
          </View>
        </Field>

        <Field label={text.add.city} required error={error?.fieldError('city')}>
          <SelectButton
            value={city?.name}
            placeholder={text.add.chooseCity}
            icon="🏙"
            onPress={() => setSheet('city')}
          />
        </Field>

        <Field
          label={text.add.address}
          hint={text.add.addressHint}
          error={error?.fieldError('address')}
        >
          <Input
            value={address}
            onChangeText={setAddress}
            placeholder={text.add.addressPlaceholder}
            maxLength={200}
          />
        </Field>

        <Field
          label={text.add.price}
          hint={text.add.priceHint}
          error={error?.fieldError('price')}
        >
          <Input
            value={price}
            onChangeText={(value) => setPrice(value.replace(/[^\d]/g, ''))}
            placeholder="0"
            keyboardType="number-pad"
            ltr
          />
        </Field>

        {/*
          عملة السعر — تُحفظ مع الإعلان ولا تُشتقّ من إعدادات المتجر.
          هذا ما يبقي رقم البائع ثابتًا مهما تحرّك سعر الصرف بعد النشر.
        */}
        {config.currency.catalogue.length > 1 ? (
          <Field label={text.add.priceCurrency} hint={text.add.priceCurrencyHint}>
            <ChoiceGroup
              options={config.currency.catalogue.map((c) => ({
                value: c.code,
                label: `${c.symbol} ${c.name}`,
              }))}
              value={priceCurrency}
              onChange={setPriceCurrency}
            />
          </Field>
        ) : null}

        <Field label={text.add.condition} required>
          <ChoiceGroup
            value={condition}
            onChange={setCondition}
            options={[
              { value: 'new', label: text.listing.conditionNew, icon: '✨' },
              { value: 'used', label: text.listing.conditionUsed, icon: '📦' },
            ]}
          />
        </Field>

        <Field
          label={text.add.description}
          required
          hint={text.add.descriptionHint}
          error={error?.fieldError('description')}
        >
          <TextArea
            value={description}
            onChangeText={setDescription}
            placeholder={text.add.descriptionPlaceholder}
            maxLength={4000}
          />
        </Field>

        <View style={{ gap: 10, marginBottom: 18 }}>
          <Notice tone="warn">{text.add.phoneNotice}</Notice>
          <Notice tone="info">{text.add.reviewNotice}</Notice>
        </View>

        <Button
          title={
            progress
              ? tp(text.add.uploadingPhotos, { done: progress.done, total: progress.total })
              : uploadingVideo
                ? text.add.uploadingVideo
                : busy
                ? text.add.submitting
                : text.add.submit
          }
          size="lg"
          block
          loading={busy}
          disabled={!canSubmit}
          onPress={submit}
        />
      </KeyboardScroll>

      {/* اختيار القسم الرئيسي */}
      <Sheet visible={sheet === 'parent'} title={text.add.chooseCategory} onClose={() => setSheet(null)}>
        <OptionList
          options={(categories ?? []).map((category) => ({
            value: category.id,
            label: `${category.icon || '📦'}  ${category.name}`,
          }))}
          value={parentId}
          onChange={(value) => {
            setParentId(value);
            const next = categories?.find((c) => c.id === value);
            // قسم بلا أقسام فرعية يُختار مباشرة
            setCategoryId(next?.children?.length ? null : value);
            setSheet(next?.children?.length ? 'child' : null);
          }}
        />
      </Sheet>

      {/* اختيار القسم الفرعي */}
      <Sheet visible={sheet === 'child'} title={text.add.chooseSubcategory} onClose={() => setSheet(null)}>
        <OptionList
          options={(parent?.children ?? []).map((category) => ({
            value: category.id,
            label: category.name,
          }))}
          value={categoryId}
          onChange={(value) => {
            setCategoryId(value);
            setSheet(null);
          }}
        />
      </Sheet>

      {/* اختيار الحي */}
      <Sheet visible={sheet === 'city'} title={text.add.chooseCity} onClose={() => setSheet(null)}>
        <OptionList
          options={(cities ?? []).map((item) => ({ value: item.id, label: item.name }))}
          value={cityId}
          onChange={(value) => {
            setCityId(value);
            setSheet(null);
          }}
        />
      </Sheet>
    </View>
  );
}
