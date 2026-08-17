import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { authApi, clearToken, getToken, Me, setToken, User } from "./lib/api";

interface AuthCtx {
  user: User | null;
  permissions: string[];
  roleLabel: string;
  featureFlags: Record<string, boolean>;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  can: (perm: string) => boolean;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [permissions, setPermissions] = useState<string[]>([]);
  const [roleLabel, setRoleLabel] = useState("");
  const [featureFlags, setFeatureFlags] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!getToken()) {
      setLoading(false);
      return;
    }
    authApi
      .me()
      .then((me: Me) => {
        setUser(me.user);
        setPermissions(me.permissions);
        setRoleLabel(me.role_label);
        setFeatureFlags(me.feature_flags);
      })
      .catch(() => clearToken())
      .finally(() => setLoading(false));
  }, []);

  const login = async (email: string, password: string) => {
    const res = await authApi.login(email, password);
    setToken(res.access_token);
    setUser(res.user);
    const me = await authApi.me();
    setPermissions(me.permissions);
    setRoleLabel(me.role_label);
    setFeatureFlags(me.feature_flags);
  };

  const logout = () => {
    clearToken();
    setUser(null);
    setPermissions([]);
  };

  const value = useMemo<AuthCtx>(
    () => ({
      user,
      permissions,
      roleLabel,
      featureFlags,
      loading,
      login,
      logout,
      can: (p: string) => permissions.includes(p),
    }),
    [user, permissions, roleLabel, featureFlags, loading]
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

/** Redirects unauthenticated users to /login. */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-ink-950">
        <div className="text-center">
          <div className="mx-auto h-10 w-10 animate-spin rounded-full border-2 border-brand/30 border-t-brand" />
          <p className="mt-4 text-sm text-slate-500">Securing your session…</p>
        </div>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  return <>{children}</>;
}

/** Guards a route by a single required permission. */
export function RequirePerm({ perm, children }: { perm: string; children: React.ReactNode }) {
  const { can, user } = useAuth();
  if (user && !can(perm)) {
    return (
      <div className="flex h-[60vh] flex-col items-center justify-center gap-3 text-center">
        <div className="text-4xl">🔒</div>
        <h2 className="text-lg font-semibold text-slate-200">Access restricted</h2>
        <p className="max-w-sm text-sm text-slate-500">
          Your role does not grant the <code className="rounded bg-white/10 px-1.5 py-0.5 font-mono text-xs text-brand">{perm}</code> permission.
          Contact a platform administrator to request access.
        </p>
      </div>
    );
  }
  return <>{children}</>;
}
