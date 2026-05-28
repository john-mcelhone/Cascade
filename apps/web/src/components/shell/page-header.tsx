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
 * Standard page header — breadcrumb on top, title + actions row, optional
 * description. Pages snap to this 4px-grid spacing.
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
        "flex flex-col gap-2 border-b border-border-subtle bg-surface px-5 py-4",
        className,
      )}
    >
      {breadcrumb && breadcrumb.length > 0 && <Breadcrumb items={breadcrumb} />}
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-lg font-medium text-text leading-tight">
            {title}
          </h1>
          {description && (
            <p className="max-w-2xl text-sm text-text-muted">{description}</p>
          )}
        </div>
        {actions && (
          <div className="flex items-center gap-2 shrink-0">{actions}</div>
        )}
      </div>
    </div>
  );
}
