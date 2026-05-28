import { cn } from "@/lib/utils";

/**
 * Cascade wordmark. The mark is the word itself rendered in Inter at 500 weight,
 * paired with a small dot in brand teal. No icon mark in v1 — the wordmark is
 * the brand.
 */
export function Logo({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "inline-flex items-center gap-1.5 select-none",
        className,
      )}
    >
      <span
        aria-hidden
        className="h-1.5 w-1.5 rounded-full bg-brand"
      />
      <span className="text-md font-medium tracking-tight text-text">
        Cascade
      </span>
    </div>
  );
}
