import { Breadcrumb } from "@/components/ui/breadcrumb";
import { cn } from "@/lib/utils";

interface PageHeaderProps {
  breadcrumb?: Array<{ label: string; href?: string }>;
  title: string;
  description?: string;
  actions?: React.ReactNode;
  className?: string;
}

/**
 * Standard page header — a dense instrument strip: locator breadcrumb on
 * top, title + actions row, optional one-line description. Snaps to the
 * 4px grid.
 */
export function PageHeader({
  breadcrumb,
  title,
  description,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <div
      className={cn(
        "flex flex-col gap-1.5 border-b border-border-subtle bg-surface px-5 py-3",
        className,
      )}
    >
      {breadcrumb && breadcrumb.length > 0 && <Breadcrumb items={breadcrumb} />}
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-0.5">
          <h1 className="truncate text-md font-semibold leading-tight tracking-tight text-text">
            {title}
          </h1>
          {description && (
            <p className="max-w-2xl text-xs leading-relaxed text-text-muted">
              {description}
            </p>
          )}
        </div>
        {actions && (
          <div className="flex shrink-0 items-center gap-2">{actions}</div>
        )}
      </div>
    </div>
  );
}
