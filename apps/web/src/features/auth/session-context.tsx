"use client";

import {
  fetchAuthSession,
  loginWithPassword,
  logoutSession,
  type AuthUser,
} from "@/data/http/auth";
import { getConfig } from "@/lib/config";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type AuthStatus = "loading" | "anonymous" | "authenticated" | "bypassed" | "disabled";

interface AuthContextValue {
  status: AuthStatus;
  user: AuthUser | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function initialStatus(): AuthStatus {
  return getConfig().apiBaseUrl ? "loading" : "disabled";
}

export function AuthSessionProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>(initialStatus);
  const [user, setUser] = useState<AuthUser | null>(null);

  const refresh = useCallback(async () => {
    const config = getConfig();
    if (!config.apiBaseUrl) {
      setUser(null);
      setStatus("disabled");
      return;
    }
    try {
      const envelope = await fetchAuthSession();
      if (envelope.data.bypass) {
        setUser(envelope.data.user);
        setStatus("bypassed");
        return;
      }
      if (envelope.data.user) {
        setUser(envelope.data.user);
        setStatus("authenticated");
        return;
      }
      setUser(null);
      setStatus("anonymous");
    } catch {
      setUser(null);
      setStatus("anonymous");
    }
  }, []);

  useEffect(() => {
    if (!getConfig().apiBaseUrl) return;
    let cancelled = false;
    void fetchAuthSession()
      .then((envelope) => {
        if (cancelled) return;
        if (envelope.data.bypass) {
          setUser(envelope.data.user);
          setStatus("bypassed");
          return;
        }
        if (envelope.data.user) {
          setUser(envelope.data.user);
          setStatus("authenticated");
          return;
        }
        setUser(null);
        setStatus("anonymous");
      })
      .catch(() => {
        if (cancelled) return;
        setUser(null);
        setStatus("anonymous");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const envelope = await loginWithPassword(email, password);
    setUser(envelope.data.user);
    setStatus("authenticated");
  }, []);

  const logout = useCallback(async () => {
    await logoutSession();
    setUser(null);
    setStatus("anonymous");
  }, []);

  const value = useMemo(
    () => ({ status, user, login, logout, refresh }),
    [status, user, login, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuthSession(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuthSession must be used within AuthSessionProvider.");
  }
  return value;
}
