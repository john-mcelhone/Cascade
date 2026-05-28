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
          "flex h-7 w-full rounded-sm border border-border-default bg-surface px-2 text-sm tabular-nums text-text",
          "placeholder:text-text-muted",
          "focus:outline-none focus:ring-2 focus:ring-border-focus focus:ring-offset-1 focus:ring-offset-background",
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
