import { z } from 'zod';

// Backend API configuration and services
// If empty, requests go to the same origin (useful with reverse-proxy on the same domain).
const BACKEND_BASE_URL = ((import.meta as any).env?.VITE_BACKEND_BASE_URL as string | undefined)?.replace(/\/+$/, '') || '';

// Token management - use ttb_token as key
export const getToken = (): string | null => {
  return localStorage.getItem('ttb_token');
};

export const setToken = (token: string): void => {
  localStorage.setItem('ttb_token', token);
};

export const removeToken = (): void => {
  localStorage.removeItem('ttb_token');
};

// Username normalization (same as server does)
export const normalizeUsername = (username: string): string => {
  return username.trim().toLowerCase().replace(/@/g, '');
};

// Validation schemas
export const usernameSchema = z
  .string()
  .min(2, 'Логин должен быть минимум 2 символа')
  .max(64, 'Логин должен быть максимум 64 символа')
  .transform(normalizeUsername)
  .refine(
    (val) => /^[a-z0-9._-]{2,64}$/.test(val),
    'Логин может содержать только латиницу (a-z), цифры, точку, дефис и подчёркивание'
  );

export const passwordSchema = z
  .string()
  .min(6, 'Пароль должен быть минимум 6 символов');

export const authSchema = z.object({
  username: usernameSchema,
  password: passwordSchema,
});

// Validation result type
type ValidationResult = 
  | { success: true; data: { username: string; password: string } }
  | { success: false; error: string };

// Validate credentials before sending
export const validateCredentials = (username: string, password: string): ValidationResult => {
  const result = authSchema.safeParse({ username, password });
  
  if (!result.success) {
    const firstError = result.error.errors[0];
    return { success: false, error: firstError.message };
  }
  
  return { success: true, data: { username: result.data.username, password: result.data.password } };
};

// API helper with better error handling
const apiRequest = async <T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> => {
  const token = getToken();
  
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  try {
    const response = await fetch(`${BACKEND_BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const detail = (errorData as any)?.detail as string | undefined;
      
      // Map server errors to user-friendly messages
      if (response.status === 401) {
        if (endpoint === '/v2/auth/login' || endpoint === '/v2/auth/register') {
          throw new Error('Неверный логин или пароль');
        }
        throw new Error(detail || 'Нужно войти в аккаунт');
      }
      if (response.status === 409) {
        throw new Error('Пользователь уже существует');
      }
      if (response.status === 400) {
        if (detail?.includes('username')) {
          throw new Error('Неверный формат логина');
        }
        if (detail?.includes('password')) {
          throw new Error('Пароль должен быть минимум 6 символов');
        }
        throw new Error(detail || 'Неверные данные');
      }
      if (response.status === 404) {
        // FastAPI default for unknown route is usually {"detail":"Not Found"}.
        // But business-logic may also use 404 (e.g. license key not found).
        if (detail && detail !== 'Not Found') {
          if (detail === 'license not found') {
            throw new Error('Ключ лицензии не найден');
          }
          throw new Error(detail);
        }
        throw new Error('Эндпоинт не найден (возможен старый backend или неверный proxy)');
      }

      if (response.status === 403) {
        throw new Error(detail || 'Доступ запрещён');
      }
      
      throw new Error(errorData.detail || errorData.message || 'Ошибка запроса');
    }

    return response.json();
  } catch (error) {
    if (error instanceof TypeError && error.message === 'Failed to fetch') {
      throw new Error('Не удалось подключиться к серверу. Проверьте интернет-соединение.');
    }
    throw error;
  }
};

// Auth types
export interface AuthResponse {
  access_token: string;
  token_type: string;
}

export interface UserProfile {
  id: string;
  username: string;
  role?: string;
  plan: string | null;
  tariff_name: string | null;
  allowed_platforms: string[];
  license_expires_at: string | null;
}

export interface CreateNotificationRequest {
  title: string;
  body: string;
  link?: string | null;
  // Legacy
  level?: 'info' | 'warning' | 'promo' | string;
  audience?: 'all' | 'users' | 'plan' | 'missing_email' | string;
  audience_value?: string | null;

  // New unified
  type?: 'system' | 'product' | 'marketing' | string;
  severity?: 'info' | 'warning' | 'promo' | string;
  in_app_enabled?: boolean;
  push_enabled?: boolean;
  targeting?: Record<string, any> | null;
  starts_at?: string | null;
  ends_at?: string | null;
  target_usernames?: string[] | null;
}

export interface CreateNotificationResponse {
  status: string;
  id: string;
}

// Auth API with validation
export const authApi = {
  register: async (username: string, password: string): Promise<AuthResponse> => {
    // Validate and normalize before sending
    const validation = validateCredentials(username, password);
    if (!validation.success) {
      throw new Error((validation as { success: false; error: string }).error);
    }
    
    const { data } = validation as { success: true; data: { username: string; password: string } };
    
    return apiRequest<AuthResponse>('/v2/auth/register', {
      method: 'POST',
      body: JSON.stringify({ 
        username: data.username, 
        password: data.password 
      }),
    });
  },

  login: async (username: string, password: string): Promise<AuthResponse> => {
    // Validate and normalize before sending
    const validation = validateCredentials(username, password);
    if (!validation.success) {
      throw new Error((validation as { success: false; error: string }).error);
    }
    
    const { data } = validation as { success: true; data: { username: string; password: string } };
    
    return apiRequest<AuthResponse>('/v2/auth/login', {
      method: 'POST',
      body: JSON.stringify({ 
        username: data.username, 
        password: data.password 
      }),
    });
  },

  getMe: () => apiRequest<UserProfile>('/v2/auth/me'),

  upgradeLicense: (licenseKey: string) =>
    apiRequest<{ success: boolean }>('/v2/auth/upgrade-license', {
      method: 'POST',
      body: JSON.stringify({ license_key: licenseKey }),
    }),
    
  // Verify token is valid
  verifyToken: async (): Promise<boolean> => {
    try {
      await apiRequest<UserProfile>('/v2/auth/me');
      return true;
    } catch {
      removeToken();
      return false;
    }
  },
};

// Plans types
export interface Plan {
  id: string;
  name: string;
  allowed_platforms: string[];
}

export interface PlansResponse {
  items: Plan[];
}

// Plans API
export const plansApi = {
  getPlans: () => apiRequest<PlansResponse>('/v2/license/plans'),
};

// Mock data for development (when backend is unavailable)
export const mockPlans: Plan[] = [
  {
    id: 'nova_streamer_one_mobile',
    name: 'NovaStreamer One (Mobile)',
    allowed_platforms: ['mobile'],
  },
  {
    id: 'nova_streamer_one_desktop',
    name: 'NovaStreamer One (Desktop)',
    allowed_platforms: ['desktop'],
  },
  {
    id: 'nova_streamer_duo',
    name: 'NovaStreamer Duo',
    allowed_platforms: ['desktop', 'mobile'],
  },
];

// Plan pricing (for UI display - actual prices from payment provider)
export const planPricing: Record<string, { price: number; currency: string; period: string }> = {
  nova_streamer_one_mobile: { price: 4.99, currency: '$', period: '/месяц' },
  nova_streamer_one_desktop: { price: 8.99, currency: '$', period: '/месяц' },
  nova_streamer_duo: { price: 14.99, currency: '$', period: '/месяц' },
};

// Plan descriptions and features
export const planDetails: Record<string, { description: string; features: string[]; available: boolean }> = {
  nova_streamer_one_mobile: {
    description: 'Идеально для мобильного стриминга',
    features: [
      'Озвучка чата',
      'Озвучка подарков',
      'Триггеры на события',
      'Вход зрителя и т.д.',
    ],
    available: true,
  },
  nova_streamer_one_desktop: {
    description: 'Полный набор для десктопа',
    features: [
      'Озвучка чата',
      'Озвучка подарков',
      'Триггеры на события',
      'Виджеты и алёрты',
    ],
    available: false,
  },
  nova_streamer_duo: {
    description: 'Максимум возможностей',
    features: [
      'Всё из Mobile + Desktop',
      'NovaBoost Tools',
      'Приоритетная поддержка',
      'Ранний доступ к фичам',
    ],
    available: false,
  },
};

// Admin API
export interface RoleItem {
  id: string;
}

export interface RolesResponse {
  items: RoleItem[];
}

export interface AdminUserItem {
  id: string;
  username: string;
  email?: string | null;
  role: string;
  created_at: string;
  tiktok_username?: string | null;
  tariff_id?: string | null;
  tariff_name?: string | null;
  license_expires_at?: string | null;
  status?: string | null;
  platform?: string | null;
  region?: string | null;
  last_login_at?: string | null;
  last_live_at?: string | null;
  last_live_tiktok_username?: string | null;
  online_now?: boolean;
  tiktok_accounts_count?: number;
  is_banned?: boolean;
  banned_at?: string | null;
  banned_reason?: string | null;
}

export interface ListUsersResponse {
  items: AdminUserItem[];
  total: number;
}

export interface SetUserRoleResponse {
  status: string;
  user_id: string;
  username: string;
  role: string;
}

export interface AdminSetUserLicenseResponse {
  status: string;
  user_id: string;
  license_key: string;
  plan: string | null;
  expires_at: string | null;
}

export interface AdminExtendUserLicenseResponse {
  status: string;
  user_id: string;
  license_key: string;
  expires_at: string | null;
}

export interface AdminRevokeUserLicenseResponse {
  status: string;
  user_id: string;
  license_key: string;
}

export interface AdminSetUserBanResponse {
  status: string;
  user_id: string;
  username: string;
  banned: boolean;
  banned_at: string | null;
  banned_reason: string | null;
}

export interface AdminDeleteUserResponse {
  status: string;
  user_id: string;
  username: string;
}

const buildQuery = (params: Record<string, string | number | undefined | null>): string => {
  const entries = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && String(v).length > 0)
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
  return entries.length ? `?${entries.join('&')}` : '';
};

export const adminApi = {
  listRoles: () => apiRequest<RolesResponse>('/v2/admin/roles'),
  createNotification: (req: CreateNotificationRequest) =>
    apiRequest<CreateNotificationResponse>('/v2/admin/notifications', {
      method: 'POST',
      body: JSON.stringify(req),
    }),
  listUsers: (
    params: {
      q?: string;
      tariff_id?: string | null;
      activity?: 'online' | 'inactive' | null;
      inactive_days?: number | null;
      platform?: 'android' | 'ios' | 'desktop' | null;
      region?: string | null;
      limit?: number;
      offset?: number;
    } = {}
  ) => {
    const qs = buildQuery({
      q: params.q?.trim() || undefined,
      tariff_id: params.tariff_id ?? undefined,
      activity: params.activity ?? undefined,
      inactive_days: params.inactive_days ?? undefined,
      platform: params.platform ?? undefined,
      region: params.region?.trim() || undefined,
      limit: params.limit ?? 50,
      offset: params.offset ?? 0,
    });
    return apiRequest<ListUsersResponse>(`/v2/admin/users${qs}`);
  },
  setUserRole: (userId: string, role: string) =>
    apiRequest<SetUserRoleResponse>(`/v2/admin/users/${encodeURIComponent(userId)}/role`, {
      method: 'PATCH',
      body: JSON.stringify({ role }),
    }),
  setUserLicense: (userId: string, plan: string | null, ttlDays: number = 30) =>
    apiRequest<AdminSetUserLicenseResponse>(`/v2/admin/users/${encodeURIComponent(userId)}/license/set`, {
      method: 'POST',
      body: JSON.stringify({ plan, ttl_days: ttlDays }),
    }),
  extendUserLicense: (userId: string, extendDays: number = 30) =>
    apiRequest<AdminExtendUserLicenseResponse>(`/v2/admin/users/${encodeURIComponent(userId)}/license/extend`, {
      method: 'POST',
      body: JSON.stringify({ extend_days: extendDays }),
    }),
  revokeUserLicense: (userId: string) =>
    apiRequest<AdminRevokeUserLicenseResponse>(`/v2/admin/users/${encodeURIComponent(userId)}/license/revoke`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),
  setUserBan: (userId: string, banned: boolean, reason?: string) =>
    apiRequest<AdminSetUserBanResponse>(`/v2/admin/users/${encodeURIComponent(userId)}/ban`, {
      method: 'POST',
      body: JSON.stringify({ banned, reason: reason?.trim() || null }),
    }),
  deleteUser: (userId: string) =>
    apiRequest<AdminDeleteUserResponse>(`/v2/admin/users/${encodeURIComponent(userId)}`, {
      method: 'DELETE',
    }),
};
