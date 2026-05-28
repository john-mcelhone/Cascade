"use client";

import { use, useCallback, useEffect, useState } from "react";
import { Loader2, Play } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shell/page-header";
import { RightRail } from "@/components/shell/right-rail";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { ConvergencePlot } from "@/components/analysis/convergence-plot";
import { HsDiagram } from "@/components/analysis/hs-diagram";
import { LossBreakdown } from "@/components/analysis/loss-breakdown";
import { VelocityTriangles } from "@/components/analysis/velocity-triangles";
import { ApiError, getApiClient } from "@/lib/api/client";
import { useProject, useProjectDisplayName } from "@/lib/api/hooks";
import type {
  AnalysisResultBackend,
  LossModelInfo,
} from "@/lib/api/types";
import { fmtNumber } from "@/lib/utils";

interface PageProps {
  params: Promise<{ id: string }>;
}

interface LossScale {
  name: string;
  value: number;
}

export default function AnalysisPage({ params }: PageProps) {
  const { id } = use(params);
  const { data: project } = useProject(id);
  const projectName = useProjectDisplayName(id);

  const [machineClass, setMachineClass] = useState<
    "radial_turbine" | "centrifugal_compressor"
  >("radial_turbine");
  const [lossModelName, setLossModelName] = useState<string>(
    "whitfield-baines-radial-v1",
  );
  const [lossModels, setLossModels] = useState<LossModelInfo[]>([]);
  const [scales, setScales] = useState<LossScale[]>([]);
  const [result, setResult] = useState<AnalysisResultBackend | null>(null);
  const [running, setRunning] = useState(false);
  const [selectedLossBucket, setSelectedLossBucket] = useState<string | null>(
    null,
  );

  // Load the loss-model catalogue once on mount. Used for the right-rail dialog.
  useEffect(() => {
    let cancelled = false;
    getApiClient()
      .listLossModels()
      .then((list) => {
        if (cancelled) return;
        setLossModels(list);
        const selected = list.find((m) => m.name === lossModelName) ?? list[0];
        if (selected) {
          setLossModelName(selected.name);
          const sf = selected.scale_factors ?? {};
          setScales(
            Object.entries(sf).map(([name, v]) => ({
              name,
              value: typeof v === "number" ? v : 1,
            })),
          );
        }
      })
      .catch(() => {
        // backend not running — keep defaults
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectedLossModel = lossModels.find((m) => m.name === lossModelName);

  const onRun = useCallback(async () => {
    setRunning(true);
    setResult(null);
    try {
      const api = getApiClient();
      const accepted = await api.runAnalysis(id, {
        machine_class: machineClass,
        loss_model: lossModelName,
        geometry: {},
        operating_point: {},
      });
      const final = await api.waitForJob(accepted.job_id, 15_000);
      if (final.status !== "done") {
        throw new ApiError(500, final.error ?? `Analysis ${final.status}.`);
      }
      const payload = final.result as AnalysisResultBackend | undefined;
      if (payload) {
        // Surface backend solver errors as toast.error — the result still
        // round-trips so we keep the (empty) chart shells.
        if (payload.error) {
          throw new ApiError(500, payload.error);
        }
        setResult(payload);
        const etaTt = payload.efficiencies?.eta_tt ?? payload.eta_total;
        const etaTs = payload.efficiencies?.eta_ts;
        const etaPiece =
          etaTs !== undefined
            ? `η_tt ${fmtNumber(etaTt, { decimals: 3 })} · η_ts ${fmtNumber(etaTs, { decimals: 3 })}`
            : `η_total ${fmtNumber(etaTt, { decimals: 3 })}`;
        toast.success("Analysis complete.", { description: etaPiece });
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : String(err);
      toast.error("Analysis failed.", { description: msg });
    } finally {
      setRunning(false);
    }
  }, [id, machineClass, lossModelName]);

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        breadcrumb={[
          { label: "Projects", href: "/projects" },
          { label: projectName, href: `/projects/${id}` },
          { label: "Analysis" },
        ]}
        title="1D / 2D analysis"
        description="Mean-line through-flow with the loss model of your choice. Every loss term is cited and tunable."
        actions={
          <Button className="gap-2" disabled={running} onClick={onRun}>
            {running ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <Play className="h-3 w-3" />
            )}
            Run analysis
          </Button>
        }
      />

      <div className="flex flex-1 overflow-hidden">
        {/* Left: parameters */}
        <div className="w-[280px] shrink-0 overflow-auto scrollbar-subtle border-r border-border-subtle bg-surface-subtle/30 px-3 py-3">
          <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-text-muted">
            Machine
          </h3>
          <Select
            value={machineClass}
            onValueChange={(v) =>
              setMachineClass(
                v as "radial_turbine" | "centrifugal_compressor",
              )
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="radial_turbine">Radial turbine</SelectItem>
              <SelectItem value="centrifugal_compressor">
                Centrifugal compressor
              </SelectItem>
            </SelectContent>
          </Select>

          <h3 className="mb-2 mt-4 text-xs font-medium uppercase tracking-wide text-text-muted">
            Operating point
          </h3>
          <ul className="flex flex-col gap-0.5 text-sm">
            <Row k="ṁ" v="0.27 kg/s" />
            <Row k="ω" v="96,000 rpm" />
            <Row k="Pt_in" v="101.3 kPa" />
            <Row k="Tt_in" v="288 K" />
          </ul>

          <h3 className="mb-2 mt-4 text-xs font-medium uppercase tracking-wide text-text-muted">
            Geometry (from picked candidate)
          </h3>
          <ul className="flex flex-col gap-0.5 text-sm">
            <Row k="r_tip_2" v="34.7 mm" />
            <Row k="blade_count" v="11" />
            <Row k="β_2,rel" v="-55°" />
          </ul>

          <h3 className="mb-2 mt-4 text-xs font-medium uppercase tracking-wide text-text-muted">
            Loss model
          </h3>
          <Select value={lossModelName} onValueChange={setLossModelName}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(lossModels.length > 0
                ? lossModels
                : [
                    {
                      name: lossModelName,
                      machine_class: machineClass,
                      citation: "",
                    } as LossModelInfo,
                  ]
              ).map((m) => (
                <SelectItem key={m.name} value={m.name}>
                  {m.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {result && (
            <>
              <h3 className="mb-2 mt-4 text-xs font-medium uppercase tracking-wide text-text-muted">
                Results
              </h3>
              <ul className="flex flex-col gap-0.5 text-sm">
                <Row
                  k="η_tt"
                  v={fmtNumber(
                    result.efficiencies?.eta_tt ?? result.eta_total,
                    { decimals: 4 },
                  )}
                />
                {result.efficiencies?.eta_ts !== undefined && (
                  <Row
                    k="η_ts"
                    v={fmtNumber(result.efficiencies.eta_ts, {
                      decimals: 4,
                    })}
                  />
                )}
                {result.efficiencies?.eta_polytropic !== undefined && (
                  <Row
                    k="η_polytropic"
                    v={fmtNumber(result.efficiencies.eta_polytropic, {
                      decimals: 4,
                    })}
                  />
                )}
                {result.pressure_ratio_tt !== undefined && (
                  <Row
                    k="PR_tt"
                    v={fmtNumber(result.pressure_ratio_tt, { decimals: 3 })}
                  />
                )}
                {result.pressure_ratio_ts !== undefined && (
                  <Row
                    k="PR_ts"
                    v={fmtNumber(result.pressure_ratio_ts, { decimals: 3 })}
                  />
                )}
                {result.work_coefficient !== undefined && (
                  <Row
                    k="Λ_u"
                    v={fmtNumber(result.work_coefficient, { decimals: 3 })}
                  />
                )}
                {result.flow_coefficient !== undefined && (
                  <Row
                    k="φ"
                    v={fmtNumber(result.flow_coefficient, { decimals: 3 })}
                  />
                )}
                {result.max_M_rel !== undefined && (
                  <Row
                    k="M_rel,max"
                    v={fmtNumber(result.max_M_rel, { decimals: 3 })}
                  />
                )}
                {result.power_W !== undefined && (
                  <Row
                    k="power"
                    v={`${fmtNumber(result.power_W / 1000, { decimals: 1 })} kW`}
                  />
                )}
                <Row k="loss_model" v={result.loss_model} />
              </ul>
            </>
          )}
        </div>

        {/* Centre: tabbed plots */}
        <div className="flex-1 overflow-auto scrollbar-subtle p-5">
          <Tabs defaultValue="hs">
            <TabsList>
              <TabsTrigger value="hs">h-s diagram</TabsTrigger>
              <TabsTrigger value="conv">Convergence</TabsTrigger>
              <TabsTrigger value="losses">Loss breakdown</TabsTrigger>
              <TabsTrigger value="vt">Velocity triangles</TabsTrigger>
            </TabsList>
            <TabsContent value="hs">
              <PlotShell>
                <HsDiagram states={result?.h_s_states ?? []} />
              </PlotShell>
            </TabsContent>
            <TabsContent value="conv">
              <PlotShell>
                <ConvergencePlot
                  history={result?.convergence_history ?? []}
                />
              </PlotShell>
            </TabsContent>
            <TabsContent value="losses">
              <PlotShell>
                <LossBreakdown
                  components={result?.loss_breakdown ?? []}
                  onSelectComponent={setSelectedLossBucket}
                />
              </PlotShell>
              {selectedLossBucket && (
                <Card className="mt-3 p-3">
                  <div className="text-xs text-text-muted">Loss bucket</div>
                  <div className="font-mono text-sm">{selectedLossBucket}</div>
                  {selectedLossModel?.citation && (
                    <div className="mt-2 text-xs text-text-muted">
                      {selectedLossModel.citation}
                    </div>
                  )}
                </Card>
              )}
            </TabsContent>
            <TabsContent value="vt">
              <div className="mt-3">
                <VelocityTriangles
                  inlet={result?.velocity_triangles?.inlet}
                  exit={result?.velocity_triangles?.exit}
                />
              </div>
            </TabsContent>
          </Tabs>
        </div>

        {/* Right rail: loss model dialog */}
        <RightRail width={320}>
          <div className="flex flex-col gap-5 p-4">
            <section>
              <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-text-muted">
                Loss model
              </h3>
              <Card className="space-y-1 p-3 text-sm">
                <div className="font-medium">
                  {selectedLossModel?.name ?? lossModelName}
                </div>
                {selectedLossModel?.description && (
                  <div className="text-xs text-text-muted">
                    {selectedLossModel.description.split("\n")[0]}
                  </div>
                )}
                {selectedLossModel?.citation && (
                  <div className="text-xs text-text-muted">
                    {selectedLossModel.citation}
                  </div>
                )}
              </Card>
            </section>
            <section>
              <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-text-muted">
                Scale factors
              </h3>
              {scales.length === 0 ? (
                <p className="text-xs text-text-muted">
                  No tunable scales for this model.
                </p>
              ) : (
                <ul className="flex flex-col gap-3">
                  {scales.map((s, i) => (
                    <li key={s.name} className="flex flex-col gap-1">
                      <div className="flex items-baseline justify-between text-xs">
                        <span className="font-mono">{s.name}</span>
                        <span className="font-mono tabular-nums text-text-muted">
                          ×{s.value.toFixed(2)}
                        </span>
                      </div>
                      <Slider
                        min={0.5}
                        max={1.5}
                        step={0.01}
                        value={[s.value]}
                        onValueChange={(v) => {
                          const next = [...scales];
                          next[i] = { ...s, value: v[0] };
                          setScales(next);
                        }}
                      />
                    </li>
                  ))}
                </ul>
              )}
              {scales.length > 0 && (
                <button
                  type="button"
                  className="mt-2 text-xs text-brand-text underline-offset-2 hover:underline"
                  onClick={() =>
                    setScales(scales.map((s) => ({ ...s, value: 1 })))
                  }
                >
                  Reset to literature defaults
                </button>
              )}
            </section>
          </div>
        </RightRail>
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <li className="flex h-6 items-center gap-2 border-b border-border-subtle/60 last:border-b-0">
      <span className="w-20 truncate font-mono text-xs text-text-muted">
        {k}
      </span>
      <span className="font-mono tabular-nums text-sm">{v}</span>
    </li>
  );
}

function PlotShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-3 h-[420px] rounded-md border border-border-subtle bg-surface-subtle/30">
      {children}
    </div>
  );
}
