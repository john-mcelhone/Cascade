"use client";

import * as React from "react";
import { use } from "react";
import { Save } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import {
  useCycle,
  useProject,
  useProjectDisplayName,
} from "@/lib/api/hooks";
import { getApiClient } from "@/lib/api/client";
import { CycleCanvas } from "@/components/cycle/cycle-canvas";

interface PageProps {
  params: Promise<{ id: string }>;
}

/**
 * Cycle Canvas — React Flow node graph with custom typed nodes, palette,
 * properties panel, run button, and live h-s diagram. Auto-saves
 * component edits; manual "Save deck" creates a project version
 * snapshot.
 */
export default function CyclePage({ params }: PageProps) {
  const { id } = use(params);
  const { data: project } = useProject(id);
  const projectName = useProjectDisplayName(id);
  const { data: cycle, isLoading } = useCycle(id);

  const onSaveVersion = async () => {
    try {
      const api = getApiClient();
      const { versionId } = await api.saveCycleVersion(id);
      toast.success("Deck snapshotted.", { description: versionId });
    } catch (err) {
      toast.error("Could not save", {
        description: (err as Error).message,
      });
    }
  };

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        breadcrumb={[
          { label: "Projects", href: "/projects" },
          { label: projectName, href: `/projects/${id}` },
          { label: "Cycle" },
        ]}
        title="Cycle"
        description="Drag components from the palette. Connect their ports. When a cycle is well-formed, run it."
        actions={
          <Button
            variant="outline"
            className="gap-2"
            onClick={onSaveVersion}
          >
            <Save className="h-3 w-3" /> Save deck
          </Button>
        }
      />

      <div className="flex flex-1 overflow-hidden">
        {isLoading || !cycle ? (
          <div className="flex flex-1 items-center justify-center text-sm text-text-muted">
            Loading the cycle…
          </div>
        ) : (
          <CycleCanvas
            projectId={id}
            project={project}
            initialNodes={cycle.nodes}
            initialEdges={cycle.edges}
          />
        )}
      </div>
    </div>
  );
}
