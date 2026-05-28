"use client";

import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { Command, ChevronRight } from "lucide-react";
import { Logo } from "./logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { UserMenu } from "./user-menu";
import { Button } from "@/components/ui/button";
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
    <header className="flex h-topbar shrink-0 items-center gap-3 border-b border-border-subtle bg-surface px-3">
      <Link
        href="/"
        className="rounded-sm px-1 py-0.5 -mx-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus"
      >
        <Logo />
      </Link>

      {projectId ? (
        <>
          <ChevronRight className="h-3 w-3 text-text-muted/60" />
          <ProjectCrumb id={projectId} />
        </>
      ) : pathname?.startsWith("/projects") ? (
        <>
          <ChevronRight className="h-3 w-3 text-text-muted/60" />
          <span className="text-sm text-text-muted">Projects</span>
        </>
      ) : null}

      <div className="ml-auto flex items-center gap-1">
        <Button
          variant="outline"
          size="sm"
          className="h-7 gap-2 px-2"
          onClick={() => setPaletteOpen(true)}
          aria-label="Open command palette"
        >
          <Command className="h-3 w-3" />
          <span className="text-xs text-text-muted">Search</span>
          <kbd className="ml-2 hidden rounded-sm border border-border-subtle bg-surface-subtle px-1 font-mono text-[10px] text-text-muted sm:inline-block">
            ⌘K
          </kbd>
        </Button>
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
