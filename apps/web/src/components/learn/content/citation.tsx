"use client";

import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";

export interface CitationProps {
  /** Short reference (e.g. "Whitfield & Baines 1990"). */
  source: string;
  /** Optional page or section pointer (e.g. "Ch. 6"). */
  page?: string;
  /** Optional DOI or external URL for the source. */
  href?: string;
  /** Optional longer body shown in the popover. */
  body?: React.ReactNode;
  className?: string;
}

/**
 * Inline footnote-style citation. Renders as a superscript-styled chip
 * that opens a small popover with the full reference on click.
 */
export function Citation({
  source,
  page,
  href,
  body,
  className,
}: CitationProps) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={`Citation: ${source}${page ? `, ${page}` : ""}`}
          className={cn(
            "ml-0.5 inline-flex h-4 items-center rounded-sm border border-border-subtle bg-surface-subtle px-1 align-middle text-[10px] font-mono leading-none text-text-muted transition-colors duration-fast hover:border-brand hover:text-brand-text",
            className,
          )}
        >
          {source}
          {page ? `, ${page}` : ""}
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-80 max-w-[90vw]" sideOffset={4}>
        <div className="flex flex-col gap-2 text-sm">
          <span className="text-sm font-medium text-text">{source}</span>
          {page && <span className="text-xs text-text-muted">{page}</span>}
          {body && (
            <div className="border-t border-border-subtle pt-2 text-text-muted">
              {body}
            </div>
          )}
          {href && (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="text-xs text-brand-text hover:underline"
            >
              Open source
            </a>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
