import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import React, { useState } from 'react';
import { Platform, View } from 'react-native';

import { api, ApiError } from '../api/client';
import { KeyboardScroll } from '../components/KeyboardScroll';
import { Field, Input } from '../components/Field';
import { SubHeader } from '../components/Header';
import {
  PhoneInput,
  fromE164,
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

type Props = NativeStackScreenProps<RootStackParamList, 'EditProfile'>;

export function EditProfileScreen({ navigation }: Props) {
  const t = useTheme();
  const { t: text } = useI18n();
  const { user, updateProfile } = useAuth();
  const toast = useToast();

  const [name, setName] = useState(user?.name ?? '');
  const [whatsapp, setWhatsapp] = useState<PhoneValue>(() =>
    // الرقم المحفوظ دوليّ — نفكّكه إلى دولة ورقم محلي ليرى المستخدم علمه
    fromE164(user?.whatsapp_number || user?.phone),
  );
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const saveProfile = async () => {
    setBusy(true);
    setError(null);
    try {
      await updateProfile({ name: name.trim(), whatsapp_number: toE164(whatsapp) });
      toast.show(text.account.saved);
      navigation.goBack();
    } catch (caught) {
      if (caught instanceof ApiError) setError(caught);
      else toast.show(text.errors.generic);
    } finally {
      setBusy(false);
    }
  };

  const savePassword = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.post('/auth/password', { current_password: current, new_password: next });
      setCurrent('');
      setNext('');
      toast.show(text.account.saved);
    } catch (caught) {
      if (caught instanceof ApiError) setError(caught);
      else toast.show(text.errors.generic);
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: t.colors.bg }}>
      <SubHeader title={text.account.editProfile} onBack={() => navigation.goBack()} />

      <KeyboardScroll contentContainerStyle={{ padding: 14, paddingBottom: 40 }}>
        {error && !error.fields ? (
          <View style={{ marginBottom: 16 }}>
            <Notice tone="danger">{error.message}</Notice>
          </View>
        ) : null}

        <Field label={text.account.name} required error={error?.fieldError('name')}>
          <Input value={name} onChangeText={setName} />
        </Field>

        <Field label={text.auth.phone}>
          <Input value={user?.phone_display ?? ''} editable={false} ltr />
        </Field>

        <Field
          label={text.account.whatsappNumber}
          required
          hint={text.auth.whatsappRequiredHint}
          error={error?.fieldError('whatsapp_number')}
        >
          <PhoneInput
            value={whatsapp}
            onChange={setWhatsapp}
            invalid={Boolean(error?.fieldError('whatsapp_number'))}
          />
        </Field>

        <Button
          title={text.common.save}
          block
          loading={busy}
          // الحقل إجباري الآن: حفظه فارغًا يقطع قناة استعادة كلمة المرور
          disabled={!looksComplete(whatsapp) || name.trim().length < 2}
          onPress={saveProfile}
        />

        <View style={{ height: 1, backgroundColor: t.colors.line, marginVertical: 26 }} />

        <Txt size={15} weight={800} align="start" style={{ marginBottom: 14 }}>
          🔒 {text.account.changePassword}
        </Txt>

        <Field label={text.account.currentPassword} error={error?.fieldError('current_password')}>
          <Input value={current} onChangeText={setCurrent} password="current" ltr />
        </Field>

        <Field
          label={text.account.newPassword}
          hint={text.auth.passwordHint}
          error={error?.fieldError('new_password')}
        >
          <Input value={next} onChangeText={setNext} password="new" ltr />
        </Field>

        <Button
          title={text.account.changePassword}
          variant="ghost"
          block
          loading={busy}
          disabled={current.length < 6 || next.length < 6}
          onPress={savePassword}
        />
      </KeyboardScroll>
    </View>
  );
}
