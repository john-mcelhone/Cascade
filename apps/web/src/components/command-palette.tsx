"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { Command } from "cmdk";
import {
  Activity,
  BookOpen,
  Cog,
  Folder,
  GraduationCap,
  Grid3x3,
  ListOrdered,
  Moon,
  Network,
  Plus,
  Settings,
  Sparkles,
  SlidersHorizontal,
  Search,
  Sun,
  Wind,
  Zap,
} from "lucide-react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { useUIStore } from "@/lib/stores/ui-store";
import { useProjects } from "@/lib/api/hooks";

interface PaletteRoute {
  label: string;
  group: "Navigation" | "Projects" | "Help";
  Icon: React.ComponentType<{ className?: string }>;
  href: string;
  keywords?: string[];
}

const navItems: PaletteRoute[] = [
  {
    label: "Projects",
    group: "Navigation",
    Icon: Folder,
    href: "/projects",
    keywords: ["workspace", "list"],
  },
  {
    label: "New project",
    group: "Navigation",
    Icon: Plus,
    href: "/projects/new",
    keywords: ["create", "template"],
  },
  {
    label: "Docs",
    group: "Help",
    Icon: BookOpen,
    href: "/docs",
    keywords: ["documentation", "theory", "manual"],
  },
  {
    label: "Learn turbomachinery",
    group: "Help",
    Icon: GraduationCap,
    href: "/learn",
    keywords: ["tutorial", "course", "beginner", "chapters"],
  },
  {
    label: "Validation report",
    group: "Help",
    Icon: BookOpen,
    href: "/docs/validation",
    keywords: ["benchmark", "pass-gates", "qa"],
  },
];

/**
 * Global command palette opened with ⌘K. Lists routes, projects, and per-project pages.
 */
export function CommandPalette() {
  const router = useRouter();
  const { setTheme } = useTheme();
  const open = useUIStore((s) => s.paletteOpen);
  const setOpen = useUIStore((s) => s.setPaletteOpen);
  const setExperience = useUIStore((s) => s.setExperience);
  const { data: projects = [] } = useProjects();

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen(!open);
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, setOpen]);

  const go = (href: string) => {
    setOpen(false);
    router.push(href);
  };

  const run = (fn: () => void) => {
    setOpen(false);
    fn();
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-xl p-0 overflow-hidden">
        <DialogTitle className="sr-only">Command palette</DialogTitle>
        <Command
          className="bg-surface-raised"
          loop
          // cmdk searches against item children + keywords.
          filter={(value, search, keywords) => {
            const haystack = `${value} ${keywords?.join(" ") ?? ""}`.toLowerCase();
            return haystack.includes(search.toLowerCase()) ? 1 : 0;
          }}
        >
          <div className="flex items-center gap-2 border-b border-border-subtle px-3">
            <Search className="h-4 w-4 shrink-0 text-text-muted" />
            <Command.Input
              placeholder="Search projects, jump to a page, or run a command…"
              className="w-full bg-transparent py-3 text-sm outline-none placeholder:text-text-muted"
            />
          </div>
          <Command.List className="max-h-80 overflow-auto scrollbar-subtle p-2">
            <Command.Empty className="px-3 py-6 text-center text-sm text-text-muted">
              Nothing matches. Try a project name or a page.
            </Command.Empty>

            <Command.Group
              heading="Navigation"
              className="px-1 pt-1 pb-2 text-[10px] uppercase tracking-wide text-text-muted [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1"
            >
              {navItems.map((item) => (
                <PaletteItem
                  key={item.href}
                  Icon={item.Icon}
                  label={item.label}
                  keywords={item.keywords}
                  onSelect={() => go(item.href)}
                />
              ))}
            </Command.Group>

            <Command.Group
              heading="Preferences"
              className="px-1 pt-1 pb-2 text-[10px] uppercase tracking-wide text-text-muted [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1"
            >
              <PaletteItem
                Icon={Sparkles}
                label="Guided mode"
                keywords={["beginner", "experience", "help", "coaching"]}
                onSelect={() => run(() => setExperience("guided"))}
              />
              <PaletteItem
                Icon={SlidersHorizontal}
                label="Standard mode"
                keywords={["experience", "default"]}
                onSelect={() => run(() => setExperience("standard"))}
              />
              <PaletteItem
                Icon={Zap}
                label="Expert mode"
                keywords={["experience", "pro", "dense", "keyboard"]}
                onSelect={() => run(() => setExperience("expert"))}
              />
              <PaletteItem
                Icon={Sun}
                label="Light theme"
                keywords={["appearance", "color"]}
                onSelect={() => run(() => setTheme("light"))}
              />
              <PaletteItem
                Icon={Moon}
                label="Dark theme"
                keywords={["appearance", "color", "night"]}
                onSelect={() => run(() => setTheme("dark"))}
              />
            </Command.Group>

            {projects.length > 0 && (
              <Command.Group
                heading="Projects"
                className="px-1 pt-1 pb-2 text-[10px] uppercase tracking-wide text-text-muted [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1"
              >
                {projects.map((p) => (
                  <PaletteItem
                    key={p.id}
                    Icon={Folder}
                    label={p.name}
                    keywords={[p.id, "project"]}
                    onSelect={() => go(`/projects/${p.id}`)}
                  />
                ))}
              </Command.Group>
            )}

            {projects.length > 0 && (
              <Command.Group
                heading="Pages"
                className="px-1 pt-1 pb-2 text-[10px] uppercase tracking-wide text-text-muted [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1"
              >
                {projects.flatMap((p) => [
                  {
                    Icon: Network,
                    href: `/projects/${p.id}/cycle`,
                    label: `${p.name} · Cycle`,
                  },
                  {
                    Icon: Wind,
                    href: `/projects/${p.id}/flowpath`,
                    label: `${p.name} · Flow path`,
                  },
                  {
                    Icon: Activity,
                    href: `/projects/${p.id}/analysis`,
                    label: `${p.name} · Analysis`,
                  },
                  {
                    Icon: Grid3x3,
                    href: `/projects/${p.id}/map`,
                    label: `${p.name} · Map`,
                  },
                  {
                    Icon: Cog,
                    href: `/projects/${p.id}/rotor`,
                    label: `${p.name} · Rotor`,
                  },
                  {
                    Icon: ListOrdered,
                    href: `/projects/${p.id}/runs`,
                    label: `${p.name} · Runs`,
                  },
                  {
                    Icon: Settings,
                    href: `/projects/${p.id}/settings`,
                    label: `${p.name} · Settings`,
                  },
                ]).map((sub) => (
                  <PaletteItem
                    key={sub.href}
                    Icon={sub.Icon}
                    label={sub.label}
                    onSelect={() => go(sub.href)}
                  />
                ))}
              </Command.Group>
            )}
          </Command.List>

          <div className="flex items-center justify-between border-t border-border-subtle px-3 py-2 text-[10px] text-text-muted">
            <span className="inline-flex items-center gap-1">
              <CascadeKbd>↑</CascadeKbd>
              <CascadeKbd>↓</CascadeKbd>
              to navigate
            </span>
            <span className="inline-flex items-center gap-1">
              <CascadeKbd>↵</CascadeKbd>
              to select
              <span className="mx-1 text-border-default">·</span>
              <CascadeKbd>esc</CascadeKbd>
              to close
            </span>
          </div>
        </Command>
      </DialogContent>
    </Dialog>
  );
}

function CascadeKbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="inline-flex h-4 min-w-4 items-center justify-center rounded border border-border-subtle bg-surface-subtle px-1 font-mono text-[10px]">
      {children}
    </kbd>
  );
}

function PaletteItem({
  Icon,
  label,
  keywords,
  onSelect,
}: {
  Icon: React.ComponentType<{ className?: string }>;
  label: string;
  keywords?: string[];
  onSelect: () => void;
}) {
  return (
    <Command.Item
      value={label}
      keywords={keywords}
      onSelect={onSelect}
      className="group flex cursor-pointer items-center gap-2.5 rounded-md px-2 py-1.5 text-sm text-text outline-none transition-colors aria-selected:bg-brand-surface aria-selected:text-brand-text data-[selected=true]:bg-brand-surface data-[selected=true]:text-brand-text"
    >
      <Icon className="h-3.5 w-3.5 text-text-muted group-aria-selected:text-brand" />
      <span className="flex-1">{label}</span>
    </Command.Item>
  );
}
