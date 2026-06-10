import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  // Square status chips — uppercase letterspaced caps, terminal-style.
  "inline-flex items-center gap-1 rounded-sm border px-1.5 py-px text-[10px] font-semibold uppercase tracking-caps tabular-nums",
  {
    variants: {
      variant: {
        default:
          "border-border-subtle bg-surface-subtle text-text",
        brand:
          "border-brand/30 bg-brand-surface text-brand-text",
        success:
          "border-semantic-success-border bg-semantic-success-surface text-semantic-success-text",
        warning:
          "border-semantic-warning-border bg-semantic-warning-surface text-semantic-warning-text",
        danger:
          "border-semantic-danger-border bg-semantic-danger-surface text-semantic-danger-text",
        info:
          "border-semantic-info-border bg-semantic-info-surface text-semantic-info-text",
        outline: "border-border-default bg-transparent text-text",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
