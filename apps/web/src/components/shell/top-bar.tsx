"use client";

import Link from "next/link";
import { useParams, usePathname, useRouter } from "next/navigation";
import {
  BookOpen,
  Check,
  ChevronsUpDown,
  CircleHelp,
  Command,
  GraduationCap,
  History,
  LayoutGrid,
  Plus,
  Search,
} from "lucide-react";
import { CascadeMark } from "./logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { ExperienceSwitcher } from "./experience-switcher";
import { UserMenu } from "./user-menu";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useUIStore } from "@/lib/stores/ui-store";
import { useProjectDisplayName, useProjects } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";

interface Workspace {
  label: string;
  /** Path segment under /projects/:id ("" is the overview). */
  segment: string;
}

/**
 * Project workspaces, in pipeline order. Like Blender's workspace tabs,
 * each is a purpose-built arrangement of editors for one stage of the job.
 */
export const PROJECT_WORKSPACES: Workspace[] = [
  { label: "Overview", segment: "" },
  { label: "Cycle", segment: "cycle" },
  { label: "Flow path", segment: "flowpath" },
  { label: "Analysis", segment: "analysis" },
  { label: "Map", segment: "map" },
  { label: "Rotor", segment: "rotor" },
  { label: "Runs", segment: "runs" },
  { label: "Settings", segment: "settings" },
];

const GLOBAL_TABS = [
  { label: "Projects", href: "/projects" },
  { label: "Learn", href: "/learn" },
  { label: "Docs", href: "/docs" },
  { label: "Changelog", href: "/changelog" },
];

/**
 * Top bar — 44 px. The only navigation chrome in the app.
 *
 *   [mark] [project switcher ▾] [workspace tabs …]      [⌘K] [level] [?] [theme] [user]
 *
 * Inside a project the tabs are the project's workspaces; outside one they
 * are the global destinations. Everything below the bar belongs to the work.
 */
export function TopBar() {
  const params = useParams<{ id?: string }>();
  const pathname = usePathname() ?? "/";
  const projectId = params?.id;

  return (
    <header className="sticky top-0 z-40 flex h-topbar shrink-0 items-center gap-2 border-b border-border-subtle bg-surface px-2.5">
      <Link
        href={projectId ? "/projects" : "/"}
        aria-label={projectId ? "All projects" : "Cascade home"}
        className="flex h-8 items-center gap-2 rounded-sm px-1.5 transition-colors hover:bg-border-subtle/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus"
      >
        <CascadeMark />
        {!projectId && (
          <span className="text-sm font-semibold tracking-tight text-text">
            Cascade
          </span>
        )}
      </Link>

      {projectId ? (
        <>
          <ProjectSwitcher id={projectId} />
          <Separator />
          <nav
            aria-label="Workspaces"
            className="scrollbar-none flex min-w-0 items-center gap-0.5 overflow-x-auto"
          >
            {PROJECT_WORKSPACES.map((w) => {
              const href = w.segment
                ? `/projects/${projectId}/${w.segment}`
                : `/projects/${projectId}`;
              const active = w.segment
                ? pathname === href || pathname.startsWith(`${href}/`)
                : pathname === href;
              return (
                <Tab key={w.label} href={href} active={active}>
                  {w.label}
                </Tab>
              );
            })}
          </nav>
        </>
      ) : (
        <>
          <Separator />
          <nav
            aria-label="Main"
            className="scrollbar-none flex min-w-0 items-center gap-0.5 overflow-x-auto"
          >
            {GLOBAL_TABS.map((t) => (
              <Tab
                key={t.href}
                href={t.href}
                active={
                  pathname === t.href || pathname.startsWith(`${t.href}/`)
                }
              >
                {t.label}
              </Tab>
            ))}
          </nav>
        </>
      )}

      <div className="ml-auto flex shrink-0 items-center gap-1">
        <CommandField />
        <ExperienceSwitcher />
        <HelpMenu />
        <ThemeToggle />
        <UserMenu />
      </div>
    </header>
  );
}

function Separator() {
  return (
    <span aria-hidden className="mx-1 h-5 w-px shrink-0 bg-border-subtle" />
  );
}

function Tab({
  href,
  active,
  children,
}: {
  href: string;
  active: boolean;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex h-7 shrink-0 items-center rounded-sm px-2.5 text-[13px] font-medium transition-colors duration-fast",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus",
        active
          ? "bg-border-subtle text-text dark:bg-border-default/60"
          : "text-text-muted hover:bg-border-subtle/60 hover:text-text",
      )}
    >
      {children}
    </Link>
  );
}

/** Project name + switcher. Lists every project, plus "All projects" and
 *  "New project". Switching keeps the current workspace. */
function ProjectSwitcher({ id }: { id: string }) {
  const router = useRouter();
  const pathname = usePathname() ?? "";
  const name = useProjectDisplayName(id);
  const { data: projects = [] } = useProjects();

  // /projects/<id>/<workspace>/… → keep <workspace> when switching.
  const workspace = pathname.split("/")[3] ?? "";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="flex h-8 min-w-0 max-w-[260px] items-center gap-1.5 rounded-sm px-2 text-sm font-semibold text-text transition-colors hover:bg-border-subtle/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus data-[state=open]:bg-border-subtle/70"
        >
          <span className="truncate">
            {name}
          </span>
          <ChevronsUpDown className="h-3.5 w-3.5 shrink-0 text-text-muted" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-72">
        <DropdownMenuLabel>Projects</DropdownMenuLabel>
        {projects.map((p) => (
          <DropdownMenuItem
            key={p.id}
            onSelect={() =>
              router.push(
                workspace
                  ? `/projects/${p.id}/${workspace}`
                  : `/projects/${p.id}`,
              )
            }
            className="gap-2"
          >
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm text-text">{p.name}</span>
              <span className="block truncate font-mono text-[10px] text-text-muted">
                {p.id}
              </span>
            </span>
            {p.id === id && <Check className="h-3.5 w-3.5 text-brand" />}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => router.push("/projects")}>
          <LayoutGrid className="h-3.5 w-3.5" />
          All projects
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => router.push("/projects/new")}>
          <Plus className="h-3.5 w-3.5" />
          New project…
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function CommandField() {
  const setPaletteOpen = useUIStore((s) => s.setPaletteOpen);
  return (
    <button
      type="button"
      onClick={() => setPaletteOpen(true)}
      aria-label="Search and run commands"
      className="group mr-1 flex h-7 w-60 items-center gap-2 rounded-sm border border-border-subtle bg-surface-subtle pl-2 pr-1 text-text-muted transition-colors hover:border-border-default hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus max-lg:w-auto max-lg:border-transparent max-lg:bg-transparent"
    >
      <Search className="h-3.5 w-3.5 shrink-0" />
      <span className="hidden flex-1 text-left text-xs lg:inline">
        Search or run a command
      </span>
      <span className="kbd hidden lg:inline-flex">⌘K</span>
    </button>
  );
}

/** Help — the global destinations that used to live in a sidebar. */
function HelpMenu() {
  const router = useRouter();
  const setPaletteOpen = useUIStore((s) => s.setPaletteOpen);
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Help and resources">
          <CircleHelp className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuItem onSelect={() => router.push("/learn")}>
          <GraduationCap className="h-3.5 w-3.5" />
          Learn turbomachinery
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => router.push("/docs")}>
          <BookOpen className="h-3.5 w-3.5" />
          Documentation
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => router.push("/changelog")}>
          <History className="h-3.5 w-3.5" />
          What&apos;s new
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => setPaletteOpen(true)}>
          <Command className="h-3.5 w-3.5" />
          Command palette
          <span className="kbd ml-auto">⌘K</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
