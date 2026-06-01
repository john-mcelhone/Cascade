"use client";

import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { Search, ChevronRight } from "lucide-react";
import { Logo } from "./logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { ExperienceSwitcher } from "./experience-switcher";
import { UserMenu } from "./user-menu";
import { useUIStore } from "@/lib/stores/ui-store";
import { useProject } from "@/lib/api/hooks";

/**
 * Top bar — 44 px tall.
 * Layout: [Logo] · [project crumb (if in /projects/[id]/...)] · [⌘K] · [Theme] · [User]
 */
export function TopBar() {
  const params = useParams<{ id?: string }>();
  const pathname = usePathname();
  const setPaletteOpen = useUIStore((s) => s.setPaletteOpen);
  const projectId = params?.id;

  return (
    <header className="glass sticky top-0 z-40 flex h-topbar shrink-0 items-center gap-2.5 border-b border-border-subtle px-3">
      <Link
        href="/"
        className="rounded-md px-1 py-0.5 -mx-1 transition-opacity hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus"
      >
        <Logo />
      </Link>

      {projectId ? (
        <>
          <ChevronRight className="h-3 w-3 text-text-muted/50" />
          <ProjectCrumb id={projectId} />
        </>
      ) : pathname?.startsWith("/projects") ? (
        <>
          <ChevronRight className="h-3 w-3 text-text-muted/50" />
          <span className="text-sm text-text-muted">Projects</span>
        </>
      ) : null}

      <div className="ml-auto flex items-center gap-1.5">
        <button
          type="button"
          onClick={() => setPaletteOpen(true)}
          aria-label="Search and run commands"
          className="group flex h-7 items-center gap-2 rounded-md border border-border-subtle bg-surface-subtle/60 pl-2 pr-1.5 text-text-muted transition-colors hover:border-border-default hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus"
        >
          <Search className="h-3.5 w-3.5" />
          <span className="hidden text-xs sm:inline">Search or jump to…</span>
          <kbd className="hidden rounded border border-border-subtle bg-surface px-1 font-mono text-[10px] sm:inline-block">
            ⌘K
          </kbd>
        </button>
        <ExperienceSwitcher />
        <div className="mx-0.5 hidden h-5 w-px bg-border-subtle sm:block" />
        <ThemeToggle />
        <UserMenu />
      </div>
    </header>
  );
}

/** Renders the project name from the mock client, suspended without throwing. */
function ProjectCrumb({ id }: { id: string }) {
  const { data, isLoading } = useProject(id);
  return (
    <Link
      href={`/projects/${id}`}
      className="text-sm font-medium text-text hover:underline underline-offset-4"
    >
      {isLoading ? "…" : data?.name ?? id}
    </Link>
  );
}
