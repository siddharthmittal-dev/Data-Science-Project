"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { type ApiError, getMe, SESSION_EXPIRED_EVENT, toApiError, type User } from "@/lib/api";

export type AuthState =
  | { status: "loading" }
  | { status: "anon"; reason?: "expired" }
  | { status: "error"; error: ApiError }
  | { status: "authed"; user: User };

interface AuthContextValue {
  state: AuthState;
  setUser: (user: User | null) => void;
  retry: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    function expireSession() {
      setState((current) => current.status === "authed" ? { status: "anon", reason: "expired" } : current);
    }
    window.addEventListener(SESSION_EXPIRED_EVENT, expireSession);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, expireSession);
  }, []);

  useEffect(() => {
    let active = true;
    getMe().then(
      (user) => {
        if (active) setState({ status: "authed", user });
      },
      (err: unknown) => {
        if (!active) return;
        const error = toApiError(err);
        setState(error.status === 401 ? { status: "anon" } : { status: "error", error });
      },
    );
    return () => {
      active = false;
    };
  }, [attempt]);

  const setUser = useCallback((user: User | null) => {
    setState(user ? { status: "authed", user } : { status: "anon" });
  }, []);

  const retry = useCallback(() => {
    setState({ status: "loading" });
    setAttempt((n) => n + 1);
  }, []);

  const value = useMemo(() => ({ state, setUser, retry }), [state, setUser, retry]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
