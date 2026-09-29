import type { Metadata } from 'next';

import { LegalPage } from '../legal/LegalPage';
import { PRIVACY } from '../legal/content';
import { getSupport } from '../legal/support';

export const revalidate = 3600;

export const metadata: Metadata = {
  title: 'سياسة الخصوصية — سوقنا (Souqna) · lebid hacalaye',
  description: 'سياسة خصوصية تطبيق سوقنا (com.souqraqqa.app) من المطوّر lebid hacalaye: ما نجمعه وما لا نجمعه وكيف تحذف حسابك.',
};

export default async function PrivacyPage() {
  return <LegalPage docs={PRIVACY} support={await getSupport()} />;
}
