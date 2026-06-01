"use client";

import { Sparkles, SlidersHorizontal, Zap, Check } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { useMounted } from "@/lib/hooks/use-mounted";
import {
  EXPERIENCE_LEVELS,
  useUIStore,
  type ExperienceLevel,
} from "@/lib/stores/ui-store";

const ICONS: Record<ExperienceLevel, LucideIcon> = {
  guided: Sparkles,
  standard: SlidersHorizontal,
  expert: Zap,
};

/**
 * Experience-level control. One dial that retunes the whole product for the
 * beginner→professional range. Lives in the top bar; the chosen level is
 * persisted and read across the app to drive density + coaching.
 */
export function ExperienceSwitcher({ compact = false }: { compact?: boolean }) {
  const mounted = useMounted();
  const experience = useUIStore((s) => s.experience);
  const setExperience = useUIStore((s) => s.setExperience);

  // Until hydrated, render the persisted default ("guided") so SSR matches.
  const current = mounted ? experience : "guided";
  const Icon = ICONS[current];
  const label = EXPERIENCE_LEVELS.find((l) => l.id === current)?.label ?? "Guided";

  return (
    <DropdownMenu>
      <Tooltip>
        <TooltipTrigger asChild>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              className={cn(
                "h-7 gap-1.5 px-2 text-text-muted hover:text-text",
                compact && "px-1.5",
              )}
              aria-label={`Experience level: ${label}`}
            >
              <Icon className="h-3.5 w-3.5 text-brand" />
              {!compact && <span className="text-xs font-medium">{label}</span>}
            </Button>
          </DropdownMenuTrigger>
        </TooltipTrigger>
        <TooltipContent>Experience level — adapts the whole app</TooltipContent>
      </Tooltip>

      <DropdownMenuContent align="end" className="w-72">
        <DropdownMenuLabel className="flex items-center gap-1.5 text-text">
          <Sparkles className="h-3 w-3 text-brand" />
          How much help do you want?
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {EXPERIENCE_LEVELS.map((level) => {
          const LevelIcon = ICONS[level.id];
          const active = current === level.id;
          return (
            <DropdownMenuItem
              key={level.id}
              onSelect={() => setExperience(level.id)}
              className="items-start gap-2.5 py-2"
            >
              <span
                className={cn(
                  "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md border",
                  active
                    ? "border-brand/40 bg-brand-surface text-brand-text"
                    : "border-border-subtle bg-surface-subtle text-text-muted",
                )}
              >
                <LevelIcon className="h-3.5 w-3.5" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-1.5">
                  <span className="text-sm font-medium text-text">
                    {level.label}
                  </span>
                  {active && <Check className="h-3 w-3 text-brand" />}
                </span>
                <span className="mt-0.5 block text-xs leading-snug text-text-muted">
                  {level.blurb}
                </span>
              </span>
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
