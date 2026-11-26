import { useCallback, useEffect, useState } from "react";
import { type ApiError, toApiError } from "@/lib/api";

export type LoadState<T> =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; data: T };

// Loads once on mount. `refresh` reloads and keeps the current data on screen;
// `retry` shows the loading state again. `load` must be a stable reference.
export function useLoader<T>(load: () => Promise<T>) {
  const [state, setState] = useState<LoadState<T>>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    load().then(
      (data) => {
        if (active) setState({ status: "ready", data });
      },
      (err: unknown) => {
        if (active) setState({ status: "error", error: toApiError(err) });
      },
    );
    return () => {
      active = false;
    };
  }, [load, attempt]);

  const refresh = useCallback(() => setAttempt((n) => n + 1), []);
  const retry = useCallback(() => {
    setState({ status: "loading" });
    setAttempt((n) => n + 1);
  }, []);

  return { state, refresh, retry };
}
