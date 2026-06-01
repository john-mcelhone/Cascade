import { cn } from "@/lib/utils";

/**
 * Cascade mark — three descending blades stepping down a slope, evoking both a
 * cascade of flow and the rows of a turbomachine blade row. Rendered in the
 * brand gradient. Paired with the wordmark in Inter 500.
 */
export function CascadeMark({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        "inline-flex h-5 w-5 items-center justify-center rounded-[5px] bg-brand-gradient shadow-z1",
        className,
      )}
    >
      <svg
        viewBox="0 0 16 16"
        fill="none"
        className="h-3.5 w-3.5"
        stroke="white"
        strokeWidth="1.6"
        strokeLinecap="round"
      >
        {/* Three stepping blades — the cascade. */}
        <path d="M3 4.5h7" opacity="0.95" />
        <path d="M4.5 8h7" opacity="0.85" />
        <path d="M6 11.5h7" opacity="0.7" />
      </svg>
    </span>
  );
}

export function Logo({
  className,
  showMark = true,
}: {
  className?: string;
  showMark?: boolean;
}) {
  return (
    <div
      className={cn("inline-flex items-center gap-2 select-none", className)}
    >
      {showMark && <CascadeMark />}
      <span className="text-md font-semibold tracking-tight text-text">
        Cascade
      </span>
    </div>
  );
}
