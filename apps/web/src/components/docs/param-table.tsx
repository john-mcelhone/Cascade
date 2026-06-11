import { cn } from "@/lib/utils";

export interface ParamRowProps {
  /** Parameter / field / property name (rendered monospace). */
  name: string;
  /** Type label, e.g. "Quantity [K]", "float", "string". */
  type?: string;
  /** Requirement chip. */
  required?: boolean;
  /** Default value, shown as a chip when present. */
  defaultValue?: string;
  children?: React.ReactNode;
}

/** One row of a Stripe-style property list. */
export function ParamRow({
  name,
  type,
  required = false,
  defaultValue,
  children,
}: ParamRowProps) {
  return (
    <div className="flex flex-col gap-1 border-b border-border-subtle py-2.5 last:border-b-0">
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <code className="font-mono text-[13px] font-medium text-text">
          {name}
        </code>
        {type && (
          <span className="font-mono text-xs text-text-muted">{type}</span>
        )}
        {required && (
          <span className="rounded-sm border border-semantic-warning-border bg-semantic-warning-surface px-1 py-px text-[10px] font-medium uppercase tracking-wide text-semantic-warning-text">
            Required
          </span>
        )}
        {defaultValue !== undefined && (
          <span className="rounded-sm border border-border-subtle bg-surface-subtle px-1 py-px font-mono text-[11px] text-text-muted">
            default: {defaultValue}
          </span>
        )}
      </div>
      {children && (
        <div className="text-sm leading-relaxed text-text-subtle">{children}</div>
      )}
    </div>
  );
}

export interface ParamTableProps {
  /** Optional caption above the list, e.g. "Parameters" or a class name. */
  title?: string;
  children: React.ReactNode;
  className?: string;
}

/** Container for `<ParamRow>` entries. */
export function ParamTable({ title, children, className }: ParamTableProps) {
  return (
    <div
      className={cn(
        "rounded-md border border-border-subtle bg-surface-raised px-4 py-1",
        className,
      )}
    >
      {title && (
        <div className="border-b border-border-subtle py-2 text-xs font-medium uppercase tracking-wide text-text-muted">
          {title}
        </div>
      )}
      {children}
    </div>
  );
}
