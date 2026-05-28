import { cn } from "@/lib/utils";

/**
 * Larger lead paragraph in a calmer text color, used right after the
 * chapter header to set up the chapter's central question.
 */
export function Lead({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <p
      className={cn(
        "max-w-2xl text-lg leading-relaxed text-text-muted",
        className,
      )}
    >
      {children}
    </p>
  );
}
