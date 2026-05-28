"use client";

import { use } from "react";
import { PageHeader } from "@/components/shell/page-header";
import { useProject, useProjectDisplayName } from "@/lib/api/hooks";
import { FlowPathLayout } from "@/components/flowpath/flowpath-layout";
import { ParameterTable } from "@/components/flowpath/parameter-table";
import { DesignScatter } from "@/components/flowpath/design-scatter";
import { ImpellerViewer } from "@/components/flowpath/impeller-viewer";
import { ExploreRunner } from "@/components/flowpath/explore-runner";
import { ManufacturabilityPanel } from "@/components/flowpath/manufacturability-panel";

interface PageProps {
  params: Promise<{ id: string }>;
}

/**
 * Flow Path Preliminary Design page — the hero page.
 *
 * Three resizable panes:
 *   1. Parameter table + loss-model picker
 *   2. Design-space scatter (Plotly) + parallel coordinates
 *   3. Live React Three Fiber impeller viewer
 *
 * Wired to the FastAPI server at `/api/projects/:id/explore` (SSE
 * streaming candidates) and `/api/candidates/:cid/geometry?lod=…` (glTF
 * binary). Falls back to polling + a procedural placeholder mesh when
 * the server is unavailable so the page still reads well in dev.
 */
export default function FlowPathPage({ params }: PageProps) {
  const { id } = use(params);
  const { data: project } = useProject(id);
  const projectName = useProjectDisplayName(id);

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        breadcrumb={[
          { label: "Projects", href: "/projects" },
          { label: projectName, href: `/projects/${id}` },
          { label: "Flow path" },
        ]}
        title="Flow path"
        description="Sweep a parameter range. Pick a candidate. The geometry and operating point land in roughly two hundred milliseconds."
        actions={<ExploreRunner projectId={id} />}
      />

      <div className="flex flex-1 overflow-hidden">
        <FlowPathLayout
          left={
            <div className="flex h-full flex-col">
              <ManufacturabilityPanel projectId={id} />
              <div className="min-h-0 flex-1 overflow-auto">
                <ParameterTable projectId={id} />
              </div>
            </div>
          }
          centre={<DesignScatter projectId={id} />}
          right={<ImpellerViewer />}
        />
      </div>
    </div>
  );
}
