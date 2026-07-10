"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { client, logout as apiLogout, type UserPublic } from "@gulp/api-client";

type AuthValue = {
  user: UserPublic | null;
  setUser: (u: UserPublic | null) => void;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({
  initialUser = null,
  children,
}: {
  initialUser?: UserPublic | null;
  children: React.ReactNode;
}) {
  const [user, setUser] = useState<UserPublic | null>(initialUser);
  const router = useRouter();

  // On a 401 from any api-client call, drop to the login screen.
  useEffect(() => {
    client.use({
      onResponse({ response }) {
        if (
          response.status === 401 &&
          !window.location.pathname.startsWith("/login")
        ) {
          setUser(null);
          router.replace("/login");
        }
        return response;
      },
    });
  }, [router]);

  async function signOut() {
    await apiLogout();
    setUser(null);
    router.replace("/login");
  }

  return (
    <AuthContext.Provider value={{ user, setUser, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
