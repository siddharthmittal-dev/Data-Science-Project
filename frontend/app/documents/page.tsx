"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

export default function DocumentsPage() {
  const router = useRouter();
  useEffect(() => { router.replace("/assistant"); }, [router]);
  return <p className="text-sm leading-7">Opening your assistant and records. <Link href="/assistant" className="underline">Continue to assistant</Link></p>;
}
