"use client";

import { useState } from "react";
import { FileText } from "lucide-react";
import { CodeBlock } from "./code-block";
import { cn } from "@/lib/utils";

export interface FileTab {
  /** Display name, e.g. "microturbine-30kw.cascade.toml". */
  name: string;
  lang: string;
  code: string;
  /** Short note shown above the code for this file. */
  note?: string;
}

/**
 * A small file browser: file list on the left, content on the right.
 * Used to walk through multi-file artifacts like a project directory
 * without stacking five code blocks.
 */
export function FileTreeTabs({
  label,
  files,
  className,
}: {
  label: string;
  files: FileTab[];
  className?: string;
}) {
  const [active, setActive] = useState(0);
  const file = files[Math.min(active, files.length - 1)];

  return (
    <figure
      className={cn(
        "w-full overflow-hidden rounded-md border border-border-subtle bg-surface-raised",
        className,
      )}
    >
      <header className="flex items-baseline gap-2 border-b border-border-subtle bg-surface-subtle/60 px-3 py-2">
        <span className="text-xs font-medium uppercase tracking-wide text-text-muted">
          Files
        </span>
        <span className="font-mono text-sm font-medium text-text">{label}</span>
      </header>
      <div className="flex flex-col sm:flex-row">
        <div className="flex shrink-0 flex-row gap-0.5 overflow-x-auto border-b border-border-subtle p-1.5 scrollbar-subtle sm:w-56 sm:flex-col sm:border-b-0 sm:border-r">
          {files.map((f, i) => (
            <button
              key={f.name}
              type="button"
              onClick={() => setActive(i)}
              className={cn(
                "flex items-center gap-1.5 whitespace-nowrap rounded-sm px-2 py-1.5 text-left font-mono text-xs transition-colors duration-fast",
                i === active
                  ? "bg-brand-surface font-medium text-brand-text"
                  : "text-text-muted hover:bg-surface-subtle hover:text-text",
              )}
            >
              <FileText className="h-3 w-3 shrink-0" />
              <span className="truncate">{f.name}</span>
            </button>
          ))}
        </div>
        <div className="min-w-0 flex-1">
          {file.note && (
            <p className="border-b border-border-subtle px-3.5 py-2 text-xs leading-relaxed text-text-muted">
              {file.note}
            </p>
          )}
          <CodeBlock
            code={file.code}
            lang={file.lang}
            bare
            className="rounded-none border-0"
          />
        </div>
      </div>
    </figure>
  );
}
