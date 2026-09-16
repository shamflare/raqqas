import type { PhoneValue } from '../components/PhoneInput';
import type { AuthReason } from '../state/AuthContext';

export type RootStackParamList = {
  Tabs: undefined;
  Listing: { id: number };
  Search:
    | { q?: string; category?: string; categoryName?: string; featured?: boolean; openFilters?: boolean }
    | undefined;
  Add: undefined;
  EditListing: { id: number };
  Auth: { reason?: AuthReason } | undefined;
  ForgotPassword: { phone?: PhoneValue } | undefined;
  MyListings: undefined;
  Notifications: undefined;
  EditProfile: undefined;
  Blocked: undefined;
  DeleteAccount: undefined;
};

export type TabParamList = {
  HomeTab: undefined;
  CategoriesTab: undefined;
  AddTab: undefined;
  FavoritesTab: undefined;
  AccountTab: undefined;
};

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace ReactNavigation {
    interface RootParamList extends RootStackParamList {}
  }
}
