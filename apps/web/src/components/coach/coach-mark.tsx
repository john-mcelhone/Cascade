"use client";

import * as React from "react";
import { Lightbulb, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/lib/stores/ui-store";
import { useCoaching } from "@/lib/hooks/use-coaching";

interface CoachMarkProps {
  /** Stable key — once dismissed, this mark never returns. */
  id: string;
  title?: string;
  children: React.ReactNode;
  /** Optional call-to-action rendered under the body. */
  action?: React.ReactNode;
  className?: string;
  /** Render even outside guided mode (rare; defaults to guided-only). */
  alwaysShow?: boolean;
}

/**
 * An inline coaching note for absolute beginners. Appears only in "guided"
 * experience mode (unless alwaysShow), is dismissible, and stays dismissed
 * across sessions. Plain language, friendly, never blocking.
 */
export function CoachMark({
  id,
  title,
  children,
  action,
  className,
  alwaysShow = false,
}: CoachMarkProps) {
  const { showInlineCoaching } = useCoaching();
  const dismissed = useUIStore((s) => Boolean(s.dismissedHints[id]));
  const dismissHint = useUIStore((s) => s.dismissHint);

  if ((!showInlineCoaching && !alwaysShow) || dismissed) return null;

  return (
    <div
      className={cn(
        // Advisory note — flat brand-surface panel with a 2px brand rail.
        "animate-fade-in-up relative flex gap-3 rounded-sm border border-brand/30 border-l-2 border-l-brand bg-brand-surface/50 p-3 pr-9 text-sm",
        className,
      )}
      role="note"
    >
      <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-brand" />
      <div className="min-w-0 flex-1">
        {title && (
          <p className="font-medium text-text">{title}</p>
        )}
        <div className={cn("text-text-subtle", title && "mt-0.5")}>
          {children}
        </div>
        {action && <div className="mt-2">{action}</div>}
      </div>
      <button
        type="button"
        onClick={() => dismissHint(id)}
        aria-label="Dismiss tip"
        className="absolute right-2 top-2 rounded-sm p-1 text-text-muted transition-colors hover:bg-brand-surface hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
