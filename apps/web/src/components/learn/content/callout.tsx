import { AlertTriangle, FlaskConical, Info, Lightbulb } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export type CalloutKind = "example" | "note" | "warning" | "tryit";

interface KindStyle {
  /** Wrapper classes — border + surface. */
  wrap: string;
  /** Icon color class. */
  icon: string;
  /** Label color class. */
  label: string;
  /** Default label when none provided. */
  defaultLabel: string;
  Icon: LucideIcon;
}

const KIND_STYLES: Record<CalloutKind, KindStyle> = {
  example: {
    wrap: "border-semantic-info-border bg-semantic-info-surface",
    icon: "text-semantic-info",
    label: "text-semantic-info-text",
    defaultLabel: "Example",
    Icon: FlaskConical,
  },
  note: {
    wrap: "border-border-subtle bg-surface-subtle",
    icon: "text-text-muted",
    label: "text-text-muted",
    defaultLabel: "Note",
    Icon: Info,
  },
  warning: {
    wrap: "border-semantic-warning-border bg-semantic-warning-surface",
    icon: "text-semantic-warning",
    label: "text-semantic-warning-text",
    defaultLabel: "Heads up",
    Icon: AlertTriangle,
  },
  tryit: {
    wrap: "border-brand/40 bg-brand-surface",
    icon: "text-brand",
    label: "text-brand-text",
    defaultLabel: "Try it",
    Icon: Lightbulb,
  },
};

export interface CalloutProps {
  kind?: CalloutKind;
  /** Header label. Defaults to the kind's canonical label. */
  title?: string;
  children: React.ReactNode;
  className?: string;
}

/** Tinted call-out box with a Lucide icon. */
export function Callout({
  kind = "note",
  title,
  children,
  className,
}: CalloutProps) {
  const style = KIND_STYLES[kind];
  const Icon = style.Icon;
  return (
    <aside
      role={kind === "warning" ? "alert" : "note"}
      className={cn(
        "flex flex-col gap-2 rounded-md border px-4 py-3 text-sm",
        style.wrap,
        className,
      )}
    >
      <div className={cn("flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide", style.label)}>
        <Icon className={cn("h-3.5 w-3.5", style.icon)} aria-hidden />
        <span>{title ?? style.defaultLabel}</span>
      </div>
      <div className="text-md leading-relaxed text-text">{children}</div>
    </aside>
  );
}
