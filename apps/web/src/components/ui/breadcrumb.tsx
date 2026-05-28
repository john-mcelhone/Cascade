import * as React from "react";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface BreadcrumbItem {
  label: string;
  href?: string;
}

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
      className={cn("flex items-center gap-1 text-sm text-text-muted", className)}
    >
      {items.map((item, i) => {
        const isLast = i === items.length - 1;
        return (
          <React.Fragment key={`${item.label}-${i}`}>
            {item.href && !isLast ? (
              <Link
                href={item.href}
                className="hover:text-text transition-colors duration-fast"
              >
                {item.label}
              </Link>
            ) : (
              <span className={cn(isLast && "text-text")}>{item.label}</span>
            )}
            {!isLast && (
              <ChevronRight className="h-3 w-3 text-text-muted/70" />
            )}
          </React.Fragment>
        );
      })}
    </nav>
  );
}
