import { cn } from "@/lib/utils";

export interface SectionProps {
  /** Stable anchor id — also the target for the right-rail reading ToC. */
  id: string;
  /** Section heading. */
  title: string;
  /** Optional eyebrow shown above the heading. */
  eyebrow?: string;
  children: React.ReactNode;
  className?: string;
}

/**
 * A chapter subsection. Renders an anchor + H2 heading + children stacked
 * with default prose gap. The id is consumed by `<ReadingToc>` via
 * IntersectionObserver to highlight the current section as the user reads.
 */
export function Section({
  id,
  title,
  eyebrow,
  children,
  className,
}: SectionProps) {
  return (
    <section
      id={id}
      data-learn-section
      data-learn-section-title={title}
      className={cn("flex scroll-mt-20 flex-col gap-4", className)}
    >
      <div className="flex flex-col gap-1">
        {eyebrow && (
          <span className="text-xs font-medium uppercase tracking-wide text-text-muted">
            {eyebrow}
          </span>
        )}
        <h2 className="group flex items-baseline gap-2 text-lg font-medium leading-tight text-text">
          <a
            href={`#${id}`}
            aria-label={`Link to ${title}`}
            className="opacity-0 transition-opacity duration-fast group-hover:opacity-60 text-text-muted no-underline"
          >
            #
          </a>
          {title}
        </h2>
      </div>
      {children}
    </section>
  );
}
