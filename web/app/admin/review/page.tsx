'use client';

import React, { useEffect, useState } from 'react';

import { api, money } from '@/lib/api';
import { Empty, Notice, Spinner, useAdmin, useApi, waitLabel } from '@/lib/admin';

/**
 * صفّ المراجعة السريع (plan2 §8.6).
 *
 * الهدف المعلن في الخطة: تقليل زمن الانتظار، لأن أكثر ما ينفّر البائعين من
 * تطبيق جديد هو انتظار الموافقة. لذلك:
 *   · إعلان واحد كبير في الشاشة، لا قائمة يجب البحث فيها
 *   · زرّان فقط: نشر · رفض بسبب جاهز
 *   · انتقال تلقائي للتالي بعد كل قرار
 *   · اختصارات لوحة المفاتيح (م / ر / ← →) لمن يراجع عشرات الإعلانات
 */

type Media = {
  id: number;
  kind: 'photo' | 'video';
  url: string;
  thumb_url: string;
  video_url?: string | null;
  duration?: number;
};

type ReviewListing = {
  id: number;
  title: string;
  description: string;
  price: number | null;
  price_text: string;
  condition: string;
  status: string;
  media: Media[];
  category: { name: string; parent: { name: string } | null } | null;
  city: { name: string } | null;
  address: string;
  seller: { id: number; name: string; phone: string; approved_count: number; status: string };
  created_at: string;
  waiting_minutes: number | null;
};

type Queue = {
  results: ReviewListing[];
  count: number;
  waiting: {
    pending_count: number;
    oldest_wait_minutes: number;
    avg_wait_minutes_7d: number | null;
    over_threshold: boolean;
  };
};

type RejectionReason = { id: number; name: string };

export default function ReviewPage() {
  const { toast } = useAdmin();
  const { data, loading, reload } = useApi<Queue>('/admin/review-queue', { page_size: 30 });
  const { data: reasons } = useApi<RejectionReason[]>('/rejection-reasons');

  const [index, setIndex] = useState(0);
  const [photo, setPhoto] = useState(0);
  const [busy, setBusy] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState('');
  const [done, setDone] = useState<number[]>([]);

  const queue = (data?.results ?? []).filter((item) => !done.includes(item.id));
  const listing = queue[Math.min(index, queue.length - 1)] ?? null;

  useEffect(() => setPhoto(0), [listing?.id]);

  const decide = async (action: 'approve' | 'reject', why = '') => {
    if (!listing || busy) return;
    setBusy(true);
    try {
      await api(`/admin/listings/${action}`, {
        method: 'POST',
        body: { ids: [listing.id], reason: why },
      });
      toast(action === 'approve' ? '✅ نُشر الإعلان' : '↩︎ أُعيد للبائع مع السبب');
      setDone((current) => [...current, listing.id]);
      setRejecting(false);
      setReason('');
      // لا نزيد المؤشّر: حذف العنصر الحالي يقدّم التالي مكانه تلقائيًا
      setIndex((current) => Math.min(current, queue.length - 2 < 0 ? 0 : queue.length - 2));
    } catch (caught) {
      toast((caught as Error).message);
    } finally {
      setBusy(false);
    }
  };

  // اختصارات لوحة المفاتيح — الفرق بين مراجعة 10 إعلانات و100
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (rejecting || (event.target as HTMLElement)?.tagName === 'TEXTAREA') return;
      if (event.key === 'ArrowLeft') setIndex((i) => Math.min(i + 1, queue.length - 1));
      if (event.key === 'ArrowRight') setIndex((i) => Math.max(i - 1, 0));
      if (event.key === 'Enter' || event.key.toLowerCase() === 'م') void decide('approve');
      if (event.key.toLowerCase() === 'ر') setRejecting(true);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }); // بلا مصفوفة اعتماديات: المستمع يحتاج أحدث حالة في كل رسم

  if (loading && !data) return <Spinner />;

  return (
    <div>
      <div className="row-between mb-8">
        <div>
          <h1 className="page-title">صفّ المراجعة</h1>
          <p className="page-sub" style={{ marginBottom: 0 }}>
            {queue.length > 0
              ? `${queue.length} إعلانًا بانتظارك · الأقدم أولًا`
              : 'لا يوجد ما ينتظر المراجعة'}
          </p>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={() => { setDone([]); void reload(); }}>
          🔄 تحديث
        </button>
      </div>

      {data?.waiting.over_threshold ? (
        <div className="mb-16">
          <Notice tone="warn">
            متوسط الانتظار هذا الأسبوع {waitLabel(data.waiting.avg_wait_minutes_7d)} — تجاوز
            الساعتين. فكّر في نمط «الأعضاء الجدد فقط» من الإعدادات.
          </Notice>
        </div>
      ) : null}

      {!listing ? (
        <Empty
          icon="🎉"
          title="لا شيء بانتظار المراجعة"
          text="كل الإعلانات مُراجَعة. البائعون لا ينتظرون."
        />
      ) : (
        <div className="row-2" style={{ alignItems: 'start' }}>
          {/* الصور */}
          <div className="card">
            {listing.media.length > 0 ? (
              <>
                {listing.media[photo]?.kind === 'video' && listing.media[photo]?.video_url ? (
                  // المراجع يشاهد الفيديو كاملًا قبل القبول — المحتوى المرئي يُراجَع كالصور
                  <>
                    <video
                      key={listing.media[photo].id}
                      className="review-photo"
                      src={listing.media[photo].video_url ?? undefined}
                      poster={listing.media[photo].url}
                      controls
                      preload="metadata"
                      style={{ background: '#000' }}
                    />
                    <a
                      className="muted txt-sm"
                      href={listing.media[photo].video_url ?? undefined}
                      target="_blank"
                      rel="noreferrer"
                    >
                      لا يعمل التشغيل؟ افتح الملف مباشرة ↗
                    </a>
                  </>
                ) : (
                  <img
                    className="review-photo"
                    src={listing.media[photo]?.url}
                    alt={listing.title}
                  />
                )}
                {listing.media.length > 1 ? (
                  <div className="review-thumbs">
                    {listing.media.map((item, i) => (
                      <img
                        key={item.id}
                        src={item.thumb_url}
                        alt={item.kind === 'video' ? 'فيديو' : ''}
                        title={item.kind === 'video' ? `🎬 فيديو · ${item.duration ?? 0} ثانية` : undefined}
                        className={i === photo ? 'is-active' : ''}
                        style={item.kind === 'video' ? { outline: '2px solid var(--gold)' } : undefined}
                        onClick={() => setPhoto(i)}
                      />
                    ))}
                  </div>
                ) : null}
              </>
            ) : (
              <div
                className="review-photo"
                style={{ display: 'grid', placeItems: 'center', background: 'var(--brand-50)' }}
              >
                <span style={{ fontSize: 46 }}>📦</span>
              </div>
            )}
            <p className="muted txt-sm mt-8">
              {listing.media.filter((m) => m.kind !== 'video').length} صورة
              {listing.media.some((m) => m.kind === 'video') ? ' · 🎬 فيديو' : ''} · وصل منذ {waitLabel(listing.waiting_minutes)}
            </p>
          </div>

          {/* التفاصيل والقرار */}
          <div className="stack">
            <div className="card">
              <div style={{ fontSize: 22, fontWeight: 900, color: 'var(--brand-text)' }}>
                {listing.price_text}
              </div>
              <h2 style={{ fontSize: 17, fontWeight: 800, margin: '4px 0 10px', lineHeight: 1.5 }}>
                {listing.title}
              </h2>

              <div className="row wrap txt-sm muted mb-12" style={{ gap: 12 }}>
                <span>
                  📂 {listing.category?.parent?.name ?? ''} › {listing.category?.name ?? '—'}
                </span>
                <span>📍 {[listing.city?.name, listing.address].filter(Boolean).join(' · ') || '—'}</span>
                <span>{listing.condition === 'new' ? '✨ جديد' : '📦 مستعمل'}</span>
              </div>

              <p style={{ fontSize: 14, color: 'var(--ink-2)', whiteSpace: 'pre-line', lineHeight: 1.9 }}>
                {listing.description}
              </p>
            </div>

            <div className="card">
              <div className="card-title">👤 البائع</div>
              <div className="row-between">
                <div>
                  <div className="bold">{listing.seller.name}</div>
                  <div className="muted txt-sm ltr" style={{ textAlign: 'start' }}>
                    {listing.seller.phone}
                  </div>
                </div>
                <div className="txt-c">
                  <div className="bold" style={{ fontSize: 18 }}>
                    {listing.seller.approved_count}
                  </div>
                  <div className="muted txt-sm">إعلان مقبول سابقًا</div>
                </div>
              </div>
              {listing.seller.approved_count === 0 ? (
                <div className="mt-12">
                  <Notice tone="info">أول إعلان لهذا البائع — راجعه بعناية أكبر.</Notice>
                </div>
              ) : null}
            </div>

            {/* القرار */}
            {!rejecting ? (
              <div className="card">
                <div className="row" style={{ gap: 10 }}>
                  <button
                    className="btn btn-success grow btn-lg"
                    disabled={busy}
                    onClick={() => decide('approve')}
                  >
                    ✅ نشر الإعلان
                  </button>
                  <button
                    className="btn btn-danger btn-lg"
                    disabled={busy}
                    onClick={() => setRejecting(true)}
                  >
                    ✕ رفض
                  </button>
                </div>
                <div className="row-between mt-12">
                  <button
                    className="btn btn-ghost btn-sm"
                    disabled={index === 0}
                    onClick={() => setIndex((i) => Math.max(i - 1, 0))}
                  >
                    ← السابق
                  </button>
                  <span className="muted txt-sm">
                    {index + 1} من {queue.length}
                  </span>
                  <button
                    className="btn btn-ghost btn-sm"
                    disabled={index >= queue.length - 1}
                    onClick={() => setIndex((i) => Math.min(i + 1, queue.length - 1))}
                  >
                    التالي →
                  </button>
                </div>
                <p className="hint txt-c mt-8">
                  اختصارات: <b>Enter</b> نشر · <b>ر</b> رفض · <b>← →</b> تنقّل
                </p>
              </div>
            ) : (
              <div className="card">
                <div className="card-title">سبب الرفض</div>
                <p className="hint mb-12">
                  يصل السبب للبائع كما هو مع إشعار — اكتبه بوضوح ليعرف ما يصلحه.
                </p>

                <div className="stack" style={{ gap: 6 }}>
                  {(reasons ?? []).map((item) => (
                    <button
                      key={item.id}
                      className="btn btn-ghost"
                      style={{ justifyContent: 'flex-start', textAlign: 'start' }}
                      onClick={() => setReason(item.name)}
                    >
                      {item.name}
                    </button>
                  ))}
                </div>

                <div className="field mt-12">
                  <label className="label">السبب المُرسَل</label>
                  <textarea
                    className="textarea"
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder="اختر سببًا جاهزًا أعلاه أو اكتب سببًا خاصًا…"
                    style={{ minHeight: 90 }}
                  />
                </div>

                <div className="row" style={{ gap: 10 }}>
                  <button
                    className="btn btn-danger grow"
                    disabled={busy || reason.trim().length < 5}
                    onClick={() => decide('reject', reason.trim())}
                  >
                    إرسال الرفض
                  </button>
                  <button className="btn btn-ghost" onClick={() => setRejecting(false)}>
                    إلغاء
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
