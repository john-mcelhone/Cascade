"use client";

import { useState } from "react";
import { ThemeProvider } from "next-themes";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import { TooltipProvider } from "@/components/ui/tooltip";
import { HealthProbe } from "@/components/shell/health-probe";

/**
 * Global client-side providers. Order matters:
 *  1. ThemeProvider sets [data-theme] before anything else paints.
 *  2. QueryClientProvider owns the server-state cache.
 *  3. NuqsAdapter binds URL state to nuqs hooks.
 *  4. TooltipProvider gives every shadcn tooltip a default delay.
 *  5. Sonner Toaster sits last so toasts overlay everything.
 */
export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            refetchOnWindowFocus: false,
            retry: 1,
          },
        },
      }),
  );

  return (
    <ThemeProvider
      attribute="data-theme"
      // Console (dark) is the product's default identity; light is the
      // "blueprint paper" companion, and System remains available.
      defaultTheme="dark"
      enableSystem
      disableTransitionOnChange
    >
      <QueryClientProvider client={queryClient}>
        <NuqsAdapter>
          <TooltipProvider delayDuration={300} skipDelayDuration={100}>
            <HealthProbe />
            {children}
            <Toaster
              richColors
              position="bottom-right"
              toastOptions={{
                classNames: {
                  toast:
                    "bg-surface text-text border border-border-subtle shadow-z2",
                },
              }}
            />
          </TooltipProvider>
        </NuqsAdapter>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
