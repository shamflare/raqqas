import AsyncStorage from '@react-native-async-storage/async-storage';
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import { api, cache } from '../api/client';
import type { Lang, Tokens, User } from '../api/types';
import { STORAGE } from '../config';

type LoginPayload = { phone: string; password: string };
type RegisterPayload = {
  name: string;
  phone: string;
  password: string;
  whatsapp_number?: string;
  language?: Lang;
};

type AuthValue = {
  user: User | null;
  ready: boolean;
  isAuthenticated: boolean;
  login: (payload: LoginPayload) => Promise<User>;
  register: (payload: RegisterPayload) => Promise<User>;
  logout: () => Promise<void>;
  updateProfile: (patch: Partial<Pick<User, 'name' | 'whatsapp_number' | 'language'>>) => Promise<User>;
  /**
   * يتبنّى جلسة صكّها الخادم خارج login/register — استعادة كلمة المرور.
   *
   * لا نعيد المستخدم إلى شاشة الدخول بعد أن أثبت ملكيته لرقمه قبل ثوانٍ
   * وكتب كلمة مروره الجديدة: الخادم أعطانا رموزًا، فنستعملها.
   */
  adoptSession: (user: User, tokens: Tokens) => Promise<void>;

  /**
   * بوابة تسجيل الدخول.
   *
   * إن كان مسجَّلًا يُنفَّذ الإجراء فورًا. وإن لم يكن، نحفظ الإجراء ونفتح شاشة
   * الدخول — وبعد نجاحه **يُنفَّذ الإجراء تلقائيًا**. أي أن من ضغط «تواصل عبر
   * واتساب» يجد واتساب مفتوحًا بعد الدخول، ولا يُرمى في الصفحة الرئيسية.
   */
  requireAuth: (reason: AuthReason, action: () => void) => void;
  /** يستدعيها المُلاح ليعرف أن عليه فتح شاشة الدخول. */
  onAuthRequested: (handler: (reason: AuthReason) => void) => () => void;
  pendingReason: AuthReason | null;
};

export type AuthReason = 'contact' | 'add' | 'favorites' | 'account' | 'block';

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const [pendingReason, setPendingReason] = useState<AuthReason | null>(null);

  const pendingAction = useRef<(() => void) | null>(null);
  const requestHandlers = useRef<((reason: AuthReason) => void)[]>([]);

  // ---------------------------------------------------------------- الإقلاع

  useEffect(() => {
    (async () => {
      const tokens = await api.loadTokens();
      const cached = await AsyncStorage.getItem(STORAGE.user);
      if (cached) {
        try {
          setUser(JSON.parse(cached) as User);
        } catch {
          /* تجاهل */
        }
      }
      setReady(true);

      // تحديث صامت للملف الشخصي — قد تكون الحالة تغيّرت (إيقاف مثلًا)
      if (tokens) {
        try {
          const fresh = await api.get<User>('/auth/me');
          setUser(fresh);
          await AsyncStorage.setItem(STORAGE.user, JSON.stringify(fresh));
        } catch {
          /* بلا إنترنت — نبقى على النسخة المحفوظة */
        }
      }
    })();
  }, []);

  const clearSession = useCallback(async () => {
    await api.setTokens(null);
    await AsyncStorage.removeItem(STORAGE.user);
    await cache.clear();
    setUser(null);
  }, []);

  // انتهت صلاحية الجلسة نهائيًا (فشل التجديد) — نخرج بهدوء
  useEffect(() => api.onUnauthorized(() => void clearSession()), [clearSession]);

  // ---------------------------------------------------------------- الإجراءات

  const persist = useCallback(async (nextUser: User, tokens?: Tokens) => {
    if (tokens) await api.setTokens(tokens);
    await AsyncStorage.setItem(STORAGE.user, JSON.stringify(nextUser));
    setUser(nextUser);
  }, []);

  const runPendingAction = useCallback(() => {
    const action = pendingAction.current;
    pendingAction.current = null;
    setPendingReason(null);
    if (action) setTimeout(action, 350); // بعد إغلاق شاشة الدخول
  }, []);

  const login = useCallback(
    async ({ phone, password }: LoginPayload) => {
      const data = await api.post<{ user: User; tokens: Tokens }>('/auth/login', {
        phone,
        password,
      });
      await persist(data.user, data.tokens);
      runPendingAction();
      return data.user;
    },
    [persist, runPendingAction],
  );

  const register = useCallback(
    async (payload: RegisterPayload) => {
      const data = await api.post<{ user: User; tokens: Tokens }>('/auth/register', payload);
      await persist(data.user, data.tokens);
      runPendingAction();
      return data.user;
    },
    [persist, runPendingAction],
  );

  const adoptSession = useCallback(
    async (nextUser: User, tokens: Tokens) => {
      await persist(nextUser, tokens);
      runPendingAction();
    },
    [persist, runPendingAction],
  );

  const logout = useCallback(async () => {
    try {
      await api.post('/auth/logout', {});
    } catch {
      /* الخروج ينجح محليًا حتى لو تعذّر إخبار الخادم */
    }
    await clearSession();
  }, [clearSession]);

  const updateProfile = useCallback(
    async (patch: Partial<Pick<User, 'name' | 'whatsapp_number' | 'language'>>) => {
      const updated = await api.patch<User>('/auth/me', patch);
      await persist(updated);
      return updated;
    },
    [persist],
  );

  const requireAuth = useCallback(
    (reason: AuthReason, action: () => void) => {
      if (user) {
        action();
        return;
      }
      pendingAction.current = action;
      setPendingReason(reason);
      requestHandlers.current.forEach((handler) => handler(reason));
    },
    [user],
  );

  const onAuthRequested = useCallback((handler: (reason: AuthReason) => void) => {
    requestHandlers.current.push(handler);
    return () => {
      requestHandlers.current = requestHandlers.current.filter((h) => h !== handler);
    };
  }, []);

  const value = useMemo<AuthValue>(
    () => ({
      user,
      ready,
      isAuthenticated: user !== null,
      login,
      register,
      logout,
      updateProfile,
      adoptSession,
      requireAuth,
      onAuthRequested,
      pendingReason,
    }),
    [user, ready, login, register, logout, updateProfile, adoptSession, requireAuth,
     onAuthRequested, pendingReason],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth يجب أن يُستخدم داخل AuthProvider');
  return context;
}
