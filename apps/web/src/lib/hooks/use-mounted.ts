"use client";

import { useEffect, useState } from "react";

/**
 * Returns true only after the first client render. Use to gate UI that depends
 * on persisted (localStorage-hydrated) state so SSR and the first client paint
 * agree, then upgrade once we know the real value.
 */
export function useMounted(): boolean {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  return mounted;
}
