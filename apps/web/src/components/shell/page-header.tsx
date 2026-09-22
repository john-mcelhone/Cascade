"use client";

import * as React from "react";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { useCoaching } from "@/lib/hooks/use-coaching";
import { cn } from "@/lib/utils";

interface PageHeaderProps {
  breadcrumb?: Array<{ label: string; href?: string }>;
  title: string;
  description?: string;
  actions?: React.ReactNode;
  className?: string;
}

/**
 * Workspace header — one 44 px toolbar row: title, a one-line description,
 * and the workspace's primary actions on the right.
 *
 * The top bar already names the project and the active workspace, so the
 * breadcrumb here only renders levels *below* a workspace (e.g. Flow path ›
 * a candidate); "Projects" and the project root are dropped.
 *
 * Experience level shapes the description: guided wraps it in full under
 * the title, standard shows it inline (truncated, full text on hover),
 * expert hides it.
 */
export function PageHeader({
  breadcrumb,
  title,
  description,
  actions,
  className,
}: PageHeaderProps) {
  const { level } = useCoaching();
  const parents = (breadcrumb ?? [])
    .slice(0, -1)
    .filter(
      (b) =>
        b.href && b.href !== "/projects" && !/^\/projects\/[^/]+$/.test(b.href),
    );
  const roomy = level === "guided";

  return (
    <div
      className={cn(
        "flex shrink-0 gap-3 border-b border-border-subtle bg-surface px-4",
        roomy ? "items-start py-2.5" : "h-11 items-center",
        className,
      )}
    >
      <div
        className={cn(
          "flex min-w-0 flex-1",
          roomy ? "flex-col gap-0.5" : "items-baseline gap-3",
        )}
      >
        <div className="flex min-w-0 shrink-0 items-center gap-1 text-sm">
          {parents.map((p) => (
            <React.Fragment key={p.href}>
              <Link
                href={p.href!}
                className="truncate text-text-muted transition-colors hover:text-text"
              >
                {p.label}
              </Link>
              <ChevronRight className="h-3.5 w-3.5 shrink-0 text-text-disabled" />
            </React.Fragment>
          ))}
          <h1 className="truncate font-semibold tracking-tight text-text">
            {title}
          </h1>
        </div>
        {description && level !== "expert" && (
          <p
            title={roomy ? undefined : description}
            className={cn(
              "text-xs text-text-muted",
              roomy ? "max-w-3xl leading-relaxed" : "min-w-0 truncate",
            )}
          >
            {description}
          </p>
        )}
      </div>
      {actions && (
        <div className="flex shrink-0 items-center gap-2">{actions}</div>
      )}
    </div>
  );
}
