"use client";

import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import {
  Network,
  Wind,
  Activity,
  Grid3x3,
  Cog,
  ListOrdered,
  Settings,
  PanelLeftClose,
  PanelLeftOpen,
  Folder,
  BookOpen,
  GraduationCap,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useUIStore } from "@/lib/stores/ui-store";
import type { LucideIcon } from "lucide-react";

interface NavItem {
  href: (projectId?: string) => string;
  label: string;
  Icon: LucideIcon;
  /** Requires a project context to render. */
  requiresProject?: boolean;
}

const projectNav: NavItem[] = [
  { label: "Cycle", Icon: Network, href: (id) => `/projects/${id}/cycle`, requiresProject: true },
  { label: "Flow path", Icon: Wind, href: (id) => `/projects/${id}/flowpath`, requiresProject: true },
  { label: "Analysis", Icon: Activity, href: (id) => `/projects/${id}/analysis`, requiresProject: true },
  { label: "Map", Icon: Grid3x3, href: (id) => `/projects/${id}/map`, requiresProject: true },
  { label: "Rotor", Icon: Cog, href: (id) => `/projects/${id}/rotor`, requiresProject: true },
  { label: "Runs", Icon: ListOrdered, href: (id) => `/projects/${id}/runs`, requiresProject: true },
  { label: "Settings", Icon: Settings, href: (id) => `/projects/${id}/settings`, requiresProject: true },
];

const globalNav: NavItem[] = [
  { label: "Projects", Icon: Folder, href: () => "/projects" },
  { label: "Learn", Icon: GraduationCap, href: () => "/learn" },
  { label: "Docs", Icon: BookOpen, href: () => "/docs" },
];

export function LeftRail() {
  const railCollapsed = useUIStore((s) => s.railCollapsed);
  const toggleRail = useUIStore((s) => s.toggleRail);
  const params = useParams<{ id?: string }>();
  const projectId = params?.id;
  const pathname = usePathname();

  const inProject = Boolean(projectId);

  return (
    <aside
      className={cn(
        "shrink-0 border-r border-border-subtle bg-surface transition-[width] duration-medium ease-out",
        railCollapsed ? "w-rail-collapsed" : "w-rail",
      )}
    >
      <nav className="flex h-full flex-col px-2 py-3">
        {/* Global nav (always visible) */}
        <div className="flex flex-col gap-0.5">
          {globalNav.map((item) => (
            <RailLink
              key={item.label}
              item={item}
              collapsed={railCollapsed}
              active={
                pathname === item.href() ||
                (item.href() !== "/" && pathname?.startsWith(item.href()))
              }
            />
          ))}
        </div>

        {/* Project nav (only when inside a project) */}
        {inProject && (
          <>
            <div className="my-3 h-px bg-border-subtle" />
            <div
              className={cn(
                "mb-1 px-2 text-xs font-medium uppercase tracking-wide text-text-muted",
                railCollapsed && "sr-only",
              )}
            >
              Project
            </div>
            <div className="flex flex-col gap-0.5">
              {projectNav.map((item) => {
                const href = item.href(projectId);
                return (
                  <RailLink
                    key={item.label}
                    item={{ ...item, href: () => href }}
                    collapsed={railCollapsed}
                    active={pathname === href}
                  />
                );
              })}
            </div>
          </>
        )}

        {/* Collapse toggle pinned to the bottom */}
        <div className="mt-auto pt-2">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                onClick={toggleRail}
                aria-label={railCollapsed ? "Expand sidebar" : "Collapse sidebar"}
                className="w-full justify-start gap-2 px-2 text-text-muted"
              >
                {railCollapsed ? (
                  <PanelLeftOpen className="h-4 w-4" />
                ) : (
                  <PanelLeftClose className="h-4 w-4" />
                )}
                {!railCollapsed && (
                  <span className="text-sm">Collapse</span>
                )}
              </Button>
            </TooltipTrigger>
            {railCollapsed && (
              <TooltipContent side="right">Expand sidebar</TooltipContent>
            )}
          </Tooltip>
        </div>
      </nav>
    </aside>
  );
}

function RailLink({
  item,
  collapsed,
  active,
}: {
  item: NavItem;
  collapsed: boolean;
  active: boolean;
}) {
  const { Icon, label } = item;
  const link = (
    <Link
      href={item.href()}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex h-7 items-center gap-2 rounded-sm px-2 text-sm transition-colors duration-fast",
        active
          ? "bg-brand-surface text-brand-text font-medium"
          : "text-text-muted hover:bg-surface-subtle hover:text-text",
        collapsed && "justify-center px-0",
      )}
    >
      <Icon className="h-4 w-4 shrink-0" />
      {!collapsed && <span className="truncate">{label}</span>}
    </Link>
  );

  if (collapsed) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>{link}</TooltipTrigger>
        <TooltipContent side="right">{label}</TooltipContent>
      </Tooltip>
    );
  }
  return link;
}
