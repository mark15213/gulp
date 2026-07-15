"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { login, register } from "@gulp/api-client";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/Button";
import styles from "./AuthForm.module.css";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const { setUser } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isLogin = mode === "login";
  const cta = isLogin ? "Log in" : "Create account";

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      // schema.gen.ts marks `locale` non-optional (openapi-typescript's
      // defaultNonNullable on the Pydantic default) — pass it explicitly.
      const user = isLogin
        ? await login({ email, password })
        : await register({ email, password, locale: "en", invite_code: inviteCode });
      setUser(user);
      router.replace("/");
    } catch {
      setError(
        isLogin ? "Invalid email or password." : "Could not create the account.",
      );
      setBusy(false);
    }
  }

  return (
    <form className={styles.form} onSubmit={onSubmit}>
      <h1 className="t-title-l">{isLogin ? "Welcome back" : "Create your account"}</h1>
      <label className={styles.field}>
        <span className="t-label">Email</span>
        <input
          className={styles.input}
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
      </label>
      <label className={styles.field}>
        <span className="t-label">Password</span>
        <input
          className={styles.input}
          type="password"
          autoComplete={isLogin ? "current-password" : "new-password"}
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
      </label>
      {!isLogin && (
        <label className={styles.field}>
          <span className="t-label">Invite code</span>
          <input
            className={styles.input}
            type="text"
            value={inviteCode}
            onChange={(e) => setInviteCode(e.target.value)}
            required
          />
        </label>
      )}
      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}
      <Button
        type="submit"
        variant="primary"
        size="lg"
        disabled={busy || !email || !password}
      >
        {busy ? "…" : cta}
      </Button>
      <p className={styles.alt}>
        {isLogin ? (
          <>
            No account? <Link href="/register">Create one</Link>
          </>
        ) : (
          <>
            Already have an account? <Link href="/login">Log in</Link>
          </>
        )}
      </p>
    </form>
  );
}
