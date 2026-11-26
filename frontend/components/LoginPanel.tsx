"use client";

import { useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { login, toApiError } from "@/lib/api";
import { btnPrimary, btnSecondary, headingClass, panelClass } from "@/components/ui";

export const LOGIN_ACCOUNTS = [
  { label: "Patient", email: "patient@terra.test" },
  { label: "Receptionist", email: "receptionist@terra.test" },
  { label: "Owner", email: "owner@terra.test" },
] as const;

export function LoginPanel() {
  const router = useRouter();
  const { state, setUser } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const passwordInput = useRef<HTMLInputElement>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError("");
    try {
      const user = await login(email, password);
      setPassword("");
      setUser(user);
      router.replace("/");
      window.scrollTo(0, 0);
    } catch (err) { setError(toApiError(err).message); }
    finally { setPending(false); }
  }

  const inputClass = "mt-2 min-h-11 w-full rounded-[3px] border border-line bg-panel px-3 text-sm";
  return <div className={panelClass}>
    <h2 className={headingClass}>Sign in to Terra Family Clinic</h2>
    <p className="mt-3 text-sm leading-6 text-muted">Choose your workspace to fill the email address, then enter your password.</p>
    {state.status === "anon" && state.reason === "expired" && <p role="status" className="mt-4 text-sm text-accent">Your session has expired. Sign in again to continue.</p>}
    <form onSubmit={submit} className="mt-5 space-y-5">
      <fieldset disabled={pending}>
        <legend className="mb-2 text-sm font-medium">Workspace</legend>
        <div className="flex flex-wrap gap-2">{LOGIN_ACCOUNTS.map(account => <button key={account.email} type="button"
          aria-pressed={email === account.email} className={`${btnSecondary} ${email === account.email ? "border-accent bg-soft text-accent" : ""}`}
          onClick={() => { setEmail(account.email); setPassword(""); setError(""); passwordInput.current?.focus(); }}>
          {account.label}
        </button>)}</div>
      </fieldset>
      <label className="block text-sm">Email address<input type="email" className={inputClass} value={email} onChange={e => setEmail(e.target.value)} autoComplete="username" maxLength={320} required disabled={pending} /></label>
      <label className="block text-sm">Password<input ref={passwordInput} type="password" className={inputClass} value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password" minLength={12} maxLength={128} required disabled={pending} /></label>
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      <button type="submit" className={`${btnPrimary} w-full`} disabled={pending}>{pending ? "Signing in..." : "Sign in"}</button>
    </form>
  </div>;
}
