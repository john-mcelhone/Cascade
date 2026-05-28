import Link from "next/link";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";

export interface NextChapterProps {
  prevHref?: string;
  prevTitle?: string;
  nextHref?: string;
  nextTitle?: string;
  className?: string;
}

/** Footer nav cards — previous / next chapter. */
export function NextChapter({
  prevHref,
  prevTitle,
  nextHref,
  nextTitle,
  className,
}: NextChapterProps) {
  return (
    <nav
      aria-label="Chapter navigation"
      className={cn(
        "mt-6 flex flex-col gap-2 border-t border-border-subtle pt-6 sm:flex-row",
        className,
      )}
    >
      {prevHref && prevTitle ? (
        <Link
          href={prevHref}
          className="group flex-1 rounded-md border border-border-subtle bg-surface-raised p-3 transition-colors duration-fast hover:border-brand"
        >
          <span className="flex items-center gap-1 text-xs text-text-muted">
            <ArrowLeft className="h-3 w-3" />
            Previous chapter
          </span>
          <span className="mt-1 block text-sm font-medium text-text group-hover:text-brand-text">
            {prevTitle}
          </span>
        </Link>
      ) : (
        <div className="flex-1" />
      )}
      {nextHref && nextTitle ? (
        <Link
          href={nextHref}
          className="group flex-1 rounded-md border border-border-subtle bg-surface-raised p-3 text-right transition-colors duration-fast hover:border-brand"
        >
          <span className="flex items-center justify-end gap-1 text-xs text-text-muted">
            Next chapter
            <ArrowRight className="h-3 w-3" />
          </span>
          <span className="mt-1 block text-sm font-medium text-text group-hover:text-brand-text">
            {nextTitle}
          </span>
        </Link>
      ) : (
        <div className="flex-1" />
      )}
    </nav>
  );
}
