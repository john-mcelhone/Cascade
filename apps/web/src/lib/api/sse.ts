"use client";

import { useEffect, useRef } from "react";
import { getApiBaseUrl } from "./client";
import { apiBase, getJob, type ServerJobEvent } from "./flowpath";
import type { SseProgressEvent } from "./types";

/**
 * Subscribe to a Server-Sent-Events stream and invoke `onEvent` for each
 * decoded JSON event. Auto-reconnects with capped exponential back-off.
 *
 * `url` is the full URL including any query string. We use a ref-backed
 * callback so the consumer can swap handlers without re-establishing the
 * connection. The hook is a no-op when `url` is null.
 *
 * When `EventSource` is not available (e.g. SSR; older browsers; some
 * test envs) the hook silently does nothing. The caller should drive the
 * UI via polling in that case (see `useJobPolling`).
 */
export function useEventStream<T = ServerJobEvent>(
  url: string | null,
  onEvent: (event: T) => void,
  opts?: { onError?: (err: unknown) => void; onOpen?: () => void },
): void {
  const onEventRef = useRef(onEvent);
  const onErrorRef = useRef(opts?.onError);
  const onOpenRef = useRef(opts?.onOpen);

  // Keep the latest callbacks without retriggering the connection.
  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);
  useEffect(() => {
    onErrorRef.current = opts?.onError;
    onOpenRef.current = opts?.onOpen;
  });

  useEffect(() => {
    if (!url || typeof window === "undefined" || !("EventSource" in window)) {
      return;
    }

    let cancelled = false;
    let es: EventSource | null = null;
    let backoff = 250;
    let reconnectTimer: number | null = null;

    const connect = () => {
      if (cancelled) return;
      try {
        es = new EventSource(url);
      } catch (err) {
        onErrorRef.current?.(err);
        return;
      }
      es.onopen = () => {
        backoff = 250;
        onOpenRef.current?.();
      };
      es.onmessage = (ev) => {
        try {
          const parsed = JSON.parse(ev.data) as T;
          onEventRef.current(parsed);
        } catch (err) {
          onErrorRef.current?.(err);
        }
      };
      es.onerror = (err) => {
        onErrorRef.current?.(err);
        es?.close();
        es = null;
        if (cancelled) return;
        backoff = Math.min(backoff * 2, 5000);
        reconnectTimer = window.setTimeout(connect, backoff);
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
      es?.close();
    };
  }, [url]);
}

/**
 * Poll `/api/jobs/:id` every `intervalMs` until the job reports a
 * terminal status (`done` / `failed` / `cancelled`) or the hook unmounts.
 *
 * Used as the graceful fallback when SSE is unavailable. The hook gives
 * the caller the same `data` object each tick so the front-end can show
 * progress without depending on event streaming.
 */
export function useJobPolling(
  jobId: string | null,
  onProgress: (event: ServerJobEvent) => void,
  intervalMs = 500,
): void {
  const onProgressRef = useRef(onProgress);
  useEffect(() => {
    onProgressRef.current = onProgress;
  }, [onProgress]);

  useEffect(() => {
    if (!jobId) return;
    let cancelled = false;
    let timer: number | null = null;

    const tick = async () => {
      if (cancelled || !jobId) return;
      try {
        const job = await getJob(jobId);
        const event: ServerJobEvent = {
          job_id: job.id,
          status: job.status,
          progress: job.progress,
          message: job.message ?? "",
        };
        onProgressRef.current(event);
        if (
          job.status === "done" ||
          job.status === "failed" ||
          job.status === "cancelled"
        ) {
          return;
        }
      } catch {
        // Transient — keep polling.
      }
      timer = window.setTimeout(tick, intervalMs);
    };
    tick();

    return () => {
      cancelled = true;
      if (timer !== null) window.clearTimeout(timer);
    };
  }, [jobId, intervalMs]);
}

/** Convenience: SSE URL for a given job. */
export function jobEventsUrl(jobId: string): string {
  return `${apiBase()}/api/jobs/${jobId}/events`;
}

/**
 * Lower-level SSE hook variant used by the Map / Rotor / Analysis pages.
 *
 * Accepts an SSE *path* (relative to the API base) or a full URL and a single
 * `onEvent` callback. The hook prepends the API base for relative paths,
 * auto-reconnects with capped backoff (250 / 500 / 1000 / 2000 ms), and
 * closes the connection on unmount or when `enabled` becomes false.
 */
export interface UseJobStreamOptions {
  enabled?: boolean;
  onEvent: (event: SseProgressEvent) => void;
  onFinal?: (event: SseProgressEvent) => void;
  onError?: (err: Event) => void;
}

export function useJobStream(
  path: string | undefined,
  options: UseJobStreamOptions,
): void {
  const { enabled = true, onEvent, onFinal, onError } = options;
  const onEventRef = useRef(onEvent);
  const onFinalRef = useRef(onFinal);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);
  useEffect(() => {
    onFinalRef.current = onFinal;
  }, [onFinal]);
  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  useEffect(() => {
    if (!enabled || !path) return;
    if (typeof window === "undefined" || !("EventSource" in window)) return;
    const url = path.startsWith("http") ? path : `${getApiBaseUrl()}${path}`;
    let attempt = 0;
    let es: EventSource | null = null;
    let timer: number | null = null;
    let cancelled = false;
    const open = () => {
      if (cancelled) return;
      es = new EventSource(url, { withCredentials: true });
      es.onopen = () => {
        attempt = 0;
      };
      es.onmessage = (raw) => {
        try {
          const data = JSON.parse(raw.data) as SseProgressEvent;
          onEventRef.current(data);
          if (data.final) {
            onFinalRef.current?.(data);
            cancelled = true;
            es?.close();
            es = null;
          }
        } catch {
          // ignore
        }
      };
      es.onerror = (err) => {
        onErrorRef.current?.(err);
        es?.close();
        es = null;
        if (cancelled) return;
        const delays = [250, 500, 1000, 2000];
        const wait = delays[Math.min(attempt, delays.length - 1)];
        attempt += 1;
        timer = window.setTimeout(open, wait);
      };
    };
    open();
    return () => {
      cancelled = true;
      if (timer !== null) window.clearTimeout(timer);
      es?.close();
      es = null;
    };
  }, [enabled, path]);
}

/** Build the API-base-relative SSE path for a job. Returns undefined for
 *  undefined jobIds so callers can pass straight to useJobStream. */
export function jobEventsPath(jobId: string | undefined): string | undefined {
  if (!jobId) return undefined;
  return `/api/jobs/${encodeURIComponent(jobId)}/events`;
}
