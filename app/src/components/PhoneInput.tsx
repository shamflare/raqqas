import React, { useMemo, useState } from 'react';
import { Pressable, ScrollView, TextInput, View } from 'react-native';

import { COUNTRIES, DEFAULT_COUNTRY, SUGGESTED_COUNTRIES, countryOf, flagOf, type Country } from '../data/countries';
import { useI18n } from '../i18n';
import { useTheme } from '../theme/ThemeProvider';
import { Input } from './Field';
import { Sheet } from './Sheet';
import { Divider, Txt } from './ui';

/**
 * حقل هاتف: زرّ دولة بالعلم ورمز النداء، ثم الرقم المحلي.
 *
 * ما يخرج منه إلى الخادم **رقم دولي كامل** (`+963944567890`) لا نصّ خام. حقل
 * نصّي عارٍ كان يجبر الخادم على تخمين الدولة من طول الرقم — وهو تخمين ينجح في
 * سوريا وتركيا ويسقط في كل ما عداهما.
 */

export type PhoneValue = {
  /** حرفا الدولة — يُحفظ ليعود المستخدم إلى آخر اختيار */
  iso: string;
  /** ما كتبه المستخدم بيده، بلا رمز الدولة */
  national: string;
};

export const emptyPhone = (iso: string = DEFAULT_COUNTRY): PhoneValue => ({ iso, national: '' });

/** الصيغة الدولية التي تُرسل إلى الخادم — أو `''` إن كان الحقل فارغًا. */
export function toE164(value: PhoneValue): string {
  const country = countryOf(value.iso);
  // الصفر بادئة محلية لا مكان لها بعد رمز الدولة: 0944… تصير +963944…
  const digits = value.national.replace(/\D/g, '').replace(/^0+/, '');
  if (!country || !digits) return '';
  return `+${country.dial}${digits}`;
}

/** يبني قيمة الحقل من رقم دولي محفوظ — لشاشة تعديل الملف الشخصي. */
export function fromE164(e164: string | null | undefined): PhoneValue {
  const digits = (e164 ?? '').replace(/\D/g, '');
  if (!digits) return emptyPhone();

  // الأطول أولًا: رمز لبنان «961» يبدأ بـ«96» ورمز اليمن «967» كذلك، فلو
  // طابقنا الأقصر لأخذنا الدولة الخطأ وأظهرنا للمستخدم علمًا ليس علمه.
  const match = [...COUNTRIES]
    .sort((a, b) => b.dial.length - a.dial.length)
    .find((country) => digits.startsWith(country.dial));

  if (!match) return { iso: DEFAULT_COUNTRY, national: digits };
  return { iso: match.iso, national: digits.slice(match.dial.length) };
}

/** هل يبدو الرقم مكتملًا؟ فحص شكلي للزرّ فقط — الخادم هو المرجع. */
export function looksComplete(value: PhoneValue): boolean {
  return value.national.replace(/\D/g, '').replace(/^0+/, '').length >= 6;
}

export function PhoneInput({
  value,
  onChange,
  invalid,
  autoFocus,
}: {
  value: PhoneValue;
  onChange: (value: PhoneValue) => void;
  invalid?: boolean;
  autoFocus?: boolean;
}) {
  const t = useTheme();
  const { t: text, lang } = useI18n();
  const [picking, setPicking] = useState(false);

  const country = countryOf(value.iso) ?? countryOf(DEFAULT_COUNTRY)!;

  return (
    <>
      {/* `t.row` ينقلب مع اللغة، لكن الرقم نفسه يبقى LTR دائمًا — فالزرّ
          يقع في بداية السطر بالمعنى الذي يفهمه قارئ كل لغة. */}
      <View style={[t.row, { gap: 8, alignItems: 'stretch' }]}>
        <Pressable
          onPress={() => setPicking(true)}
          accessibilityRole="button"
          accessibilityLabel={country.names[lang] ?? country.names.en}
          style={({ pressed }) => [
            t.row,
            {
              alignItems: 'center',
              gap: 5,
              paddingHorizontal: t.sp(11),
              backgroundColor: t.colors.surface,
              borderWidth: 1.5,
              borderColor: invalid ? t.colors.danger : t.colors.line,
              borderRadius: t.radius.md,
              opacity: pressed ? 0.7 : 1,
            },
          ]}
        >
          <Txt size={17}>{flagOf(country.iso)}</Txt>
          <Txt size={14} weight={700} style={{ writingDirection: 'ltr' }}>
            {`+${country.dial}`}
          </Txt>
          <Txt size={10} muted>
            ▾
          </Txt>
        </Pressable>

        <View style={{ flex: 1 }}>
          <Input
            value={value.national}
            onChangeText={(national) => onChange({ ...value, national })}
            placeholder={country.example || '000 000 000'}
            keyboardType="phone-pad"
            autoComplete="tel-national"
            autoFocus={autoFocus}
            invalid={invalid}
            ltr
          />
        </View>
      </View>

      <CountrySheet
        visible={picking}
        selected={value.iso}
        onClose={() => setPicking(false)}
        onPick={(iso) => {
          onChange({ ...value, iso });
          setPicking(false);
        }}
      />
    </>
  );
}

/* ------------------------------------------------------------ قائمة الدول */

function CountrySheet({
  visible,
  selected,
  onClose,
  onPick,
}: {
  visible: boolean;
  selected: string;
  onClose: () => void;
  onPick: (iso: string) => void;
}) {
  const t = useTheme();
  const { t: text, lang } = useI18n();
  const [query, setQuery] = useState('');

  const { suggested, rest } = useMemo(() => {
    const collator = new Intl.Collator(lang);
    const named = (country: Country) => country.names[lang] ?? country.names.en;

    const needle = query.trim().toLowerCase().replace(/^\+/, '');
    const matches = (country: Country) => {
      if (!needle) return true;
      // الرقم يطابق رمز النداء، والحروف تطابق الاسم بأي لغة من الثلاث —
      // فمن يكتب «49» يجد ألمانيا، ومن يكتب «Alman» أو «ألما» يجدها أيضًا.
      if (/^\d+$/.test(needle)) return country.dial.startsWith(needle);
      return Object.values(country.names).some((name) =>
        name.toLowerCase().includes(needle),
      );
    };

    const all = COUNTRIES.filter(matches);
    return {
      suggested: query
        ? []
        : (SUGGESTED_COUNTRIES.map((iso) => COUNTRIES.find((c) => c.iso === iso)).filter(
            Boolean,
          ) as Country[]),
      rest: all.sort((a, b) => collator.compare(named(a), named(b))),
    };
  }, [query, lang]);

  return (
    <Sheet visible={visible} title={text.auth.chooseCountry} onClose={onClose}>
      <TextInput
        value={query}
        onChangeText={setQuery}
        placeholder={text.auth.searchCountry}
        placeholderTextColor={t.colors.ink3}
        autoCorrect={false}
        style={[
          t.font(400),
          {
            backgroundColor: t.colors.bg,
            borderWidth: 1.5,
            borderColor: t.colors.line,
            borderRadius: t.radius.md,
            paddingHorizontal: t.sp(14),
            paddingVertical: t.sp(10),
            fontSize: t.fs(14.5),
            color: t.colors.ink,
            textAlign: t.isRTL ? 'right' : 'left',
            marginBottom: 12,
          },
        ]}
      />

      {/* ارتفاع ثابت: القائمة داخل ScrollView النافذة، ولولاه لامتدّت 245 صفًا
          فخرج حقل البحث من أعلى الشاشة وضاع سبب وجوده. */}
      <ScrollView
        style={{ maxHeight: 360 }}
        keyboardShouldPersistTaps="handled"
        nestedScrollEnabled
      >
        {suggested.length ? (
          <>
            <Txt size={11.5} weight={700} muted align="start" style={{ marginBottom: 4 }}>
              {text.auth.suggestedCountries}
            </Txt>
            {suggested.map((country) => (
              <CountryRow
                key={`top-${country.iso}`}
                country={country}
                selected={country.iso === selected}
                onPress={() => onPick(country.iso)}
              />
            ))}
            <Divider style={{ marginVertical: 10 }} />
          </>
        ) : null}

        {rest.length === 0 ? (
          <Txt size={13} muted align="center" style={{ paddingVertical: 20 }}>
            {text.auth.noCountryFound}
          </Txt>
        ) : (
          rest.map((country) => (
            <CountryRow
              key={country.iso}
              country={country}
              selected={country.iso === selected}
              onPress={() => onPick(country.iso)}
            />
          ))
        )}
      </ScrollView>
    </Sheet>
  );
}

function CountryRow({
  country,
  selected,
  onPress,
}: {
  country: Country;
  selected: boolean;
  onPress: () => void;
}) {
  const t = useTheme();
  const { lang } = useI18n();
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        t.row,
        {
          alignItems: 'center',
          gap: 11,
          paddingVertical: 11,
          paddingHorizontal: 6,
          borderRadius: t.radius.sm,
          backgroundColor: selected ? t.colors.brand50 : 'transparent',
          opacity: pressed ? 0.6 : 1,
        },
      ]}
    >
      <Txt size={19}>{flagOf(country.iso)}</Txt>
      <Txt size={14} weight={selected ? 800 : 600} style={{ flex: 1 }} align="start" numberOfLines={1}>
        {country.names[lang] ?? country.names.en}
      </Txt>
      <Txt size={13} weight={700} muted style={{ writingDirection: 'ltr' }}>
        {`+${country.dial}`}
      </Txt>
    </Pressable>
  );
}
