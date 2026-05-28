"use client";

import { useEffect, useRef } from "react";
import { toast } from "sonner";

import { ApiError, getApiClient } from "@/lib/api/client";

/**
 * Pings `/api/health` once on mount. If the backend is unreachable we surface
 * a Sonner toast pointing the user at the make target. The probe is a no-op
 * thereafter; pages keep rendering with whatever fallback data they have.
 */
export function HealthProbe() {
  const fired = useRef(false);

  useEffect(() => {
    if (fired.current) return;
    fired.current = true;
    const api = getApiClient();
    api.health().catch((err: unknown) => {
      const isNetworkError = err instanceof ApiError && err.status === 0;
      if (isNetworkError) {
        toast.error("Cascade backend is not running.", {
          description:
            "Start it with `cd apps/api && make dev` (or `make api`) on port 8000.",
          duration: 8000,
        });
      } else {
        const msg = err instanceof Error ? err.message : String(err);
        toast.error("Cascade backend health check failed.", {
          description: msg,
          duration: 6000,
        });
      }
    });
  }, []);

  return null;
}
