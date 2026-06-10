import * as React from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";

interface BreadcrumbItem {
  label: string;
  href?: string;
}

/**
 * Locator breadcrumb — uppercase micro-labels joined by slashes, reading
 * like a console path: PROJECTS / MICROTURBINE 30KW / CYCLE.
 */
export function Breadcrumb({
  items,
  className,
}: {
  items: BreadcrumbItem[];
  className?: string;
}) {
  return (
    <nav
      aria-label="Breadcrumb"
      className={cn("flex items-center gap-1.5", className)}
    >
      {items.map((item, i) => {
        const isLast = i === items.length - 1;
        return (
          <React.Fragment key={`${item.label}-${i}`}>
            {item.href && !isLast ? (
              <Link
                href={item.href}
                className="micro-label transition-colors duration-fast hover:text-text"
              >
                {item.label}
              </Link>
            ) : (
              <span
                className={cn("micro-label", isLast && "!text-text-subtle")}
              >
                {item.label}
              </span>
            )}
            {!isLast && (
              <span
                aria-hidden
                className="select-none text-[10px] text-border-strong"
              >
                /
              </span>
            )}
          </React.Fragment>
        );
      })}
    </nav>
  );
}
