'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import React, { useEffect, useState } from 'react';

import { API_URL } from '@/lib/api';
import { AdminProvider, Spinner, useAdmin, useApi } from '@/lib/admin';

const LINKS = [
  { href: '/admin', icon: '📊', label: 'لوحة الأرقام', exact: true },
  { href: '/admin/review', icon: '⏳', label: 'صفّ المراجعة', badge: 'pending' },
  { href: '/admin/listings', icon: '📋', label: 'كل الإعلانات' },
  { href: '/admin/reports', icon: '🚩', label: 'البلاغات', badge: 'reports' },
  { href: '/admin/users', icon: '👥', label: 'المستخدمون' },
  { href: '/admin/categories', icon: '📂', label: 'الأقسام', adminOnly: true },
  { href: '/admin/design', icon: '🎨', label: 'محرّر التصميم', adminOnly: true },
  { href: '/admin/whatsapp', icon: '💬', label: 'واتساب', adminOnly: true },
  { href: '/admin/updates', icon: '🔄', label: 'التحديثات', adminOnly: true },
  { href: '/admin/settings', icon: '⚙️', label: 'الإعدادات', adminOnly: true },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <AdminProvider>
      <Shell>{children}</Shell>
    </AdminProvider>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  const { user, ready, logout } = useAdmin();
  const pathname = usePathname();
  const router = useRouter();
  const isLogin = pathname === '/admin/login';

  useEffect(() => {
    if (ready && !user && !isLogin) router.replace('/admin/login');
    if (ready && user && isLogin) router.replace('/admin');
  }, [ready, user, isLogin, router]);

  if (!ready) return <Spinner />;
  if (isLogin) return <>{children}</>;
  if (!user) return <Spinner />;

  return (
    <>
      <header className="admin-header">
        <div className="admin-header-inner">
          <div className="row">
            <Brand />
          </div>
          <div className="grow" />
          <span className="txt-sm" style={{ opacity: 0.85, fontWeight: 700 }}>
            {user.name}
          </span>
          <button className="btn btn-sm btn-ghost" onClick={logout}>
            خروج
          </button>
        </div>
      </header>

      <div className="admin-shell">
        <aside className="admin-side">
          <Sidebar pathname={pathname} role={user.role} />
        </aside>
        <main>{children}</main>
      </div>
    </>
  );
}


/**
 * هوية اللوحة — من الإعدادات لا من الكود.
 *
 * كان الاسم والحرف مكتوبين ثابتين هنا، فيغيّرهما الأدمن في «هوية التطبيق»
 * ويرى التطبيق والصفحة التعريفية يتغيّران بينما لوحته هي وحدها لا تتغيّر —
 * فيظنّ أن الحفظ لم ينجح.
 *
 * نقرأ من `/app-config` العام لا من مسار إداري: الترويسة تُرسم قبل اكتمال
 * التحقّق من الجلسة، وطلبٌ يحتاج رمز دخول كان سيفشل في تلك اللحظة.
 */
function Brand() {
  const [brand, setBrand] = useState<{ name: string; mark: string; logo: string | null } | null>(
    null,
  );

  useEffect(() => {
    let alive = true;
    fetch(`${API_URL}/app-config`)
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (alive && data?.brand) setBrand(data.brand);
      })
      .catch(() => {
        /* الإعدادات غير متاحة — نبقى على النصّ الاحتياطي */
      });
    return () => {
      alive = false;
    };
  }, []);

  const name = brand?.name || 'سوق الرقة';
  const mark = brand?.mark || 'س';

  return (
    <>
      {brand?.logo ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={brand.logo}
          alt={name}
          width={34}
          height={34}
          style={{ borderRadius: 10, objectFit: 'cover', background: '#fff' }}
        />
      ) : (
        <span className="admin-mark">{mark}</span>
      )}
      <div>
        <div style={{ fontSize: 15, fontWeight: 900, lineHeight: 1.2 }}>{name}</div>
        <div style={{ fontSize: 10.5, opacity: 0.7, fontWeight: 600 }}>لوحة الإدارة</div>
      </div>
    </>
  );
}

function Sidebar({ pathname, role }: { pathname: string; role: string }) {
  // عدّادان فقط يستحقّان أن يُطلبا باستمرار: ما ينتظر تدخّلك
  const { data } = useApi<{
    listings: { by_status: Record<string, number> };
    reports: { open: number };
  }>('/admin/dashboard');

  const counts: Record<string, number> = {
    pending: data?.listings.by_status?.pending ?? 0,
    reports: data?.reports.open ?? 0,
  };

  return (
    <nav className="menu">
      {LINKS.filter((link) => !link.adminOnly || role === 'admin').map((link) => {
        const active = link.exact ? pathname === link.href : pathname.startsWith(link.href);
        const badge = link.badge ? counts[link.badge] : 0;
        return (
          <Link
            key={link.href}
            href={link.href}
            className={`menu-item${active ? ' is-active' : ''}`}
          >
            <span className="menu-icon">{link.icon}</span>
            <span>{link.label}</span>
            {badge > 0 ? <span className="menu-count">{badge}</span> : null}
          </Link>
        );
      })}
    </nav>
  );
}
