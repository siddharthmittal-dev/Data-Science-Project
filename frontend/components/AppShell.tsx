"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { useAuth } from "@/lib/auth";
import { logout, type Role, toApiError } from "@/lib/api";
import { ErrorState, Skeleton, btnSecondary } from "@/components/ui";
import { ClinicHome } from "@/components/ClinicHome";

const ROLE_LABEL: Record<Role, string> = {
  patient: "Patient",
  receptionist: "Receptionist",
  admin: "Owner",
};

const NAV = [
  { href: "/", label: "Overview", staffOnly: false },
  { href: "/doctors", label: "Doctors", staffOnly: false },
  { href: "/appointments", label: "Appointments", staffOnly: false },
  { href: "/assistant", label: "Assistant & records", staffOnly: false },
  { href: "/insights", label: "Insights", staffOnly: true },
  { href: "/retention", label: "Patient follow-up", staffOnly: true, adminOnly: true },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { state, setUser, retry } = useAuth();
  const [signOutError, setSignOutError] = useState<string | null>(null);

  const isLogin = pathname === "/login";
  const anonymous = state.status === "anon";
  const publicHome = pathname === "/" && state.status !== "authed";

  useEffect(() => {
    if (anonymous && !isLogin && !publicHome) router.replace("/login#sign-in");
  }, [anonymous, isLogin, publicHome, router]);

  if (isLogin) return <>{children}</>;
  if (publicHome) return <ClinicHome />;

  if (state.status === "loading" || anonymous) {
    return (
      <div className="mx-auto max-w-[1400px] px-5 py-10">
        <Skeleton lines={4} />
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className="mx-auto max-w-[1400px] px-5 py-10">
        <ErrorState
          title="Terra Family Clinic could not reach the server"
          message={state.error.message}
          onRetry={retry}
        />
      </div>
    );
  }

  const { user } = state;
  const isStaff = user.role !== "patient";

  async function switchRole() {
    setSignOutError(null);
    try {
      await logout();
    } catch (err) {
      setSignOutError(toApiError(err).message);
      return;
    }
    setUser(null);
    router.replace("/login");
  }

  return (
    <div className="min-h-screen">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:bg-panel focus:px-4 focus:py-2"
      >
        Skip to content
      </a>
      <header className="border-b border-line bg-bg">
        <div className="mx-auto flex max-w-[1400px] flex-wrap items-center justify-between gap-x-6 gap-y-3 px-5 pt-4 md:px-[5%]">
          <Link href="/" className="font-serif text-2xl text-ink">
            Terra Family Clinic
          </Link>
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <span className="font-medium">{user.name}</span>
            <span className="rounded-[3px] bg-soft px-2 py-1 text-xs font-semibold text-accent">
              {ROLE_LABEL[user.role]}
            </span>
            <button type="button" onClick={switchRole} className={`${btnSecondary} min-h-11`}>
              Sign out
            </button>
          </div>
          {signOutError && (
            <p role="alert" className="w-full text-sm text-danger">
              {signOutError}
            </p>
          )}
          <nav
            aria-label="Main navigation"
            className="-mx-5 flex w-full gap-1 overflow-x-auto px-5 md:mx-0 md:w-auto md:px-0"
          >
            {NAV.filter((item) => (!item.staffOnly || isStaff) && (!item.adminOnly || user.role === "admin")).map((item) => {
              const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={`inline-flex min-h-11 items-center whitespace-nowrap border-b-2 px-3 text-sm ${
                    active
                      ? "border-accent font-medium text-accent"
                      : "border-transparent text-muted hover:text-ink"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>
      <main id="main" tabIndex={-1} className="mx-auto max-w-[1400px] px-5 py-10 md:px-[5%]">
        <p className="mb-5 text-xs leading-6 text-muted">Mon–Fri 08:00–18:00 · Sat 09:00–13:00 · Sunday closed</p>
        {children}
      </main>
    </div>
  );
}
