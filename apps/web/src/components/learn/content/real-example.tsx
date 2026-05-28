import { cn } from "@/lib/utils";

export interface RealExampleProps {
  /** Card title (e.g. "Capstone C30 microturbine"). */
  title: string;
  /** Optional source citation shown in small text in the header. */
  source?: string;
  children: React.ReactNode;
  className?: string;
}

/**
 * Boxed real-world example. The brief calls these out because the tutorial
 * leads with concrete machines (a turbocharger, a microturbine) before
 * abstracting to math.
 */
export function RealExample({
  title,
  source,
  children,
  className,
}: RealExampleProps) {
  return (
    <figure
      className={cn(
        "flex flex-col gap-2 rounded-md border border-border-subtle bg-surface-raised px-4 py-3",
        className,
      )}
    >
      <figcaption className="flex items-baseline justify-between gap-3 border-b border-border-subtle pb-2">
        <span className="text-sm font-medium text-text">
          Real example · {title}
        </span>
        {source && (
          <span className="text-xs text-text-muted">{source}</span>
        )}
      </figcaption>
      <div className="text-md leading-relaxed text-text">{children}</div>
    </figure>
  );
}
