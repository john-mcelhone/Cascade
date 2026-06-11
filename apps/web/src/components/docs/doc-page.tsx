import Link from "next/link";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { ReadingToc } from "@/components/learn/content";
import { getDocNeighbors, getDocPage, docHref } from "@/lib/docs/manifest";
import { cn } from "@/lib/utils";

export interface DocPageProps {
  /** Slug in the docs manifest — drives the header and prev/next footer. */
  slug: string;
  /** Optional override for the lead paragraph under the title. */
  lead?: React.ReactNode;
  /** Hide the right-rail "On this page" ToC (for short pages). */
  noToc?: boolean;
  children: React.ReactNode;
}

/**
 * Shared article shell for every docs page: eyebrow + H1 + lead from the
 * manifest, a 720px prose column, the sticky right-rail ToC (driven by
 * `<Section>` anchors), and prev/next footer cards.
 */
export function DocPage({ slug, lead, noToc = false, children }: DocPageProps) {
  const meta = getDocPage(slug);
  const { prev, next } = getDocNeighbors(slug);

  return (
    <div className="flex w-full justify-center px-6">
      <article className="flex w-full max-w-3xl flex-col gap-6 py-8 lg:py-12">
        <header className="flex flex-col gap-2">
          <span className="text-xs font-medium uppercase tracking-wide text-text-muted">
            Documentation
          </span>
          <h1 className="text-xl font-medium leading-tight text-text">
            {meta?.title ?? slug}
          </h1>
          <p className="max-w-2xl text-lg leading-relaxed text-text-muted">
            {lead ?? meta?.description}
          </p>
        </header>

        <div className="flex flex-col gap-8 text-md leading-relaxed text-text">
          {children}
        </div>

        <footer className="mt-4 grid gap-3 border-t border-border-subtle pt-6 sm:grid-cols-2">
          {prev ? (
            <NeighborCard
              href={docHref(prev.slug)}
              direction="prev"
              title={prev.title}
            />
          ) : (
            <div />
          )}
          {next ? (
            <NeighborCard
              href={docHref(next.slug)}
              direction="next"
              title={next.title}
            />
          ) : (
            <div />
          )}
        </footer>
      </article>
      {!noToc && <ReadingToc />}
    </div>
  );
}

function NeighborCard({
  href,
  direction,
  title,
}: {
  href: string;
  direction: "prev" | "next";
  title: string;
}) {
  const next = direction === "next";
  return (
    <Link
      href={href}
      className={cn(
        "group flex flex-col gap-1 rounded-md border border-border-subtle bg-surface-raised px-4 py-3 transition-colors duration-fast hover:border-border-default",
        next ? "items-end text-right sm:col-start-2" : "items-start",
      )}
    >
      <span className="flex items-center gap-1 text-xs font-medium uppercase tracking-wide text-text-muted">
        {!next && (
          <ArrowLeft className="h-3 w-3 transition-transform duration-fast group-hover:-translate-x-0.5" />
        )}
        {next ? "Next" : "Previous"}
        {next && (
          <ArrowRight className="h-3 w-3 transition-transform duration-fast group-hover:translate-x-0.5" />
        )}
      </span>
      <span className="text-sm font-medium text-text">{title}</span>
    </Link>
  );
}
