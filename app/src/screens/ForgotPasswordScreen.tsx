import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import React, { useEffect, useRef, useState } from 'react';
import { Pressable, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { api, ApiError } from '../api/client';
import type { Tokens, User } from '../api/types';
import { Field, Input } from '../components/Field';
import { KeyboardScroll } from '../components/KeyboardScroll';
import {
  PhoneInput,
  emptyPhone,
  looksComplete,
  toE164,
  type PhoneValue,
} from '../components/PhoneInput';
import { useToast } from '../components/Toast';
import { Button, Notice, Txt } from '../components/ui';
import { useI18n } from '../i18n';
import type { RootStackParamList } from '../navigation/types';
import { useAuth } from '../state/AuthContext';
import { useTheme } from '../theme/ThemeProvider';

type Props = NativeStackScreenProps<RootStackParamList, 'ForgotPassword'>;

type Step = 'phone' | 'code' | 'password';

/** ثانية قبل السماح بطلب رمز جديد — تمنع الضغط المتكرّر على زرّ لم يصل أثره بعد. */
const RESEND_AFTER = 60;

/**
 * استعادة كلمة المرور — ثلاث خطوات في شاشة واحدة.
 *
 * شاشة واحدة لا ثلاث شاشات متتابعة: المستخدم يرى أين هو ممّا بدأ، والرجوع
 * خطوةً لا يخرجه من العملية كلها. والرقم المقنَّع يبقى أمامه في الخطوة ②
 * ليطمئن أن الرمز ذهب إلى رقمه هو.
 */
export function ForgotPasswordScreen({ navigation, route }: Props) {
  const t = useTheme();
  const { t: text, tp } = useI18n();
  const { adoptSession } = useAuth();
  const toast = useToast();
  const insets = useSafeAreaInsets();

  const [step, setStep] = useState<Step>('phone');
  const [phone, setPhone] = useState<PhoneValue>(
    route.params?.phone ?? emptyPhone(),
  );
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');
  const [ticket, setTicket] = useState('');
  const [masked, setMasked] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cooldown, setCooldown] = useState(0);

  // عدّاد إعادة الإرسال — مؤقّت واحد يعيش مع الشاشة لا مع كل رسم
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => {
    if (cooldown <= 0) return;
    timer.current = setInterval(() => setCooldown((value) => Math.max(0, value - 1)), 1000);
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [cooldown > 0]); // eslint-disable-line react-hooks/exhaustive-deps

  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : text.errors.generic);
    } finally {
      setBusy(false);
    }
  };

  // ------------------------------------------------------------------ الخطوات

  const sendCode = () =>
    run(async () => {
      const result = await api.post<{ masked: string }>('/auth/password/forgot', {
        phone: toE164(phone),
      });
      setMasked(result.masked);
      setCode('');
      setCooldown(RESEND_AFTER);
      setStep('code');
    });

  const verifyCode = () =>
    run(async () => {
      const result = await api.post<{ ticket: string }>('/auth/password/verify', {
        phone: toE164(phone),
        code,
      });
      setTicket(result.ticket);
      setStep('password');
    });

  const savePassword = () =>
    run(async () => {
      const result = await api.post<{ user: User; tokens: Tokens }>(
        '/auth/password/reset',
        { ticket, new_password: password },
      );
      // الدخول فوري: من أثبت ملكيته للرقم قبل ثوانٍ لا يُعاد إلى شاشة الدخول
      // ليكتب ما كتبه للتوّ.
      await adoptSession(result.user, result.tokens);
      toast.show(text.auth.passwordChanged);
      navigation.goBack();
    });

  const canSubmit =
    step === 'phone'
      ? looksComplete(phone)
      : step === 'code'
        ? code.replace(/\D/g, '').length >= 4
        : password.length >= 6;

  const submit = step === 'phone' ? sendCode : step === 'code' ? verifyCode : savePassword;

  return (
    <View style={{ flex: 1, backgroundColor: t.colors.bg }}>
      <KeyboardScroll contentContainerStyle={{ flexGrow: 1 }}>
        <View
          style={{
            backgroundColor: t.colors.brand,
            paddingTop: insets.top + 24,
            paddingBottom: 30,
            paddingHorizontal: 20,
            alignItems: 'center',
          }}
        >
          <Pressable
            onPress={() => navigation.goBack()}
            hitSlop={10}
            style={{ position: 'absolute', top: insets.top + 10, [t.isRTL ? 'right' : 'left']: 14 }}
          >
            <Txt size={22} color="#FFFFFF">
              ✕
            </Txt>
          </Pressable>

          <Txt size={34}>🔑</Txt>
          <Txt size={22} weight={900} color="#FFFFFF" align="center" style={{ marginTop: 8 }}>
            {text.auth.forgotTitle}
          </Txt>
          <Txt
            size={13}
            weight={600}
            color="rgba(255,255,255,0.85)"
            align="center"
            style={{ marginTop: 3 }}
          >
            {step === 'phone'
              ? text.auth.forgotSubtitle
              : step === 'code'
                ? tp(text.auth.codeSentTo, { phone: masked })
                : text.auth.chooseNewPassword}
          </Txt>
        </View>

        <View style={{ padding: 16, maxWidth: 440, width: '100%', alignSelf: 'center' }}>
          <Steps current={step} />

          {error ? (
            <View style={{ marginBottom: 16 }}>
              <Notice tone="danger">{error}</Notice>
            </View>
          ) : null}

          {step === 'phone' ? (
            <Field label={text.auth.phone} required hint={text.auth.forgotPhoneHint}>
              <PhoneInput value={phone} onChange={setPhone} autoFocus />
            </Field>
          ) : null}

          {step === 'code' ? (
            <>
              <Field label={text.auth.code} required hint={text.auth.codeHint}>
                <Input
                  value={code}
                  onChangeText={(value) => setCode(value.replace(/\D/g, '').slice(0, 6))}
                  placeholder="------"
                  keyboardType="number-pad"
                  autoComplete="sms-otp"
                  maxLength={6}
                  autoFocus
                  ltr
                  style={{ textAlign: 'center', letterSpacing: 8, fontSize: t.fs(22) }}
                />
              </Field>

              <Pressable
                onPress={cooldown > 0 || busy ? undefined : sendCode}
                style={{ marginBottom: 18 }}
              >
                <Txt
                  size={13}
                  weight={700}
                  align="center"
                  color={cooldown > 0 ? t.colors.ink3 : t.colors.brandText}
                >
                  {cooldown > 0
                    ? tp(text.auth.resendIn, { seconds: formatSeconds(cooldown) })
                    : text.auth.resendCode}
                </Txt>
              </Pressable>
            </>
          ) : null}

          {step === 'password' ? (
            <Field label={text.auth.newPassword} required hint={text.auth.passwordHint}>
              <Input value={password} onChangeText={setPassword} password="new" autoFocus ltr />
            </Field>
          ) : null}

          <Button
            title={
              step === 'phone'
                ? text.auth.sendCode
                : step === 'code'
                  ? text.auth.verifyCode
                  : text.auth.savePassword
            }
            size="lg"
            block
            loading={busy}
            disabled={!canSubmit}
            onPress={submit}
          />

          {step !== 'phone' ? (
            <Pressable
              onPress={() => {
                setError(null);
                setStep(step === 'password' ? 'code' : 'phone');
              }}
              style={{ marginTop: 16 }}
            >
              <Txt size={13} weight={700} color={t.colors.ink3} align="center">
                {text.auth.back}
              </Txt>
            </Pressable>
          ) : null}
        </View>
      </KeyboardScroll>
    </View>
  );
}

function formatSeconds(total: number): string {
  const minutes = Math.floor(total / 60);
  return `${minutes}:${String(total % 60).padStart(2, '0')}`;
}

/** ثلاث نقاط تقول للمستخدم أين هو — بلا نصّ يُترجم ثلاث مرات. */
function Steps({ current }: { current: Step }) {
  const t = useTheme();
  const order: Step[] = ['phone', 'code', 'password'];
  const index = order.indexOf(current);
  return (
    <View style={[t.row, { gap: 6, justifyContent: 'center', marginBottom: 20 }]}>
      {order.map((step, position) => (
        <View
          key={step}
          style={{
            height: 4,
            width: position === index ? 26 : 14,
            borderRadius: 2,
            backgroundColor: position <= index ? t.colors.brand : t.colors.line,
          }}
        />
      ))}
    </View>
  );
}
