"use client";

import { usePathname } from "next/navigation";
import { TopBar } from "./top-bar";
import { LeftRail } from "./left-rail";
import { BottomBar } from "./bottom-bar";
import { CommandPalette } from "@/components/command-palette";

/**
 * Top-level shell. Hides the app chrome on the marketing landing page (/),
 * /pricing, and the docs landing tree (/docs/...) — those surfaces want
 * full-bleed pages.
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() ?? "/";
  const isMarketing =
    pathname === "/" ||
    pathname.startsWith("/pricing") ||
    pathname.startsWith("/terms") ||
    pathname.startsWith("/privacy");
  const isDocs = pathname.startsWith("/docs");
  const isLearn = pathname.startsWith("/learn");

  if (isMarketing) {
    return (
      <div className="flex min-h-screen flex-col">
        {children}
        <CommandPalette />
      </div>
    );
  }

  // Docs uses a slim chrome (top bar only, no left rail or bottom bar).
  if (isDocs) {
    return (
      <div className="flex min-h-screen flex-col">
        <TopBar />
        <main className="flex flex-1 overflow-hidden">{children}</main>
        <CommandPalette />
      </div>
    );
  }

  // /learn has its own chapter sidebar; defer to the learn layout for chrome.
  if (isLearn) {
    return (
      <div className="flex min-h-screen flex-col">
        <TopBar />
        <main className="flex flex-1 overflow-hidden">{children}</main>
        <CommandPalette />
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col">
      <TopBar />
      <div className="flex flex-1 overflow-hidden">
        <LeftRail />
        <main className="flex-1 overflow-auto scrollbar-subtle">{children}</main>
      </div>
      <BottomBar />
      <CommandPalette />
    </div>
  );
}
