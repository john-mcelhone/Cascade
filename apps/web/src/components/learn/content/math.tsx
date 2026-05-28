import { BlockMath, InlineMath } from "react-katex";
import { cn } from "@/lib/utils";

export interface MathProps {
  /**
   * TeX source. Accepts a single string or an array of strings (JSX
   * sometimes splits content with embedded braces into multiple children);
   * arrays are joined before they reach KaTeX.
   */
  children: string | string[];
  className?: string;
}

function joinChildren(c: string | string[]): string {
  return Array.isArray(c) ? c.join("") : c;
}

/**
 * Block-display math. Wraps `react-katex`'s `<BlockMath>`. SSR-safe — KaTeX
 * itself renders on the server; we just provide a styled container.
 */
export function Math({ children, className }: MathProps) {
  return (
    <div
      className={cn(
        "overflow-x-auto rounded-md border border-border-subtle bg-surface-subtle/40 px-4 py-3 text-text",
        className,
      )}
    >
      <BlockMath math={joinChildren(children)} />
    </div>
  );
}

/** Inline math; intended to be dropped inside a paragraph. */
export function Inline({
  children,
  className,
}: {
  children: string | string[];
  className?: string;
}) {
  return (
    <span className={cn("text-text", className)}>
      <InlineMath math={joinChildren(children)} />
    </span>
  );
}
