"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useRouter } from "next/navigation";

import {
  ApiError,
  authApi,
  clearAuth,
  getAuth,
  storeAuth,
  type AuthTokens,
  type User,
} from "@/lib/api";

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  loginWithGoogle: (idToken: string) => Promise<void>;
  register: (
    email: string,
    password: string,
    firstName?: string,
    lastName?: string,
  ) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    const stored = getAuth();
    if (!stored) {
      setUser(null);
      return;
    }

    try {
      const me = await authApi.me();
      setUser(me);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401 && stored.refresh) {
        try {
          const tokens = await authApi.refresh(stored.refresh);
          storeAuth(tokens);
          setUser(tokens.user);
          return;
        } catch {
          clearAuth();
          setUser(null);
          return;
        }
      }
      clearAuth();
      setUser(null);
    }
  }, []);

  useEffect(() => {
    const init = async () => {
      const stored = getAuth();
      if (stored?.user) {
        setUser(stored.user);
      }
      await refreshUser();
      setIsLoading(false);
    };
    void init();
  }, [refreshUser]);

  const persist = useCallback((tokens: AuthTokens) => {
    storeAuth(tokens);
    setUser(tokens.user);
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const tokens = await authApi.login({ email, password });
      persist(tokens);
      router.push("/");
    },
    [persist, router],
  );

  const loginWithGoogle = useCallback(
    async (idToken: string) => {
      const tokens = await authApi.google({ id_token: idToken });
      persist(tokens);
      router.push("/");
    },
    [persist, router],
  );

  const register = useCallback(
    async (
      email: string,
      password: string,
      firstName = "",
      lastName = "",
    ) => {
      const tokens = await authApi.register({
        email,
        password,
        first_name: firstName,
        last_name: lastName,
      });
      persist(tokens);
      router.push("/");
    },
    [persist, router],
  );

  const logout = useCallback(() => {
    clearAuth();
    setUser(null);
    router.push("/login");
  }, [router]);

  const value = useMemo(
    () => ({
      user,
      isLoading,
      isAuthenticated: Boolean(user),
      login,
      loginWithGoogle,
      register,
      logout,
      refreshUser,
    }),
    [user, isLoading, login, loginWithGoogle, register, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
