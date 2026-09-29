import { Image } from 'expo-image';
import * as ImagePicker from 'expo-image-picker';
import { useVideoPlayer, VideoView } from 'expo-video';
import React from 'react';
import { Modal, Pressable, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import type { PickedVideo } from '../api/photos';
import type { Media } from '../api/types';
import { useI18n } from '../i18n';
import { useAppConfig } from '../state/AppConfigContext';
import { useTheme } from '../theme/ThemeProvider';
import { useToast } from './Toast';
import { Txt } from './ui';

/** 75 ثانية → «1:15» */
export function formatDuration(seconds: number): string {
  const whole = Math.max(0, Math.round(seconds));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`;
}

/**
 * اختيار فيديو من معرض الجوال، مع فحص المدة والحجم **قبل** الرفع.
 *
 * الفحص هنا مجاملة لا حماية — الخادم يعيد الفحص. لكنه يوفّر على المستخدم رفع
 * مئة ميغابايت على إنترنت الرقة ليسمع بعدها «المقطع أطول من المسموح».
 *
 * لا قصّ داخل التطبيق: منتقي أندرويد لا يقصّ الفيديو، ومعرض كل جوال يفعل.
 */
export function usePickVideo() {
  const { t: text, tp } = useI18n();
  const { config } = useAppConfig();
  const toast = useToast();
  const maxSeconds = config.limits.max_video_seconds;
  const maxMb = config.limits.max_video_mb;

  return async (): Promise<PickedVideo | null> => {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      toast.show(text.errors.permissionPhotos);
      return null;
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['videos'],
      allowsMultipleSelection: false,
      videoMaxDuration: maxSeconds,
    });
    if (result.canceled || !result.assets[0]) return null;

    const asset = result.assets[0];
    const duration = (asset.duration ?? 0) / 1000;           // المنتقي يعيد ميلي ثانية
    if (duration > maxSeconds + 1) {
      toast.show(tp(text.add.videoTooLong, { duration: Math.round(duration), max: maxSeconds }));
      return null;
    }
    if (asset.fileSize && asset.fileSize > maxMb * 1024 * 1024) {
      toast.show(tp(text.add.videoTooBig, { max: maxMb }));
      return null;
    }

    return {
      uri: asset.uri,
      name: asset.fileName || `video-${Date.now()}.mp4`,
      type: asset.mimeType || 'video/mp4',
      duration,
      size: asset.fileSize ?? null,
    };
  };
}

/**
 * مربّع الفيديو في نموذج الإعلان — بحجم مربّعات الصور وبجانبها.
 *
 * ثلاث حالات: لا فيديو (زرّ إضافة) · فيديو مختار لم يُرفع (إطار ذهبي كالصور
 * الجديدة) · فيديو مرفوع (غلافه من الخادم).
 */
export function VideoTile({
  picked,
  existing,
  onAdd,
  onRemove,
}: {
  picked: PickedVideo | null;
  existing?: Media | null;
  onAdd: () => void;
  onRemove: () => void;
}) {
  const t = useTheme();
  const { t: text } = useI18n();

  const box = {
    width: 76,
    height: 76,
    borderRadius: t.radius.sm,
    overflow: 'hidden' as const,
  };

  if (!picked && !existing) {
    return (
      <Pressable
        onPress={onAdd}
        style={({ pressed }) => ({
          ...box,
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
        <Txt size={20}>🎬</Txt>
        <Txt size={10} weight={700} color={t.colors.brandText}>
          {text.add.addVideo}
        </Txt>
      </Pressable>
    );
  }

  const duration = picked?.duration ?? existing?.duration ?? 0;
  return (
    <View
      style={[
        box,
        { backgroundColor: '#1B1B1B', alignItems: 'center', justifyContent: 'center' },
        picked ? { borderWidth: 1.5, borderColor: t.colors.gold } : null,
      ]}
    >
      {existing?.thumb_url ? (
        <Image
          source={{ uri: existing.thumb_url }}
          style={{ position: 'absolute', width: '100%', height: '100%' }}
          contentFit="cover"
        />
      ) : null}
      <Txt size={22} color="#FFFFFF">▶</Txt>
      <View
        style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          backgroundColor: 'rgba(0,0,0,0.6)',
          paddingVertical: 2,
        }}
      >
        <Txt size={9.5} weight={800} color="#FFFFFF" align="center">
          🎬 {formatDuration(duration)}
        </Txt>
      </View>
      <Pressable
        onPress={onRemove}
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
    </View>
  );
}

/**
 * مشغّل بملء الشاشة.
 *
 * يُركَّب فقط حين يُفتح: المشغّل يبدأ التنزيل لحظة إنشائه، ولا نريد أن يستهلك
 * كل من فتح الإعلان باقته على فيديو لم يطلب مشاهدته.
 */
export function VideoPlayerModal({ url, onClose }: { url: string | null; onClose: () => void }) {
  return (
    <Modal
      visible={url !== null}
      animationType="fade"
      onRequestClose={onClose}
      supportedOrientations={['portrait', 'landscape']}
    >
      {url ? <Player url={url} onClose={onClose} /> : null}
    </Modal>
  );
}

function Player({ url, onClose }: { url: string; onClose: () => void }) {
  const insets = useSafeAreaInsets();
  const player = useVideoPlayer(url, (instance) => {
    instance.loop = false;
    instance.play();
  });

  return (
    <View style={{ flex: 1, backgroundColor: '#000000' }}>
      <VideoView
        player={player}
        style={{ flex: 1 }}
        contentFit="contain"
        nativeControls
        fullscreenOptions={{ enable: true }}
      />
      <Pressable
        onPress={onClose}
        hitSlop={10}
        style={{
          position: 'absolute',
          top: insets.top + 10,
          right: 14,
          width: 38,
          height: 38,
          borderRadius: 19,
          backgroundColor: 'rgba(0,0,0,0.6)',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Txt size={18} color="#FFFFFF">
          ✕
        </Txt>
      </Pressable>
    </View>
  );
}
