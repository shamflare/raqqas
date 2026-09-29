'use client';

import Link from 'next/link';
import React, { createContext, useContext, useState } from 'react';

import styles from './legal.module.css';
import { IDENTITY, LANGS, type Doc, type Lang } from './content';

/**
 * عارض الوثائق القانونية — بمبدّل لغة.
 *
 * ثلاث لغات في **صفحة واحدة** لا ثلاثة مسارات: Google Play يطلب رابطًا واحدًا
 * لسياسة الخصوصية، ومستخدمونا يقرؤون بثلاث لغات. مسارات منفصلة كانت ستعني أن
 * رابط الكونسول يقود إلى نسخة عربية وحدها بينما المراجع يقرأ الإنكليزية.
 */
/**
 * اللغة المختارة، لمن يُركَّب داخل الصفحة.
 *
 * لم نمرّرها دالةً في `children` لأن مكوّن الخادم لا يستطيع تمرير دالة إلى
 * مكوّن عميل — يفشل البناء عند التوليد المسبق. السياق يعبر الحدّ بلا مشكلة:
 * الصفحة تمرّر عنصرًا جاهزًا، وهو يقرأ اللغة من هنا.
 */
const LegalLangContext = createContext<Lang>('ar');

export function useLegalLang(): Lang {
  return useContext(LegalLangContext);
}

export function LegalPage({
  docs,
  support,
  children,
}: {
  docs: Record<Lang, Doc>;
  support?: { whatsapp: string; email: string };
  /** محتوى إضافي أسفل الوثيقة — نموذج الحذف يستعمله. */
  children?: React.ReactNode;
}) {
  const [lang, setLang] = useState<Lang>('ar');
  const doc = docs[lang];
  const dir = LANGS.find((l) => l.code === lang)?.dir ?? 'rtl';

  return (
    <LegalLangContext.Provider value={lang}>
    <div className={styles.page} dir={dir} lang={lang}>
      <div className={styles.bar}>
        <div className={styles.barInner}>
          {/* الاسم كما في متجر Google Play — المراجع يطابقه بصفحة التطبيق (content.ts → IDENTITY) */}
          <Link href="/" className={styles.home}>
            {IDENTITY.appName}
          </Link>
          <div className={styles.langs}>
            {LANGS.map((option) => (
              <button
                key={option.code}
                type="button"
                className={styles.lang}
                data-active={option.code === lang}
                onClick={() => setLang(option.code)}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className={styles.wrap}>
        <h1 className={styles.title}>{doc.title}</h1>
        <p className={styles.updated}>{doc.updated}</p>

        <div className={styles.lead}>{doc.lead}</div>

        {doc.sections.map((section) => (
          <section className={styles.section} key={section.h}>
            <h2 className={styles.h2}>{section.h}</h2>
            <div className={styles.body}>
              {section.p.map((paragraph) => (
                <p key={paragraph}>{paragraph}</p>
              ))}
            </div>
            {section.list ? (
              <ul className={styles.list}>
                {section.list.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : null}
          </section>
        ))}

        {children}

        <div className={styles.contact}>
          <p>{doc.contact}</p>
          {support?.email ? (
            <p>
              ✉️ <a href={`mailto:${support.email}`}>{support.email}</a>
            </p>
          ) : null}
          {support?.whatsapp ? (
            <p>
              💬{' '}
              <a
                href={`https://wa.me/${support.whatsapp.replace(/\D/g, '')}`}
                target="_blank"
                rel="noreferrer"
              >
                {support.whatsapp}
              </a>
            </p>
          ) : null}
        </div>
      </div>
    </div>
    </LegalLangContext.Provider>
  );
}
