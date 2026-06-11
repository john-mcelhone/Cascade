import { cn } from "@/lib/utils";

type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

const METHOD_TONE: Record<HttpMethod, string> = {
  GET: "border-semantic-info-border bg-semantic-info-surface text-semantic-info-text",
  POST: "border-semantic-success-border bg-semantic-success-surface text-semantic-success-text",
  PUT: "border-semantic-warning-border bg-semantic-warning-surface text-semantic-warning-text",
  PATCH: "border-semantic-warning-border bg-semantic-warning-surface text-semantic-warning-text",
  DELETE: "border-semantic-danger-border bg-semantic-danger-surface text-semantic-danger-text",
};

export interface EndpointProps {
  method: HttpMethod;
  path: string;
  /** One-line summary shown right of the path on wide screens. */
  summary?: string;
  className?: string;
}

/** A REST endpoint signature: method chip + monospace path. */
export function Endpoint({ method, path, summary, className }: EndpointProps) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-2 rounded-md border border-border-subtle bg-surface-raised px-3 py-2",
        className,
      )}
    >
      <span
        className={cn(
          "rounded-sm border px-1.5 py-px font-mono text-[11px] font-semibold",
          METHOD_TONE[method],
        )}
      >
        {method}
      </span>
      <code className="font-mono text-[13px] text-text">{path}</code>
      {summary && (
        <span className="ml-auto hidden text-xs text-text-muted sm:inline">
          {summary}
        </span>
      )}
    </div>
  );
}

export interface EndpointListProps {
  children: React.ReactNode;
  className?: string;
}

/** Tight vertical stack of `<Endpoint>` rows. */
export function EndpointList({ children, className }: EndpointListProps) {
  return <div className={cn("flex flex-col gap-1.5", className)}>{children}</div>;
}
