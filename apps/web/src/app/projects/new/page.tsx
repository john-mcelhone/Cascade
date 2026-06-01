"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Wind, Flame, Network, Gauge, Check } from "lucide-react";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { CoachMark } from "@/components/coach/coach-mark";

type Template = {
  id: string;
  name: string;
  blurb: string;
  Icon: typeof Wind;
  /** Which mock project we route to as the demo destination. */
  routeTo: string;
};

const TEMPLATES: Template[] = [
  {
    id: "microturbine",
    name: "Recuperated microturbine",
    blurb:
      "Single-shaft Brayton cycle with a recuperator. Centrifugal compressor + radial-inflow turbine. The canonical first project.",
    Icon: Flame,
    routeTo: "microturbine-30kw",
  },
  {
    id: "sco2-loop",
    name: "sCO₂ test loop",
    blurb:
      "Recompression supercritical-CO₂ cycle. Real fluid properties via REFPROP wrapper. 600 kW test loop.",
    Icon: Wind,
    routeTo: "sco2-test-loop",
  },
  {
    id: "radial-turbine",
    name: "Radial-inflow turbine",
    blurb:
      "Single-stage radial turbine, 100 kW class. Inlet cascade + volute + rotor + diffuser.",
    Icon: Gauge,
    routeTo: "microturbine-30kw",
  },
  {
    id: "axial-stage",
    name: "Two-stage axial — v1.1",
    blurb:
      "Axial mean-line through-flow is planned for v1.1 and is not implemented in v1 (see KNOWN_GAPS KG-AXT-01). Opens a preview workspace.",
    Icon: Network,
    routeTo: "aero-demonstrator",
  },
];

export default function NewProjectPage() {
  const router = useRouter();
  const [picked, setPicked] = useState<Template | null>(null);

  function onCreate() {
    if (!picked) return;
    // Mock: route to the existing demo project that maps to this template.
    router.push(`/projects/${picked.routeTo}`);
  }

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        breadcrumb={[{ label: "Projects", href: "/projects" }, { label: "New" }]}
        title="New project"
        description="Pick a template. You can edit every parameter once the project opens; the template only sets the initial deck."
        actions={
          <div className="flex items-center gap-2">
            <Button variant="ghost" onClick={() => router.back()}>
              Cancel
            </Button>
            <Button onClick={onCreate} disabled={!picked}>
              Create project
            </Button>
          </div>
        }
      />

      <div className="flex-1 overflow-auto scrollbar-subtle px-5 py-5">
        <div className="mb-4">
          <CoachMark id="new-project-pick" title="Pick a starting point.">
            A template just pre-fills the deck so you&apos;re not staring at a
            blank canvas — every parameter is still yours to change once the
            project opens. The <strong>recuperated microturbine</strong> is the
            best first project.
          </CoachMark>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {TEMPLATES.map((t) => {
            const active = picked?.id === t.id;
            return (
              <Card
                key={t.id}
                onClick={() => setPicked(t)}
                role="button"
                tabIndex={0}
                aria-pressed={active}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setPicked(t);
                  }
                }}
                className={`relative cursor-pointer p-4 transition-all duration-medium ease-out hover:-translate-y-0.5 hover:shadow-z2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus ${
                  active
                    ? "border-brand bg-brand-surface/40 ring-1 ring-brand"
                    : "hover:border-border-default"
                }`}
              >
                {active && (
                  <span className="absolute right-3 top-3 flex h-5 w-5 items-center justify-center rounded-full bg-brand text-text-inverse">
                    <Check className="h-3 w-3" />
                  </span>
                )}
                <div className="flex items-start gap-3">
                  <div
                    className={`flex h-9 w-9 items-center justify-center rounded-lg transition-colors ${
                      active
                        ? "bg-brand-gradient text-text-inverse shadow-z1"
                        : "border border-border-subtle bg-surface-subtle text-text-subtle"
                    }`}
                  >
                    <t.Icon className="h-4 w-4" />
                  </div>
                  <div className="flex-1 pr-6">
                    <h3 className="text-md font-semibold tracking-tight text-text">
                      {t.name}
                    </h3>
                    <p className="mt-1 text-sm leading-relaxed text-text-muted">
                      {t.blurb}
                    </p>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}
