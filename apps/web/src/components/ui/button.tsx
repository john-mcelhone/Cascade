import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  // Base — 28 px tall dense by default, 4 px radius, tabular figures.
  // Flat fills; state is carried by color, not shadow or scale.
  "inline-flex items-center justify-center gap-1.5 rounded-sm border text-sm font-medium select-none tabular-nums whitespace-nowrap transition-[background-color,border-color,color] duration-fast ease-out disabled:pointer-events-none disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-background focus-visible:ring-border-focus [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        // Solid brand cyan — primary action. Inverse text reads like an
        // illuminated key on the console.
        default:
          "bg-brand text-text-inverse border-transparent shadow-z1 hover:bg-brand-hover active:bg-brand-pressed",
        // Quiet filled — secondary action. Reads as a raised key on the
        // panel rather than a hollow outline.
        outline:
          "bg-surface-raised text-text border-border-default shadow-z1 hover:bg-surface-subtle hover:border-border-strong dark:bg-border-subtle dark:hover:bg-border-default/70",
        // Ghost — toolbar / nav buttons; no border.
        ghost:
          "border-transparent bg-transparent text-text-subtle hover:bg-border-subtle/70 hover:text-text",
        // Subtle filled — a step quieter than outline; for compact toolbars.
        subtle:
          "bg-surface-subtle text-text border-transparent hover:bg-border-subtle",
        // Destructive — used on confirm dialogs for destructive verbs.
        destructive:
          "bg-semantic-danger text-text-inverse border-semantic-danger hover:opacity-90",
        // Link — text-only, brand color.
        link:
          "border-transparent bg-transparent text-brand-text underline-offset-4 hover:underline px-0 h-auto",
      },
      size: {
        // Dense default per DESIGN_SYSTEM §10.
        default: "h-7 px-3 text-sm",
        sm: "h-6 px-2 text-xs",
        lg: "h-9 px-4 text-sm",
        // Generous size for marketing / onboarding heroes.
        xl: "h-10 px-5 text-md",
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
