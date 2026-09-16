'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';

import { api, ApiError } from '@/lib/api';
import { Notice, Spinner, useAdmin } from '@/lib/admin';

type Status = {
  provider: string;
  manageable: boolean;
  ready?: boolean;
  number?: string | null;
  name?: string | null;
  connected_at?: string | null;
  /** رمز QR صورةً جاهزة (data URL) — يولّده البوت فلا يحتاج المتصفّح مكتبة */
  qr?: string | null;
  qr_age?: number | null;
  logged_out?: boolean;
};

/** كل ثانيتين: رمز QR يتجدّد عند واتساب كل ~20 ثانية، وعرض رمز ميت يعني مسحًا لا ينجح. */
const POLL_MS = 2000;

/**
 * ربط رقم واتساب — الشاشة التي تجعل التطبيق قادرًا على إرسال رموز الاستعادة.
 *
 * صُنعت لتُستعمل بيدٍ واحدة وهاتفٍ في الأخرى: الصفحة تُحدّث نفسها، ولا تطلب
 * ضغط «تحديث» ولا نسخ شيء. أول ما يُمسح الرمز تنقلب الشاشة إلى «متصل».
 */
export default function WhatsAppPage() {
  const { toast } = useAdmin();
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [testPhone, setTestPhone] = useState('');

  // مرجع ثابت حتى لا يعيد المؤقّت بناء نفسه مع كل رسم
  const load = useCallback(async () => {
    try {
      setStatus(await api<Status>('/admin/whatsapp'));
      setError(null);
    } catch (caught) {
      setError((caught as ApiError).message);
    }
  }, []);

  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => {
    void load();
    timer.current = setInterval(() => void load(), POLL_MS);
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [load]);

  const unlink = async () => {
    if (
      !confirm(
        'فكّ ربط الرقم الحالي؟\n\n' +
          'سيتوقّف إرسال رموز استعادة كلمة المرور حتى تربط رقمًا جديدًا.',
      )
    )
      return;
    setBusy(true);
    try {
      await api('/admin/whatsapp/logout', { method: 'POST', body: {} });
      toast('فُكّ الربط — امسح الرمز الجديد لربط رقم آخر');
      await load();
    } catch (caught) {
      toast((caught as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const sendTest = async () => {
    setBusy(true);
    try {
      const result = await api<{ to: string }>('/admin/whatsapp/test', {
        method: 'POST',
        body: { phone: testPhone },
      });
      toast(`✅ أُرسلت إلى ${result.to} — تحقّق من واتساب`);
    } catch (caught) {
      toast((caught as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (!status && !error) return <Spinner />;

  return (
    <div>
      <h1 className="page-title">💬 واتساب</h1>
      <p className="page-sub">
        الرقم الذي تصل منه رموز استعادة كلمة المرور إلى الزبائن
      </p>

      {error ? (
        <div className="mb-16">
          <Notice tone="danger">
            {error}
            <br />
            <span className="txt-sm">
              إن كانت الخدمة موقوفة على الخادم:{' '}
              <code className="ltr">systemctl start souq-wa</code>
            </span>
          </Notice>
        </div>
      ) : null}

      {status && !status.manageable ? (
        <Notice tone="info">
          المزوّد الحالي <b className="ltr">{status.provider}</b> لا يُدار من هنا.
          {status.provider === 'log'
            ? ' الخادم لا يرسل رسائل واتساب أصلًا — راجع deploy/WHATSAPP.md.'
            : ' الربط يتم من حساب Meta Business.'}
        </Notice>
      ) : null}

      {status?.manageable && status.ready ? (
        <Connected status={status} busy={busy} onUnlink={unlink} />
      ) : null}

      {status?.manageable && !status.ready ? <Pairing status={status} /> : null}

      {status?.ready ? (
        <div className="card mt-16">
          <div className="bold mb-8">جرّب الإرسال</div>
          <p className="muted txt-sm">
            «مربوط» لا تعني «يرسل». الجلسة قد تكون مفتوحة والرقم ممنوعًا من
            المراسلة — وأسوأ وقت لاكتشاف ذلك هو حين ينسى زبون كلمة مروره.
          </p>
          <div className="row" style={{ gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
            <input
              className="input ltr grow"
              value={testPhone}
              onChange={(event) => setTestPhone(event.target.value)}
              placeholder="+963 944 567 890"
              style={{ minWidth: 220 }}
            />
            <button
              className="btn btn-primary"
              disabled={busy || testPhone.trim().length < 6}
              onClick={sendTest}
            >
              إرسال رسالة تجريبية
            </button>
          </div>
        </div>
      ) : null}

      <div className="mt-16">
        <Notice tone="warn">
          <b>استعمل رقمًا مخصّصًا للتطبيق، لا رقمك الشخصي.</b>
          <br />
          هذه طريقة غير رسمية، وواتساب قد يحظر الرقم بلا إنذار. لو حُظر رقم
          مخصّص اشتريت غيره؛ ولو حُظر رقمك الشخصي خسرت واتسابك كلّه.
        </Notice>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ مربوط */

function Connected({
  status,
  busy,
  onUnlink,
}: {
  status: Status;
  busy: boolean;
  onUnlink: () => void;
}) {
  return (
    <div className="card" style={{ borderColor: 'var(--success)' }}>
      <div className="row-between" style={{ flexWrap: 'wrap', gap: 12 }}>
        <div className="grow">
          <span className="status status-published">● متصل</span>
          <div className="bold ltr mt-8" style={{ fontSize: 20, textAlign: 'start' }}>
            {status.number ?? '—'}
          </div>
          {status.name ? <div className="muted">{status.name}</div> : null}
          {status.connected_at ? (
            <div className="muted txt-sm">
              منذ {new Date(status.connected_at).toLocaleString('ar-EG')}
            </div>
          ) : null}
        </div>
        <button className="btn btn-ghost" disabled={busy} onClick={onUnlink}>
          فكّ الربط
        </button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ الربط */

function Pairing({ status }: { status: Status }) {
  return (
    <div className="card">
      <div className="row-between mb-8">
        <span className="status status-draft">غير مربوط</span>
        {status.logged_out ? (
          <span className="muted txt-sm">انتهى الربط السابق</span>
        ) : null}
      </div>

      <div
        className="row"
        style={{ gap: 24, alignItems: 'flex-start', flexWrap: 'wrap', marginTop: 12 }}
      >
        <div
          style={{
            width: 240,
            height: 240,
            background: '#FFFFFF',
            borderRadius: 12,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          {status.qr ? (
            // الصورة تأتي من البوت جاهزة — لا مكتبة QR في المتصفّح ولا طلب خارجي
            // eslint-disable-next-line @next/next/no-img-element
            <img src={status.qr} alt="رمز QR لربط واتساب" width={224} height={224} />
          ) : (
            <Spinner />
          )}
        </div>

        <div className="grow" style={{ minWidth: 260 }}>
          <div className="bold mb-8">اربط الرقم في ثلاث خطوات</div>
          <ol className="stack" style={{ paddingInlineStart: 20, lineHeight: 2 }}>
            <li>افتح واتساب على هاتف الرقم المخصّص للتطبيق</li>
            <li>
              اضغط <b>⋮</b> ← <b>الأجهزة المرتبطة</b> ← <b>ربط جهاز</b>
            </li>
            <li>وجّه الكاميرا إلى الرمز</li>
          </ol>
          <p className="muted txt-sm mt-8">
            الرمز يتجدّد وحده كل بضع ثوانٍ — لا تنتظر، امسح الظاهر أمامك. وأول
            ما ينجح المسح تتغيّر هذه الشاشة من نفسها.
          </p>
        </div>
      </div>
    </div>
  );
}
