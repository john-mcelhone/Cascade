import type { Metadata } from "next";
import "katex/dist/katex.min.css";
import { LearnSidebar } from "@/components/learn/learn-sidebar";

export const metadata: Metadata = {
  title: {
    default: "Learn",
    template: "%s — Learn — Cascade",
  },
  description:
    "Cascade's introductory tutorial — turbomachinery from first principles, tied to features you can use.",
};

/**
 * The `/learn` shell.
 *
 * Chapter-chrome layout:
 *   ┌────────────────┬────────────────────────────────┐
 *   │ chapter rail   │ main column (720 px max)       │
 *   │   240 px       │ + right ToC (sticky, optional) │
 *   └────────────────┴────────────────────────────────┘
 *
 * The right-rail ToC mounts inside each chapter page via `<ReadingToc>` —
 * we leave the slot here so pages decide whether to show it.
 */
export default function LearnLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex w-full flex-1 overflow-hidden">
      <LearnSidebar />
      <div className="flex-1 overflow-auto scrollbar-subtle">
        {children}
      </div>
    </div>
  );
}
