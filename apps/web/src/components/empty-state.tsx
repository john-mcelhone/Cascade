import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * First-class empty state. Three lines max: one heading, one orienting
 * sentence with a number, one action. No illustrations. No exclamations.
 */
export function EmptyState({
  Icon,
  title,
  description,
  action,
  className,
}: {
  Icon?: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "mx-auto flex max-w-md flex-col items-center justify-center gap-3 px-5 py-8 text-center",
        className,
      )}
    >
      {Icon && (
        <div className="animate-scale-in flex h-14 w-14 items-center justify-center rounded-2xl border border-border-subtle bg-gradient-to-b from-surface-raised to-surface-subtle text-text-muted shadow-z1">
          <Icon className="h-6 w-6 text-brand" aria-hidden />
        </div>
      )}
      <h2 className="text-md font-semibold tracking-tight text-text">{title}</h2>
      {description && (
        <p className="text-sm text-text-muted">{description}</p>
      )}
      {action && <div className="pt-1">{action}</div>}
    </div>
  );
}
