"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Command } from "cmdk";
import {
  Activity,
  BookOpen,
  Cog,
  Folder,
  Grid3x3,
  ListOrdered,
  Network,
  Plus,
  Settings,
  Wind,
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
  const open = useUIStore((s) => s.paletteOpen);
  const setOpen = useUIStore((s) => s.setPaletteOpen);
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
          <Command.Input
            placeholder="Search projects, pages, settings…"
            className="w-full border-b border-border-subtle bg-transparent px-4 py-3 text-sm outline-none placeholder:text-text-muted"
          />
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
        </Command>
      </DialogContent>
    </Dialog>
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
      className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-sm text-text outline-none aria-selected:bg-surface-subtle data-[selected=true]:bg-surface-subtle"
    >
      <Icon className="h-3 w-3 text-text-muted" />
      <span className="flex-1">{label}</span>
    </Command.Item>
  );
}
