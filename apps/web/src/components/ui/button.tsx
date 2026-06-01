import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  // Base — 28 px tall dense by default, 12 px horizontal padding,
  // 4 px radius (radius.sm), tabular figures inside buttons. A gentle active
  // press-scale gives every button a tactile, Apple-grade response.
  "inline-flex items-center justify-center gap-1.5 rounded-md border text-sm font-medium tabular-nums whitespace-nowrap transition-[background-color,border-color,color,box-shadow,transform] duration-fast ease-out active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50 disabled:active:scale-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-background focus-visible:ring-border-focus [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        // Brand teal gradient — primary action. Lifts on hover with a soft glow.
        default:
          "bg-brand-gradient text-text-inverse border-transparent shadow-z1 hover:shadow-glow hover:brightness-[1.04] active:brightness-95",
        // Quiet outlined — secondary action.
        outline:
          "bg-surface text-text border-border-default hover:bg-surface-subtle hover:border-border-strong",
        // Ghost — toolbar / nav buttons; no border.
        ghost:
          "border-transparent bg-transparent text-text hover:bg-surface-subtle",
        // Subtle filled — a step quieter than outline; for compact toolbars.
        subtle:
          "bg-surface-subtle text-text border-transparent hover:bg-brand-surface",
        // Destructive — used on confirm dialogs for destructive verbs.
        destructive:
          "bg-semantic-danger text-text-inverse border-semantic-danger hover:opacity-90",
        // Link — text-only, brand color.
        link:
          "border-transparent bg-transparent text-brand-text underline-offset-4 hover:underline px-0 h-auto active:scale-100",
      },
      size: {
        // Dense default per DESIGN_SYSTEM §10.
        default: "h-7 px-3 text-sm",
        sm: "h-6 px-2 text-xs",
        lg: "h-9 px-4 text-sm",
        // Generous size for marketing / onboarding heroes.
        xl: "h-11 px-5 text-md rounded-lg",
        // Icon-only; square at the dense toolbar size.
        icon: "h-7 w-7 p-0",
        "icon-sm": "h-6 w-6 p-0",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
