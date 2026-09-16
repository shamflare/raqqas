import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import React, { useState } from 'react';
import { Platform, Pressable, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { ApiError } from '../api/client';
import { KeyboardScroll } from '../components/KeyboardScroll';
import { Field, Input } from '../components/Field';
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

type Props = NativeStackScreenProps<RootStackParamList, 'Auth'>;

export function AuthScreen({ navigation, route }: Props) {
  const t = useTheme();
  const { t: text, tp, lang } = useI18n();
  const { login, register } = useAuth();
  const toast = useToast();
  const insets = useSafeAreaInsets();

  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [name, setName] = useState('');
  const [phone, setPhone] = useState<PhoneValue>(emptyPhone());
  const [password, setPassword] = useState('');
  const [whatsapp, setWhatsapp] = useState<PhoneValue>(emptyPhone());
  /**
   * هل لمس المستخدم حقل واتساب؟
   *
   * ما دام لم يلمسه، يتبع رقم الحساب حرفًا بحرف — لأن هذا هو الغالب، فلا نطلب
   * منه كتابة الرقم نفسه مرتين. وأول تعديل منه يقطع الرابط فلا نعود ندوس على
   * ما كتبه.
   */
  const [whatsappEdited, setWhatsappEdited] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const whatsappValue = whatsappEdited ? whatsapp : phone;

  const reasonText: Record<string, string> = {
    contact: text.auth.loginRequiredContact,
    add: text.auth.loginRequiredAdd,
    favorites: text.auth.loginRequiredFavorites,
    account: text.account.guestText,
    block: text.auth.loginRequiredBlock,
  };
  const reason = route.params?.reason ? reasonText[route.params.reason] : null;

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const user =
        mode === 'login'
          ? await login({ phone: toE164(phone), password })
          : await register({
              name,
              phone: toE164(phone),
              password,
              whatsapp_number: toE164(whatsappValue),
              language: lang,
            });
      toast.show(tp(text.auth.welcomeUser, { name: user.name }));
      navigation.goBack();
    } catch (caught) {
      if (caught instanceof ApiError) setError(caught);
      else toast.show(text.errors.generic);
    } finally {
      setBusy(false);
    }
  };

  const canSubmit =
    looksComplete(phone) &&
    password.length >= 6 &&
    (mode === 'login' || (name.trim().length >= 2 && looksComplete(whatsappValue)));

  return (
    <View style={{ flex: 1, backgroundColor: t.colors.bg }}>
      <KeyboardScroll contentContainerStyle={{ flexGrow: 1 }}>
        {/* الترويسة الملوّنة — .auth-hero في التصميم */}
        <View
          style={{
            backgroundColor: t.colors.brand,
            paddingTop: insets.top + 28,
            paddingBottom: 34,
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

          <View
            style={{
              width: 62,
              height: 62,
              borderRadius: 19,
              backgroundColor: '#FFFFFF',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Txt size={30} weight={900} color={t.colors.brand}>
              {text.brand.mark}
            </Txt>
          </View>
          <Txt size={25} weight={900} color="#FFFFFF" align="center" style={{ marginTop: 12 }}>
            {mode === 'login' ? text.auth.welcomeBack : text.auth.createAccount}
          </Txt>
          <Txt size={13.5} weight={600} color="rgba(255,255,255,0.85)" align="center" style={{ marginTop: 3 }}>
            {text.auth.subtitle}
          </Txt>
        </View>

        <View style={{ padding: 16, maxWidth: 440, width: '100%', alignSelf: 'center' }}>
          {reason ? (
            <View style={{ marginBottom: 18 }}>
              <Notice tone="info">{reason}</Notice>
            </View>
          ) : null}

          {/* المبدّل — .seg في التصميم */}
          <View
            style={[
              t.row,
              {
                backgroundColor: t.colors.bg,
                borderRadius: t.radius.md,
                padding: 4,
                marginBottom: 20,
              },
            ]}
          >
            {(['login', 'register'] as const).map((key) => (
              <Pressable
                key={key}
                onPress={() => {
                  setMode(key);
                  setError(null);
                }}
                style={{
                  flex: 1,
                  paddingVertical: 9,
                  borderRadius: t.radius.sm,
                  backgroundColor: mode === key ? t.colors.surface : 'transparent',
                  alignItems: 'center',
                  ...(mode === key ? t.shadow('sm') : {}),
                }}
              >
                <Txt
                  size={13.5}
                  weight={800}
                  color={mode === key ? t.colors.brandText : t.colors.ink3}
                >
                  {key === 'login' ? text.auth.login : text.auth.register}
                </Txt>
              </Pressable>
            ))}
          </View>

          {error && !error.fields ? (
            <View style={{ marginBottom: 16 }}>
              <Notice tone="danger">{error.message}</Notice>
            </View>
          ) : null}

          {mode === 'register' ? (
            <Field label={text.auth.name} required error={error?.fieldError('name')}>
              <Input
                value={name}
                onChangeText={setName}
                placeholder={text.auth.namePlaceholder}
                autoComplete="name"
              />
            </Field>
          ) : null}

          <Field
            label={text.auth.phone}
            required
            hint={text.auth.phoneHint}
            error={error?.fieldError('phone')}
          >
            <PhoneInput
              value={phone}
              onChange={setPhone}
              invalid={Boolean(error?.fieldError('phone'))}
            />
          </Field>

          <Field
            label={text.auth.password}
            required
            hint={text.auth.passwordHint}
            error={error?.fieldError('password')}
          >
            <Input
              value={password}
              onChangeText={setPassword}
              password={mode === 'login' ? 'current' : 'new'}
              ltr
            />
          </Field>

          {mode === 'login' ? (
            <Pressable
              onPress={() =>
                navigation.navigate('ForgotPassword', {
                  // نحمل ما كتبه معه: من نسي كلمته لا يُطلب منه كتابة رقمه ثانيةً
                  phone: looksComplete(phone) ? phone : undefined,
                })
              }
              hitSlop={8}
              style={{ marginTop: -6, marginBottom: 18 }}
            >
              <Txt size={13} weight={700} color={t.colors.brandText} align="end">
                {text.auth.forgotPassword}
              </Txt>
            </Pressable>
          ) : null}

          {mode === 'register' ? (
            <Field
              label={text.auth.whatsappNumber}
              required
              hint={text.auth.whatsappRequiredHint}
              error={error?.fieldError('whatsapp_number')}
            >
              <PhoneInput
                value={whatsappValue}
                onChange={(value) => {
                  setWhatsappEdited(true);
                  setWhatsapp(value);
                }}
                invalid={Boolean(error?.fieldError('whatsapp_number'))}
              />
            </Field>
          ) : null}

          <Button
            title={mode === 'login' ? text.auth.submitLogin : text.auth.submitRegister}
            size="lg"
            block
            loading={busy}
            disabled={!canSubmit}
            onPress={submit}
          />

          <Pressable onPress={() => navigation.goBack()} style={{ marginTop: 18 }}>
            <Txt size={13.5} weight={700} color={t.colors.ink3} align="center">
              {text.auth.continueAsGuest}
            </Txt>
          </Pressable>
        </View>
      </KeyboardScroll>
    </View>
  );
}
