import type { Metadata } from "next";
import "katex/dist/katex.min.css";
import { DocsSidebar } from "@/components/docs";

export const metadata: Metadata = {
  title: {
    default: "Docs",
    template: "%s — Docs — Cascade",
  },
  description:
    "Cascade documentation — guides, scripting and API reference, and the public validation report.",
};

/**
 * The /docs shell. Mirrors the /learn chrome:
 *
 *   ┌────────────────┬────────────────────────────────┐
 *   │ docs rail      │ main column (720 px max)       │
 *   │   240 px       │ + right ToC (sticky, optional) │
 *   └────────────────┴────────────────────────────────┘
 *
 * Each page mounts `<DocPage>` which renders the header, the prose column,
 * the right-rail "On this page" ToC, and prev/next navigation from the
 * docs manifest.
 */
export default function DocsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex w-full flex-1 overflow-hidden">
      <DocsSidebar />
      <div className="flex-1 overflow-auto scrollbar-subtle">{children}</div>
    </div>
  );
}
