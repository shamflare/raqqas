'use client';

import React, { useState } from 'react';

import { api } from '@/lib/api';
import { Empty, Spinner, useAdmin, useApi } from '@/lib/admin';

type AdminUserRow = {
  id: number;
  name: string;
  phone: string;
  whatsapp: string;
  role: string;
  status: string;
  language: string;
  listings_total: number;
  listings_approved_count: number;
  auto_publish: boolean;
  created_at: string;
  last_seen_at: string | null;
};

type Page = { results: AdminUserRow[]; count: number; page: number; has_next: boolean };

const STATUS_LABELS: Record<string, string> = {
  active: 'نشط',
  suspended: 'موقوف',
  banned: 'محظور',
};

/**
 * كلمة مقترحة سهلة الإملاء على الهاتف: أربعة أحرف لاتينية صغيرة ثم أربعة أرقام.
 * لا أرقام فقط — المدقّق في الخادم يرفض الكلمة الرقمية بالكامل.
 * والأحرف المتشابهة (l · o · i) محذوفة كي لا يخطئ العميل في كتابتها.
 */
function suggestPassword(): string {
  const letters = 'abcdefghjkmnpqrstuvwxyz';
  const random = new Uint32Array(8);
  crypto.getRandomValues(random);
  const head = Array.from(random.slice(0, 4), (n) => letters[n % letters.length]).join('');
  const tail = Array.from(random.slice(4), (n) => String(n % 10)).join('');
  return head + tail;
}

type IssuedPassword = { name: string; phone: string; password: string };

const ROLE_LABELS: Record<string, string> = {
  user: 'مستخدم',
  moderator: 'مشرف',
  admin: 'مدير',
};

export default function UsersPage() {
  const { toast, user: me } = useAdmin();
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  // تبديلات لم يردّ عليها الخادم بعد — تُعرض فورًا كي لا يبدو المربّع متجمّدًا
  const [pending, setPending] = useState<Record<number, boolean>>({});
  // آخر كلمة عُيّنت — تبقى ظاهرة حتى يغلقها المدير، كي ينسخها ويرسلها للعميل
  const [issued, setIssued] = useState<IssuedPassword | null>(null);
  const isAdmin = me?.role === 'admin';

  const { data, loading, reload } = useApi<Page>('/admin/users', {
    q: query || undefined,
    status: status || undefined,
    page,
  });

  /**
   * منح النشر بلا مراجعة لهذا الحساب وحده.
   *
   * نحدّث الصف محليًا قبل ردّ الخادم لأن المربّع يجب أن يستجيب للنقرة فورًا؛
   * وإن فشل الطلب نعيد تحميل الجدول فيعود المربّع إلى حقيقته.
   */
  const toggleAutoPublish = async (row: AdminUserRow, next: boolean) => {
    setPending((current) => ({ ...current, [row.id]: next }));
    try {
      await api(`/admin/users/${row.id}/auto-publish`, {
        method: 'POST',
        body: { auto_publish: next },
      });
      toast(next ? `${row.name} ينشر الآن بلا مراجعة` : `عادت إعلانات ${row.name} إلى المراجعة`);
    } catch (caught) {
      toast((caught as Error).message);
    } finally {
      setPending((current) => {
        const rest = { ...current };
        delete rest[row.id];
        return rest;
      });
      void reload();
    }
  };

  const setStatusFor = async (row: AdminUserRow, next: string) => {
    let reason = '';
    if (next !== 'active') {
      const entered = prompt(`سبب ${next === 'banned' ? 'الحظر' : 'الإيقاف'}:`);
      if (entered === null) return;
      reason = entered;
    }
    try {
      await api(`/admin/users/${row.id}/status`, {
        method: 'POST',
        body: { status: next, reason },
      });
      toast('حُدّثت حالة الحساب');
      void reload();
    } catch (caught) {
      toast((caught as Error).message);
    }
  };

  /**
   * تعيين كلمة جديدة لعميل تواصل مع الإدارة.
   *
   * نقترح كلمة جاهزة يستطيع المدير تعديلها. والخادم يُخرج العميل من كل أجهزته،
   * فيدخل بعدها بالكلمة الجديدة وحدها.
   */
  const resetPassword = async (row: AdminUserRow) => {
    const entered = prompt(
      `كلمة المرور الجديدة لـ ${row.name} (${row.phone}):\n` +
        'يمكنك تعديل الكلمة المقترحة — 6 خانات على الأقل، ولا تكون أرقامًا فقط.',
      suggestPassword(),
    );
    if (entered === null) return;
    const password = entered.trim();
    if (!password) return;
    try {
      await api(`/admin/users/${row.id}/password`, {
        method: 'POST',
        body: { new_password: password },
      });
      setIssued({ name: row.name, phone: row.phone, password });
      toast(`عُيّنت كلمة مرور جديدة لـ ${row.name}`);
    } catch (caught) {
      toast((caught as Error).message);
    }
  };

  const copyIssued = async () => {
    if (!issued) return;
    try {
      await navigator.clipboard.writeText(issued.password);
      toast('نُسخت كلمة المرور');
    } catch {
      toast('تعذّر النسخ — انسخها يدويًا');
    }
  };

  return (
    <div>
      <h1 className="page-title">👥 المستخدمون</h1>
      <p className="page-sub">{data ? `${data.count} حسابًا` : '…'}</p>

      {issued ? (
        <div className="card mb-16" style={{ borderColor: 'var(--success)' }}>
          <div className="card-title">🔑 كلمة المرور الجديدة لـ {issued.name}</div>
          <p className="muted txt-sm mb-12">
            أرسلها للعميل على رقمه <span className="ltr">{issued.phone}</span>. خرج من كل أجهزته،
            ويدخل الآن برقمه وهذه الكلمة. لن تظهر مرة أخرى بعد إغلاق هذا المربّع.
          </p>
          <div className="row wrap" style={{ gap: 8, alignItems: 'center' }}>
            <code
              className="ltr bold"
              style={{ fontSize: 20, letterSpacing: 2, padding: '6px 14px', background: 'var(--brand-50)', borderRadius: 8 }}
            >
              {issued.password}
            </code>
            <button className="btn btn-primary btn-sm" onClick={copyIssued}>نسخ</button>
            <button className="btn btn-ghost btn-sm" onClick={() => setIssued(null)}>إغلاق</button>
          </div>
        </div>
      ) : null}

      <div className="row wrap mb-16" style={{ gap: 8 }}>
        {['', 'active', 'suspended', 'banned'].map((value) => (
          <button
            key={value || 'all'}
            className={`btn btn-sm ${status === value ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => { setStatus(value); setPage(1); }}
          >
            {value ? STATUS_LABELS[value] : 'الكل'}
          </button>
        ))}
        <form
          className="row grow"
          onSubmit={(e) => { e.preventDefault(); setQuery(search); setPage(1); }}
        >
          <input
            className="input"
            placeholder="ابحث بالاسم أو الرقم…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button className="btn btn-ghost btn-sm">بحث</button>
        </form>
      </div>

      {loading && !data ? (
        <Spinner />
      ) : !data || data.results.length === 0 ? (
        <Empty icon="👤" title="لا توجد حسابات" />
      ) : (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>الاسم</th>
                  <th>الهاتف</th>
                  <th>الدور</th>
                  <th>الإعلانات</th>
                  <th>النشر التلقائي</th>
                  <th>الحالة</th>
                  <th>الإجراءات</th>
                </tr>
              </thead>
              <tbody>
                {data.results.map((row) => (
                  <tr key={row.id}>
                    <td className="bold">{row.name}</td>
                    <td className="ltr" style={{ textAlign: 'start' }}>
                      {row.phone}
                      {row.whatsapp ? (
                        <div className="muted txt-sm">واتساب: {row.whatsapp}</div>
                      ) : null}
                    </td>
                    <td>{ROLE_LABELS[row.role] ?? row.role}</td>
                    <td>
                      <span className="bold">{row.listings_total}</span>
                      <span className="muted txt-sm"> ({row.listings_approved_count} مقبول)</span>
                    </td>
                    <td>
                      <label
                        className="row"
                        style={{ gap: 6, alignItems: 'center', cursor: 'pointer' }}
                        title="عند التحديد تُنشر إعلانات هذا المستخدم فورًا بلا مراجعة"
                      >
                        <input
                          type="checkbox"
                          checked={pending[row.id] ?? row.auto_publish}
                          onChange={(e) => toggleAutoPublish(row, e.target.checked)}
                          style={{ width: 17, height: 17, accentColor: 'var(--brand)', cursor: 'pointer' }}
                        />
                        <span className="muted txt-sm">
                          {(pending[row.id] ?? row.auto_publish) ? 'بلا مراجعة' : 'يُراجَع'}
                        </span>
                      </label>
                    </td>
                    <td>
                      <span
                        className={`status status-${row.status === 'active' ? 'published' : row.status === 'suspended' ? 'pending' : 'rejected'}`}
                      >
                        {STATUS_LABELS[row.status]}
                      </span>
                    </td>
                    <td>
                      {row.role === 'admin' || row.id === me?.id ? (
                        <span className="muted txt-sm">—</span>
                      ) : (
                        <div className="row" style={{ gap: 5 }}>
                          {isAdmin ? (
                            <button
                              className="btn btn-soft btn-sm"
                              onClick={() => resetPassword(row)}
                              title="تعيين كلمة مرور جديدة لهذا الحساب"
                            >
                              🔑 كلمة المرور
                            </button>
                          ) : null}
                          {row.status !== 'active' ? (
                            <button
                              className="btn btn-success btn-sm"
                              onClick={() => setStatusFor(row, 'active')}
                            >
                              تفعيل
                            </button>
                          ) : (
                            <>
                              <button
                                className="btn btn-ghost btn-sm"
                                onClick={() => setStatusFor(row, 'suspended')}
                              >
                                إيقاف
                              </button>
                              <button
                                className="btn btn-danger btn-sm"
                                onClick={() => setStatusFor(row, 'banned')}
                              >
                                حظر
                              </button>
                            </>
                          )}
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="row-between mt-16">
            <button
              className="btn btn-ghost btn-sm"
              disabled={page === 1}
              onClick={() => setPage((p) => p - 1)}
            >
              → السابق
            </button>
            <span className="muted txt-sm">صفحة {data.page}</span>
            <button
              className="btn btn-ghost btn-sm"
              disabled={!data.has_next}
              onClick={() => setPage((p) => p + 1)}
            >
              التالي ←
            </button>
          </div>
        </>
      )}
    </div>
  );
}
