import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge Tailwind class names with last-wins precedence.
 * Used by every shadcn/ui primitive.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format a number for an engineering UI cell: tabular figures, fixed
 * decimal places by default, trims trailing zeros after the decimal.
 */
export function fmtNumber(
  value: number,
  opts: { decimals?: number; sigFigs?: number } = {},
): string {
  if (!Number.isFinite(value)) return "—";
  const { decimals, sigFigs } = opts;
  if (typeof sigFigs === "number") {
    return value.toPrecision(sigFigs);
  }
  if (typeof decimals === "number") {
    return value.toFixed(decimals);
  }
  if (Math.abs(value) >= 1000 || (Math.abs(value) < 0.01 && value !== 0)) {
    return value.toExponential(2);
  }
  return value.toFixed(3).replace(/\.?0+$/, "");
}
