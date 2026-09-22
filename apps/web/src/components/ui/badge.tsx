import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  // Status chips — compact, sentence case, tinted by meaning.
  "inline-flex h-[18px] items-center gap-1 whitespace-nowrap rounded-sm border px-1.5 text-[11px] font-medium leading-none tabular-nums",
  {
    variants: {
      variant: {
        default:
          "border-border-subtle bg-surface-subtle text-text-subtle",
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
        outline: "border-border-default bg-transparent text-text-subtle",
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
