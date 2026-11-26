import { CareArt } from "@/components/CareArt";
import Link from "next/link";
import { LoginPanel } from "@/components/LoginPanel";
import { btnPrimary, btnSecondary } from "@/components/ui";

export function ClinicHome() {
  return <div className="min-h-screen">
    <a href="#clinic-home" className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:bg-panel focus:p-3">Skip to content</a>
    <header className="border-b border-line">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-4 md:px-8">
        <Link href="/" className="font-serif text-xl leading-tight sm:text-2xl">Terra Family Clinic</Link>
        <a href="#sign-in" className={btnSecondary}>Go to sign in</a>
      </div>
    </header>
    <main id="clinic-home" className="mx-auto max-w-6xl px-5 md:px-8">
      <section className="grid items-center gap-8 py-10 md:grid-cols-[1.2fr_1fr] md:gap-14 md:py-12">
        <div>
          <h1 className="max-w-xl font-serif text-[clamp(2.5rem,5vw,4.5rem)] leading-[1.06] tracking-[-0.03em]">Your clinic.<br />A little more connected.</h1>
          <p className="mt-5 max-w-lg text-sm leading-7 text-muted">Welcome to Terra Family Clinic. Plan your visits, understand your records and keep the next step in view.</p>
          <a href="#sign-in" className={`${btnPrimary} mt-6`}>Open your workspace</a>
        </div>
        <div className="hidden md:block"><CareArt /></div>
      </section>
      <section aria-label="Clinic information" className="grid gap-5 border-y border-line py-6 text-sm sm:grid-cols-3 sm:gap-8">
        <div><h2 className="font-medium">Clinic hours</h2><p className="mt-2 leading-6 text-muted">Mon–Fri 08:00–18:00<br />Sat 09:00–13:00 · Sunday closed</p></div>
        <div><h2 className="font-medium">Your visit</h2><p className="mt-2 leading-6 text-muted">30-minute appointments<br />Review and confirm before booking</p></div>
        <div><h2 className="font-medium">Care services</h2><p className="mt-2 leading-6 text-muted">Family medicine, pediatrics, dermatology, cardiology, physiotherapy and women’s health.</p></div>
      </section>
      <section id="sign-in" aria-label="Workspace sign-in" className="grid scroll-mt-6 items-start gap-8 py-10 md:grid-cols-[0.9fr_1.1fr] md:gap-14 md:py-12">
        <div>
          <h2 className="font-serif text-3xl tracking-[-0.02em]">One place for the next step.</h2>
          <dl className="mt-6 divide-y divide-line text-sm">
            <div className="py-4"><dt className="font-semibold">Patient</dt><dd className="mt-2 leading-6 text-muted">Open records, ask about written instructions and manage appointments.</dd></div>
            <div className="py-4"><dt className="font-semibold">Receptionist</dt><dd className="mt-2 leading-6 text-muted">Coordinate appointments and view current notes shared by the clinic.</dd></div>
            <div className="py-4"><dt className="font-semibold">Owner</dt><dd className="mt-2 leading-6 text-muted">Review clinic activity, patient records and follow-up work.</dd></div>
          </dl>
        </div>
        <LoginPanel />
      </section>
    </main>
    <footer className="border-t border-line px-5 py-5 text-center text-xs leading-6 text-muted">Terra Family Clinic · Your workspace opens after sign-in.</footer>
  </div>;
}
