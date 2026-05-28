"use client";

import Link from "next/link";
import { ExternalLink, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface WidgetFrameProps {
  /** Label shown in the widget header. */
  label: string;
  /** Optional short caption shown right of the label. */
  caption?: string;
  /** Called when the user clicks Reset. */
  onReset?: () => void;
  /** Optional "Open in Cascade" deep-link. */
  openHref?: string;
  /** Treat the open link as external (new tab). */
  openExternal?: boolean;
  /** CTA label for the open link. */
  openLabel?: string;
  /** Optional CSS aspect ratio applied to the body container. */
  aspectRatio?: string;
  /** Body height — overrides aspect ratio when both supplied. */
  bodyHeight?: string;
  children: React.ReactNode;
  className?: string;
}

/**
 * Shared shell for every learn widget. Provides the bordered card,
 * dark-mode aware surface, a header with label + reset + open CTA, and
 * an aspect-ratio body so the widget never collapses to zero height
 * while loading.
 */
export function WidgetFrame({
  label,
  caption,
  onReset,
  openHref,
  openExternal,
  openLabel = "Open in Cascade",
  aspectRatio = "16 / 10",
  bodyHeight,
  children,
  className,
}: WidgetFrameProps) {
  const LinkComp = openExternal ? "a" : Link;
  const externalProps = openExternal
    ? { target: "_blank", rel: "noreferrer" }
    : {};
  return (
    <figure
      className={cn(
        "flex w-full flex-col gap-0 overflow-hidden rounded-md border border-border-subtle bg-surface-raised",
        className,
      )}
    >
      <header className="flex items-center justify-between gap-2 border-b border-border-subtle bg-surface-subtle/50 px-3 py-2">
        <div className="flex items-baseline gap-2">
          <span className="text-xs font-medium uppercase tracking-wide text-text-muted">
            Widget
          </span>
          <span className="text-sm font-medium text-text">{label}</span>
          {caption && (
            <span className="text-xs text-text-muted">{caption}</span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {onReset && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onReset}
              className="gap-1"
            >
              <RotateCcw className="h-3 w-3" />
              Reset
            </Button>
          )}
          {openHref && (
            <LinkComp
              href={openHref}
              {...externalProps}
              className="inline-flex h-6 items-center gap-1 rounded-sm border border-brand/30 bg-brand-surface px-2 text-xs font-medium text-brand-text transition-colors duration-fast hover:border-brand"
            >
              {openLabel}
              {openExternal && <ExternalLink className="h-3 w-3" />}
            </LinkComp>
          )}
        </div>
      </header>
      <div
        className="relative w-full"
        style={
          bodyHeight
            ? { height: bodyHeight }
            : { aspectRatio }
        }
      >
        {children}
      </div>
    </figure>
  );
}
