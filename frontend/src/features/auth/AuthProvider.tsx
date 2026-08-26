import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api, setAccessToken, setUnauthorizedHandler, type User } from "../../app/api";

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  login(email: string, password: string): Promise<void>;
  register(email: string, password: string): Promise<void>;
  logout(): void;
}

const AuthContext = createContext<AuthContextValue | null>(null);
const storageKey = "rfp-lens.access-token";

export function AuthProvider({ children }: { children: React.ReactNode }): React.ReactElement {
  const [token, setToken] = useState<string | null>(() => sessionStorage.getItem(storageKey));
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(Boolean(token));

  const logout = useCallback(() => {
    setAccessToken(null);
    sessionStorage.removeItem(storageKey);
    setToken(null);
    setUser(null);
    setIsLoading(false);
  }, []);

  const saveToken = useCallback((nextToken: string) => {
    setAccessToken(nextToken);
    sessionStorage.setItem(storageKey, nextToken);
    setToken(nextToken);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(logout);
    return () => setUnauthorizedHandler(null);
  }, [logout]);

  useEffect(() => {
    if (!token) return;
    setAccessToken(token);
    api
      .me()
      .then(setUser)
      .catch(logout)
      .finally(() => setIsLoading(false));
  }, [logout, token]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isLoading,
      async login(email, password) {
        const response = await api.login(email, password);
        saveToken(response.access_token);
        const currentUser = await api.me();
        setUser(currentUser);
        setIsLoading(false);
      },
      async register(email, password) {
        await api.register(email, password);
        const response = await api.login(email, password);
        saveToken(response.access_token);
        const currentUser = await api.me();
        setUser(currentUser);
        setIsLoading(false);
      },
      logout,
    }),
    [isLoading, logout, saveToken, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
