"use client";

import { use } from "react";
import Link from "next/link";
import { PageHeader } from "@/components/shell/page-header";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { useProject, useProjectDisplayName, useRuns } from "@/lib/api/hooks";
import { fmtNumber } from "@/lib/utils";
import { ArrowUpRight, ListOrdered } from "lucide-react";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function RunsPage({ params }: PageProps) {
  const { id } = use(params);
  const { data: project } = useProject(id);
  const projectName = useProjectDisplayName(id);
  const { data: runs = [] } = useRuns(id);

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        breadcrumb={[
          { label: "Projects", href: "/projects" },
          { label: projectName, href: `/projects/${id}` },
          { label: "Runs" },
        ]}
        title="Runs"
        description="Every cycle solve, mean-line analysis, exploration, map, and rotor-dyn run is captured here with its inputs and timing."
      />
      <div className="flex-1 overflow-auto scrollbar-subtle px-5 py-5">
        {runs.length === 0 ? (
          <EmptyState
            Icon={ListOrdered}
            title="No runs yet."
            description="Open a module and run something. The history lands here with its timing and residual."
          />
        ) : (
          <Card className="overflow-hidden">
            <table className="w-full text-sm">
              <thead className="border-b border-border-subtle bg-surface-subtle text-xs uppercase tracking-wide text-text-muted">
                <tr>
                  <th className="px-3 py-2 text-left font-medium">id</th>
                  <th className="px-3 py-2 text-left font-medium">kind</th>
                  <th className="px-3 py-2 text-left font-medium">status</th>
                  <th className="px-3 py-2 text-left font-medium">summary</th>
                  <th className="px-3 py-2 text-right font-medium">duration</th>
                  <th className="px-3 py-2 text-left font-medium">started</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr
                    key={r.id}
                    className="border-b border-border-subtle/60 hover:bg-surface-subtle/40"
                  >
                    <td className="px-3 py-1.5 font-mono text-xs text-text-muted">
                      {r.id}
                    </td>
                    <td className="px-3 py-1.5 font-medium">{r.kind}</td>
                    <td className="px-3 py-1.5">
                      <Badge
                        variant={
                          r.status === "succeeded"
                            ? "success"
                            : r.status === "failed"
                              ? "danger"
                              : r.status === "cancelled"
                                ? "warning"
                                : "info"
                        }
                      >
                        {r.status}
                        {/* U1 refusal contract: a refused run is `failed`
                            by design, not a crash — qualify the badge. */}
                        {r.refused ? " · refused" : ""}
                      </Badge>
                    </td>
                    <td className="px-3 py-1.5 text-text-muted">
                      {r.summary ?? "—"}
                      {/* U8: explore runs deep-link to their best
                          candidate's detail route. */}
                      {r.kind === "explore" && r.bestCandidateId && (
                        <Link
                          href={`/projects/${id}/flowpath/${encodeURIComponent(r.bestCandidateId)}`}
                          className="ml-2 inline-flex items-center gap-0.5 text-brand-text hover:underline"
                          aria-label={`Open detail for best candidate of run ${r.id}`}
                        >
                          best candidate
                          <ArrowUpRight className="h-3 w-3" aria-hidden />
                        </Link>
                      )}
                    </td>
                    <td className="px-3 py-1.5 text-right font-mono tabular-nums">
                      {typeof r.durationMs === "number"
                        ? `${fmtNumber(r.durationMs)} ms`
                        : "—"}
                    </td>
                    <td className="px-3 py-1.5 font-mono text-xs text-text-muted">
                      {new Date(r.startedAt)
                        .toISOString()
                        .slice(0, 16)
                        .replace("T", " ")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )}
      </div>
    </div>
  );
}
