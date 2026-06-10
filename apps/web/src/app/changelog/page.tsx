import type { Metadata } from "next";
import { PageHeader } from "@/components/shell/page-header";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import {
  CATEGORY_LABEL,
  CHANGELOG,
  type ChangeCategory,
} from "@/lib/changelog";

export const metadata: Metadata = {
  title: "Changelog",
  description: "Every update shipped to Cascade, newest first.",
};

const CATEGORY_VARIANT: Record<ChangeCategory, BadgeProps["variant"]> = {
  release: "brand",
  feature: "success",
  fix: "warning",
  design: "info",
  docs: "default",
};

/** Render an ISO yyyy-mm-dd date as e.g. "Jun 10, 2026" (UTC, no drift). */
function formatDate(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-US", {
    timeZone: "UTC",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default function ChangelogPage() {
  return (
    <div className="flex flex-1 flex-col overflow-auto scrollbar-subtle">
      <PageHeader
        breadcrumb={[{ label: "Changelog" }]}
        title="Changelog"
        description="Every update shipped to Cascade, newest first."
      />
      <div className="mx-auto w-full max-w-3xl px-5 py-6">
        <ol className="relative border-l border-border-subtle">
          {CHANGELOG.map((entry) => (
            <li
              key={`${entry.date}-${entry.title}`}
              className="relative pb-8 pl-6 last:pb-2"
            >
              {/* Timeline dot */}
              <span
                aria-hidden
                className="absolute -left-[5px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-brand bg-surface"
              />

              <div className="flex flex-wrap items-center gap-2">
                <time
                  dateTime={entry.date}
                  className="font-mono text-xs tabular-nums text-text-muted"
                >
                  {formatDate(entry.date)}
                </time>
                <Badge variant={CATEGORY_VARIANT[entry.category]}>
                  {CATEGORY_LABEL[entry.category]}
                </Badge>
                {entry.pr != null && (
                  <a
                    href={`https://github.com/john-mcelhone/Cascade/pull/${entry.pr}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-text-muted underline-offset-4 hover:text-text hover:underline"
                  >
                    PR #{entry.pr}
                  </a>
                )}
              </div>

              <h2 className="mt-1.5 text-md font-medium text-text">
                {entry.title}
              </h2>
              <p className="mt-1 max-w-prose text-sm text-text-muted">
                {entry.summary}
              </p>

              {entry.details && entry.details.length > 0 && (
                <ul className="mt-2 max-w-prose list-disc space-y-1 pl-4 text-sm text-text-muted marker:text-text-subtle">
                  {entry.details.map((d) => (
                    <li key={d}>{d}</li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
