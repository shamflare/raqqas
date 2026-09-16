import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { NavigationContainer, useNavigation, type Theme as NavTheme } from '@react-navigation/native';
import {
  createNativeStackNavigator,
  type NativeStackNavigationProp,
} from '@react-navigation/native-stack';
import React, { useEffect, useMemo } from 'react';

import { BottomNav } from '../components/BottomNav';
import { useI18n } from '../i18n';
import { AccountScreen } from '../screens/AccountScreen';
import { AddListingScreen } from '../screens/AddListingScreen';
import { AuthScreen } from '../screens/AuthScreen';
import { BlockedScreen } from '../screens/BlockedScreen';
import { CategoriesScreen } from '../screens/CategoriesScreen';
import { DeleteAccountScreen } from '../screens/DeleteAccountScreen';
import { EditListingScreen } from '../screens/EditListingScreen';
import { EditProfileScreen } from '../screens/EditProfileScreen';
import { FavoritesScreen } from '../screens/FavoritesScreen';
import { ForgotPasswordScreen } from '../screens/ForgotPasswordScreen';
import { HomeScreen } from '../screens/HomeScreen';
import { ListingScreen } from '../screens/ListingScreen';
import { MyListingsScreen } from '../screens/MyListingsScreen';
import { NotificationsScreen } from '../screens/NotificationsScreen';
import { SearchScreen } from '../screens/SearchScreen';
import { useAppConfig } from '../state/AppConfigContext';
import { useAuth } from '../state/AuthContext';
import { useTheme } from '../theme/ThemeProvider';
import type { RootStackParamList, TabParamList } from './types';

const Stack = createNativeStackNavigator<RootStackParamList>();
const Tab = createBottomTabNavigator<TabParamList>();

function Tabs() {
  const { t: text } = useI18n();
  const { config } = useAppConfig();
  const { requireAuth } = useAuth();
  const navigation = useNavigation();

  return (
    <Tab.Navigator
      tabBar={(props) => <BottomNav {...props} />}
      screenOptions={{ headerShown: false }}
    >
      <Tab.Screen
        name="HomeTab"
        component={HomeScreen as never}
        options={{ title: text.nav.home, tabBarIcon: '🏠' } as never}
      />
      <Tab.Screen
        name="CategoriesTab"
        component={CategoriesScreen}
        options={{ title: text.nav.categories, tabBarIcon: '📂' } as never}
      />
      <Tab.Screen
        name="AddTab"
        component={EmptyTab}
        options={{ title: text.nav.add } as never}
        listeners={{
          // زر «أضف إعلان» ليس تبويبًا بل شاشة فوق كل شيء،
          // ويحتاج تسجيلًا (قرار 17) — فنعترض الضغطة هنا.
          tabPress: (event) => {
            event.preventDefault();
            requireAuth('add', () => navigation.navigate('Add' as never));
          },
        }}
      />
      <Tab.Screen
        name="FavoritesTab"
        component={FavoritesScreen}
        options={
          {
            title: config.features.chat_enabled ? text.nav.messages : text.nav.favorites,
            tabBarIcon: config.features.chat_enabled ? '💬' : '❤',
          } as never
        }
      />
      <Tab.Screen
        name="AccountTab"
        component={AccountScreen}
        options={{ title: text.nav.account, tabBarIcon: '👤' } as never}
      />
    </Tab.Navigator>
  );
}

/** لا يُعرض أبدًا — تبويب «أضف إعلان» يُعترَض قبل الوصول إليه. */
function EmptyTab() {
  return null;
}

export function RootNavigator() {
  const t = useTheme();
  const { isRTL } = useI18n();

  const navTheme = useMemo<NavTheme>(
    () => ({
      dark: t.isDark,
      colors: {
        primary: t.colors.brand,
        background: t.colors.bg,
        card: t.colors.surface,
        text: t.colors.ink,
        border: t.colors.line,
        notification: t.colors.danger,
      },
      fonts: {
        regular: { fontFamily: 'Cairo_400Regular', fontWeight: '400' },
        medium: { fontFamily: 'Cairo_600SemiBold', fontWeight: '600' },
        bold: { fontFamily: 'Cairo_700Bold', fontWeight: '700' },
        heavy: { fontFamily: 'Cairo_900Black', fontWeight: '900' },
      },
    }),
    [t],
  );

  return (
    <NavigationContainer theme={navTheme} direction={isRTL ? 'rtl' : 'ltr'}>
      <AuthGateListener />
      <Stack.Navigator screenOptions={{ headerShown: false }}>
        <Stack.Screen name="Tabs" component={Tabs} />
        <Stack.Screen name="Listing" component={ListingScreen} />
        <Stack.Screen name="Search" component={SearchScreen} />
        <Stack.Screen name="Add" component={AddListingScreen} />
        <Stack.Screen name="EditListing" component={EditListingScreen} />
        <Stack.Screen name="MyListings" component={MyListingsScreen} />
        <Stack.Screen name="Notifications" component={NotificationsScreen} />
        <Stack.Screen name="EditProfile" component={EditProfileScreen} />
        <Stack.Screen name="Blocked" component={BlockedScreen} />
        <Stack.Screen name="DeleteAccount" component={DeleteAccountScreen} />
        <Stack.Screen
          name="Auth"
          component={AuthScreen}
          options={{ presentation: 'modal', animation: 'slide_from_bottom' }}
        />
        <Stack.Screen
          name="ForgotPassword"
          component={ForgotPasswordScreen}
          options={{ presentation: 'modal', animation: 'slide_from_bottom' }}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
}

/**
 * يفتح شاشة الدخول حين يطلبها أي مكان في التطبيق.
 *
 * السبب في وضعه هنا: الشاشات لا يجب أن تعرف كيف يُفتح التسجيل — تقول
 * requireAuth وتنتهي، وبعد نجاح الدخول يُستأنف إجراؤها تلقائيًا.
 */
function AuthGateListener() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { onAuthRequested } = useAuth();

  useEffect(
    () => onAuthRequested((reason) => navigation.navigate('Auth', { reason })),
    [navigation, onAuthRequested],
  );

  return null;
}
