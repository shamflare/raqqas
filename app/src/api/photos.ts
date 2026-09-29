import { File, UploadType } from 'expo-file-system';

import { ApiError, api, OfflineError } from './client';
import { API_URL, UPLOAD_TIMEOUT_MS, VIDEO_UPLOAD_TIMEOUT_MS } from '../config';
import type { Media } from './types';

/** صورة اختارها المستخدم من جهازه ولم تُرفع بعد. */
export type PickedPhoto = { uri: string; name: string; type: string };

export type UploadOutcome = {
  uploaded: Media[];
  /** الصور التي لم تُرفع — تبقى في الشاشة ليعيد المستخدم المحاولة عليها وحدها. */
  failed: PickedPhoto[];
  /** رسالة صالحة للعرض للمستخدم، إن فشل شيء. */
  message?: string;
  /** نصّ الخطأ التقني — سطر صغير تحت الرسالة، يختصر ساعات تشخيص. */
  detail?: string;
};

/**
 * رفع صورة واحدة عبر الطبقة الأصلية (`expo-file-system`).
 *
 * **لماذا لا نستعمل `fetch` مع `FormData`؟** لأن ذلك المسار كان يفشل عندنا قبل
 * أن يخرج بايت واحد من الجهاز: يبني أندرويد جسم الطلب بنفسه من مسار الملف،
 * وإن تعذّر فتحه أُلغي الطلب كاملًا فلا يصل الخادمَ شيء ولا يُسجَّل أثر.
 *
 * هذه الدالة تسلّم مسار الملف للطبقة الأصلية مباشرة، فتقرأه وترفعه وتعيد
 * ردّ الخادم كما هو — بلا وسيط JavaScript يبني multipart.
 */
type Target = { path: string; fieldName: string; timeoutMs: number };

const PHOTO_TARGET = (listingId: number): Target => ({
  path: `/listings/${listingId}/media`,
  fieldName: 'images',
  timeoutMs: UPLOAD_TIMEOUT_MS,
});

async function send(target: Target, file: PickedPhoto, token: string | null) {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), target.timeoutMs);
  try {
    return await new File(file.uri).upload(`${API_URL}${target.path}`, {
      httpMethod: 'POST',
      uploadType: UploadType.MULTIPART,
      fieldName: target.fieldName,
      mimeType: file.type,
      headers,
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timer);
  }
}

/** يرسل ملفًا، ويجدّد الرمز مرة إن انتهت صلاحيته أثناء الرفع الطويل. */
async function sendWithRenewal(target: Target, file: PickedPhoto) {
  let result = await send(target, file, api.accessToken);
  if (result.status === 401) {
    const renewed = await api.renewAccessToken();
    if (renewed) result = await send(target, file, renewed);
  }
  return result;
}

async function uploadOne(listingId: number, photo: PickedPhoto): Promise<Media[]> {
  const result = await sendWithRenewal(PHOTO_TARGET(listingId), photo);

  if (result.status >= 400) {
    const error = safeJson(result.body)?.error;
    throw new ApiError(result.status, {
      code: error?.code,
      message: error?.fields?.images?.[0] ?? error?.message ?? 'تعذّر رفع الصورة.',
      fields: error?.fields,
    });
  }

  return (safeJson(result.body) ?? []) as Media[];
}

function safeJson(text: string): any {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

/**
 * رفع صور إعلان.
 *
 * **صورة واحدة في كل طلب، بالتتابع.** الدفعة الواحدة كانت تعني أن أي عطل —
 * انقطاع، مهلة، ملف واحد لا يُقرأ — يسقط الصور كلها معًا. أما هنا فتنجح الصور
 * السليمة وتُعرَف الفاشلة بعينها، وهذا ما يعمل فعلًا على إنترنت ضعيف.
 *
 * ولا يبتلع خطأً أبدًا: ما يفشل يعود في `failed` برسالته.
 */
export async function uploadPhotos(
  listingId: number,
  photos: PickedPhoto[],
  onProgress?: (done: number, total: number) => void,
): Promise<UploadOutcome> {
  const uploaded: Media[] = [];
  const failed: PickedPhoto[] = [];
  let message: string | undefined;
  let detail: string | undefined;

  for (const [index, photo] of photos.entries()) {
    try {
      uploaded.push(...(await uploadOne(listingId, photo)));
    } catch (caught) {
      failed.push(photo);
      // نحتفظ بأول خطأ فقط: عرض خمس رسائل متطابقة لا يفيد أحدًا
      if (!message) {
        if (caught instanceof ApiError) {
          message = caught.fieldError('images') ?? caught.message;
        } else if (caught instanceof OfflineError) {
          message = caught.message;
          detail = caught.detail;
        } else {
          message = 'تعذّر رفع الصورة. تحقّق من الإنترنت وأعد المحاولة.';
          detail = (caught as Error)?.message;
        }
      }
    }

    onProgress?.(index + 1, photos.length);
  }

  return { uploaded, failed, message, detail };
}

/** فيديو اختاره المستخدم ولم يُرفع بعد. `duration` بالثواني. */
export type PickedVideo = PickedPhoto & { duration: number; size: number | null };

export type VideoOutcome =
  | { ok: true; media: Media }
  | { ok: false; message: string; detail?: string };

/**
 * رفع فيديو الإعلان — مقطع واحد، بالمسار الأصلي نفسه الذي ترفع به الصور.
 *
 * الخادم يفحصه ويستخرج غلافه ويعيده فورًا، ثم يضغطه لاحقًا. فالانتظار هنا هو
 * زمن الرفع وحده — ولذلك مهلته أطول بكثير من مهلة الصورة.
 */
export async function uploadVideo(listingId: number, video: PickedVideo): Promise<VideoOutcome> {
  try {
    const result = await sendWithRenewal(
      { path: `/listings/${listingId}/video`, fieldName: 'video', timeoutMs: VIDEO_UPLOAD_TIMEOUT_MS },
      video,
    );
    const body = safeJson(result.body);
    if (result.status >= 400) {
      const error = body?.error;
      return {
        ok: false,
        message: error?.fields?.video?.[0] ?? error?.message ?? 'تعذّر رفع الفيديو.',
      };
    }
    return { ok: true, media: body as Media };
  } catch (caught) {
    if (caught instanceof OfflineError) {
      return { ok: false, message: caught.message, detail: caught.detail };
    }
    return {
      ok: false,
      message: 'تعذّر رفع الفيديو. تحقّق من الإنترنت وأعد المحاولة.',
      detail: (caught as Error)?.message,
    };
  }
}

/** حذف صورة من إعلان — نهائي وفوري. */
export function deletePhoto(listingId: number, mediaId: number) {
  return api.del(`/listings/${listingId}/media/${mediaId}`);
}
