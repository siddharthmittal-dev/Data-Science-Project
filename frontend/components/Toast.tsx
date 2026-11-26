"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const TOAST_MS = 4000;

export function useToast() {
  const [message, setMessage] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, []);

  const show = useCallback((text: string) => {
    if (timer.current) clearTimeout(timer.current);
    setMessage(text);
    timer.current = setTimeout(() => setMessage(null), TOAST_MS);
  }, []);

  return { message, show };
}

// Always mounted so screen readers announce each new message.
export function LiveRegion({ message }: { message: string | null }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="pointer-events-none fixed inset-x-0 bottom-6 z-50 flex justify-center px-4"
    >
      {message && (
        <div className="pointer-events-auto max-w-md rounded-[3px] bg-ink px-5 py-3 text-sm text-panel shadow-lg">
          {message}
        </div>
      )}
    </div>
  );
}
