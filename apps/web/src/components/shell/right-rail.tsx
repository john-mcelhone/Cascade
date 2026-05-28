import { cn } from "@/lib/utils";

/**
 * Right-rail container. 320 px wide by default. Pages compose this with
 * arbitrary content (properties panels, candidate detail, loss-model picker,
 * etc). Border on the left side, scrollable.
 */
export function RightRail({
  children,
  width = 320,
  className,
}: {
  children: React.ReactNode;
  width?: number;
  className?: string;
}) {
  return (
    <aside
      style={{ width }}
      className={cn(
        "shrink-0 overflow-auto scrollbar-subtle border-l border-border-subtle bg-surface-subtle/40",
        className,
      )}
    >
      {children}
    </aside>
  );
}
