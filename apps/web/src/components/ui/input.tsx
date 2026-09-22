import * as React from "react";
import { cn } from "@/lib/utils";

export type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        ref={ref}
        className={cn(
          // Recessed field: sits a step below the panel, hairline edge that
          // firms up on hover, brand ring on focus.
          "flex h-7 w-full rounded-sm border border-border-subtle bg-surface-subtle px-2 text-sm tabular-nums text-text",
          "transition-[border-color,box-shadow] duration-fast",
          "placeholder:text-text-disabled hover:border-border-default",
          "focus:outline-none focus:border-brand/70 focus:ring-2 focus:ring-brand/25",
          "disabled:cursor-not-allowed disabled:opacity-50",
          // Yellow user-input convention (DESIGN_SYSTEM §11 #8) — opt in with data-input.
          "data-[input=true]:bg-surface-input",
          className,
        )}
        {...props}
      />
    );
  },
);
Input.displayName = "Input";

export { Input };
