"use client";

import { useCallback, useMemo, useState } from "react";
import { Check, Copy } from "lucide-react";
import { tokenize, TOKEN_CLASS } from "@/lib/docs/highlight";
import { cn } from "@/lib/utils";

export interface CodeBlockProps {
  /** Source code. Leading/trailing blank lines are trimmed. */
  code: string;
  /** Language id: python | bash | toml | json | http | filter | text. */
  lang?: string;
  /** Optional filename / title shown in the header bar. */
  title?: string;
  /** Hide the header bar entirely (still shows a floating copy button). */
  bare?: boolean;
  /** Lines to tint (1-based), e.g. the line a paragraph is discussing. */
  highlightLines?: number[];
  className?: string;
}

const LANG_LABEL: Record<string, string> = {
  python: "Python",
  py: "Python",
  bash: "Shell",
  sh: "Shell",
  shell: "Shell",
  toml: "TOML",
  json: "JSON",
  http: "HTTP",
  filter: "Filter DSL",
  text: "Text",
};

/**
 * The docs code block: header bar with filename + language + copy button,
 * line-by-line highlighting via the local tokenizer, optional tinted lines.
 * Dark "terminal" surface in both themes so code reads as one artifact.
 */
export function CodeBlock({
  code,
  lang = "text",
  title,
  bare = false,
  highlightLines,
  className,
}: CodeBlockProps) {
  const cleaned = useMemo(() => code.replace(/^\n+|\s+$/g, ""), [code]);
  const lines = useMemo(() => cleaned.split("\n"), [cleaned]);
  const highlighted = useMemo(() => new Set(highlightLines ?? []), [highlightLines]);

  const [copied, setCopied] = useState(false);
  const onCopy = useCallback(() => {
    navigator.clipboard
      .writeText(cleaned)
      .then(() => {
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1600);
      })
      .catch(() => {
        /* clipboard unavailable — leave the button as-is */
      });
  }, [cleaned]);

  const copyButton = (
    <button
      type="button"
      onClick={onCopy}
      aria-label={copied ? "Copied" : "Copy code"}
      className={cn(
        "inline-flex h-6 items-center gap-1 rounded-sm border px-1.5 text-[11px] font-medium transition-colors duration-fast",
        copied
          ? "border-semantic-success-border bg-semantic-success-surface text-semantic-success-text"
          : "border-border-subtle bg-surface text-text-muted hover:border-border-default hover:text-text",
      )}
    >
      {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
      {copied ? "Copied" : "Copy"}
    </button>
  );

  return (
    <figure
      className={cn(
        "group relative w-full overflow-hidden rounded-md border border-border-subtle bg-surface-raised",
        className,
      )}
    >
      {!bare && (
        <figcaption className="flex items-center justify-between gap-2 border-b border-border-subtle bg-surface-subtle/60 px-3 py-1.5">
          <div className="flex min-w-0 items-baseline gap-2">
            {title && (
              <span className="truncate font-mono text-xs text-text">{title}</span>
            )}
            <span className="shrink-0 text-[11px] uppercase tracking-wide text-text-muted">
              {LANG_LABEL[lang] ?? lang}
            </span>
          </div>
          {copyButton}
        </figcaption>
      )}
      {bare && (
        <div className="absolute right-2 top-2 z-10 opacity-0 transition-opacity duration-fast group-hover:opacity-100">
          {copyButton}
        </div>
      )}
      <pre className="overflow-x-auto px-0 py-2.5 text-[13px] leading-relaxed scrollbar-subtle">
        <code className="block font-mono">
          {lines.map((line, i) => (
            <span
              key={i}
              className={cn(
                "block px-3.5",
                highlighted.has(i + 1) && "bg-brand-surface/70",
              )}
            >
              {tokenize(line, lang).map((tok, j) =>
                tok.type === "plain" ? (
                  <span key={j}>{tok.text}</span>
                ) : (
                  <span key={j} className={TOKEN_CLASS[tok.type]}>
                    {tok.text}
                  </span>
                ),
              )}
              {line === "" ? " " : null}
            </span>
          ))}
        </code>
      </pre>
    </figure>
  );
}
