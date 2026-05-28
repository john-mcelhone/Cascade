import Link from "next/link";
import { BookOpen, FileText, Database, Cog, Wind } from "lucide-react";
import { PageHeader } from "@/components/shell/page-header";
import { Card } from "@/components/ui/card";
import type { LucideIcon } from "lucide-react";

const SECTIONS: Array<{
  title: string;
  href: string;
  blurb: string;
  Icon: LucideIcon;
}> = [
  {
    title: "Validation report",
    href: "/docs/validation",
    blurb:
      "Pass-gate cases against published references. 171 tests, 45 pass-gate-marked, with tolerances per SPEC_SHEET §12.",
    Icon: FileText,
  },
  {
    title: "Cycle solver",
    href: "/docs",
    blurb:
      "Brayton, recuperated Brayton, sCO₂ recompression, intercooled. Per-component equations and convergence guarantees.",
    Icon: Database,
  },
  {
    title: "Loss models",
    href: "/docs",
    blurb:
      "Aungier 2000, Whitfield-Baines, Wood, Soderberg, Stepanov. Each card has the equation, the citation, and a calibration scale slider.",
    Icon: Cog,
  },
  {
    title: "Working fluids",
    href: "/docs",
    blurb:
      "CoolProp wrapper by default; REFPROP optional. The cascade knows the difference between Pt and P at every state.",
    Icon: Wind,
  },
];

export default function DocsPage() {
  return (
    <div className="flex flex-1 flex-col overflow-auto scrollbar-subtle">
      <PageHeader
        breadcrumb={[{ label: "Docs" }]}
        title="Documentation"
        description="The cascade is auditable. Every page here mirrors what runs in the solver."
      />
      <div className="mx-auto w-full max-w-5xl px-5 py-5">
        <div className="grid gap-3 sm:grid-cols-2">
          {SECTIONS.map((s) => (
            <Link key={s.title} href={s.href} className="group block">
              <Card className="flex items-start gap-3 p-4 transition-colors duration-fast hover:border-border-default">
                <div className="rounded-sm border border-border-subtle bg-surface-raised p-2">
                  <s.Icon className="h-4 w-4 text-text-muted" />
                </div>
                <div className="flex-1">
                  <h3 className="text-md font-medium text-text">{s.title}</h3>
                  <p className="mt-1 text-sm text-text-muted">{s.blurb}</p>
                </div>
              </Card>
            </Link>
          ))}
        </div>

        <div className="mt-6 flex items-start gap-3 rounded-md border border-border-subtle bg-surface-subtle/40 p-4">
          <BookOpen className="h-4 w-4 mt-0.5 shrink-0 text-text-muted" />
          <div className="text-sm text-text-muted">
            Full theory manuals, KaTeX-rendered equations, and runnable code
            samples land here as the API surface comes online. For now, see the
            validation report and the public spec sheet.
          </div>
        </div>
      </div>
    </div>
  );
}
