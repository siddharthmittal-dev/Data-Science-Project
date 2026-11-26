"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { ClinicHome } from "@/components/ClinicHome";

export default function LoginPage() {
  const { state } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (state.status === "authed") router.replace("/");
  }, [state.status, router]);
  return <ClinicHome />;
}
