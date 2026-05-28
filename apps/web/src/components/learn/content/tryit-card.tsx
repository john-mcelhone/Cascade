import Link from "next/link";
import { ArrowRight, ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";

export interface TryItCardProps {
  /** Destination URL — usually a Cascade deep-link. */
  href: string;
  /** Card title. */
  title: string;
  /** One- or two-sentence body. */
  body?: React.ReactNode;
  /** CTA label. Defaults to "Open in Cascade". */
  cta?: string;
  /** Render the link as an external (new tab) link. */
  external?: boolean;
  className?: string;
}

/**
 * "Try it in Cascade" card. Appears at the end of every section that has a
 * matching feature, deep-linking the reader into the product with the
 * exact concept they just read about.
 */
export function TryItCard({
  href,
  title,
  body,
  cta = "Open in Cascade",
  external,
  className,
}: TryItCardProps) {
  const LinkComp = external ? "a" : Link;
  const externalProps = external
    ? { target: "_blank", rel: "noreferrer" }
    : {};
  return (
    <LinkComp
      href={href}
      {...externalProps}
      className={cn(
        "group flex flex-col gap-3 rounded-md border border-brand/30 bg-brand-surface px-4 py-3 transition-colors duration-fast hover:border-brand",
        className,
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium uppercase tracking-wide text-brand-text">
          Try it in Cascade
        </span>
        {external && <ExternalLink className="h-3 w-3 text-brand-text" aria-hidden />}
      </div>
      <div className="flex flex-col gap-1">
        <span className="text-md font-medium text-text">{title}</span>
        {body && <p className="text-sm text-text-muted">{body}</p>}
      </div>
      <div className="flex items-center gap-1 text-sm font-medium text-brand-text">
        {cta}
        <ArrowRight className="h-3 w-3 transition-transform duration-fast group-hover:translate-x-0.5" aria-hidden />
      </div>
    </LinkComp>
  );
}
