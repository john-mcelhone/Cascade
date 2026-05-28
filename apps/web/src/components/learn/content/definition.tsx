"use client";

import Link from "next/link";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";

export interface DefinitionProps {
  /** Glossary term key — kept as a hook for future hot-linking. */
  term: string;
  /** Optional short definition. If provided, shown inline in the popover. */
  definition?: React.ReactNode;
  /** Optional citation to the glossary or a textbook. */
  source?: string;
  /** Where this term is introduced (chapter slug). */
  chapter?: string;
  children: React.ReactNode;
  className?: string;
}

/**
 * Wraps a word in a popover that surfaces the glossary entry on hover or
 * keyboard focus. Falls back to an underline with the term name if no
 * definition is provided.
 */
export function Definition({
  term,
  definition,
  source,
  chapter,
  children,
  className,
}: DefinitionProps) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className={cn(
            "underline decoration-dotted decoration-text-muted/60 underline-offset-4 outline-none hover:decoration-brand focus-visible:rounded-sm focus-visible:ring-2 focus-visible:ring-border-focus",
            className,
          )}
          aria-label={`Definition: ${term}`}
        >
          {children}
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-80 max-w-[90vw]" sideOffset={4}>
        <div className="flex flex-col gap-2">
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-sm font-medium text-text">{term}</span>
            {chapter && (
              <a
                href={`/learn/${chapter}`}
                className="text-xs text-brand-text hover:underline"
              >
                Ch. {chapter.split("-")[0]}
              </a>
            )}
          </div>
          {definition ? (
            <div className="text-sm leading-relaxed text-text-muted">
              {definition}
            </div>
          ) : (
            <p className="text-sm leading-relaxed text-text-muted">
              See the{" "}
              <Link
                href="/learn/glossary"
                className="text-brand-text hover:underline"
              >
                glossary
              </Link>
              {" "}for the full definition.
            </p>
          )}
          {source && (
            <p className="border-t border-border-subtle pt-2 text-xs text-text-muted">
              {source}
            </p>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
