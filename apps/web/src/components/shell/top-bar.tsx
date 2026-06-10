"use client";

import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { Search } from "lucide-react";
import { Logo } from "./logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { ExperienceSwitcher } from "./experience-switcher";
import { UserMenu } from "./user-menu";
import { useUIStore } from "@/lib/stores/ui-store";
import { useProject } from "@/lib/api/hooks";

/**
 * Top bar — 40 px command bar.
 * Layout: [Logo] / [context path] · [⌘K command field] · [Experience] · [Theme] · [User]
 * The context path reads like a console locator: PROJECTS / <NAME>.
 */
export function TopBar() {
  const params = useParams<{ id?: string }>();
  const pathname = usePathname();
  const setPaletteOpen = useUIStore((s) => s.setPaletteOpen);
  const projectId = params?.id;

  return (
    <header className="sticky top-0 z-40 flex h-topbar shrink-0 items-center gap-3 border-b border-border-subtle bg-surface px-3">
      <Link
        href="/"
        className="rounded-sm px-1 py-0.5 -mx-1 transition-opacity hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus"
      >
        <Logo />
      </Link>

      {projectId ? (
        <>
          <PathDivider />
          <Link
            href="/projects"
            className="micro-label transition-colors hover:text-text"
          >
            Projects
          </Link>
          <PathDivider />
          <ProjectCrumb id={projectId} />
        </>
      ) : pathname?.startsWith("/projects") ? (
        <>
          <PathDivider />
          <span className="micro-label text-text-subtle">Projects</span>
        </>
      ) : null}

      <div className="ml-auto flex items-center gap-1.5">
        <button
          type="button"
          onClick={() => setPaletteOpen(true)}
          aria-label="Search and run commands"
          className="group flex h-7 w-56 items-center gap-2 rounded-sm border border-border-subtle bg-surface-subtle pl-2 pr-1.5 text-text-muted transition-colors hover:border-border-default hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus max-sm:w-auto"
        >
          <Search className="h-3.5 w-3.5 shrink-0" />
          <span className="hidden flex-1 text-left text-xs sm:inline">
            Jump or run a command
          </span>
          <kbd className="hidden rounded-sm border border-border-subtle bg-surface px-1 font-mono text-[10px] text-text-muted sm:inline-block">
            ⌘K
          </kbd>
        </button>
        <ExperienceSwitcher />
        <div className="mx-0.5 hidden h-4 w-px bg-border-subtle sm:block" />
        <ThemeToggle />
        <UserMenu />
      </div>
    </header>
  );
}

function PathDivider() {
  return (
    <span aria-hidden className="select-none text-xs text-border-strong">
      /
    </span>
  );
}

/** Renders the project name from the mock client, suspended without throwing. */
function ProjectCrumb({ id }: { id: string }) {
  const { data, isLoading } = useProject(id);
  return (
    <Link
      href={`/projects/${id}`}
      className="micro-label !text-text transition-colors hover:!text-brand-text"
    >
      {isLoading ? "…" : data?.name ?? id}
    </Link>
  );
}
