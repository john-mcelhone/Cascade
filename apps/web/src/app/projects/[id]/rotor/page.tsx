"use client";

import { use, useCallback, useEffect, useMemo, useState } from "react";
import { Download, Loader2, Play } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shell/page-header";
import { RightRail } from "@/components/shell/right-rail";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BearingEditor } from "@/components/rotor/bearing-editor";
import { BodePlot } from "@/components/rotor/bode-plot";
import { CampbellDiagram } from "@/components/rotor/campbell-diagram";
import { CompliancePanel } from "@/components/rotor/compliance-panel";
import { CriticalSpeedMap } from "@/components/rotor/critical-speed-map";
import { ModeShapes } from "@/components/rotor/mode-shapes";
import {
  RotorSketch,
  bearingsFromShape,
  type BearingDef,
} from "@/components/rotor/rotor-sketch";
import { StabilityChart } from "@/components/rotor/stability-chart";
import { ApiError, getApiClient } from "@/lib/api/client";
import {
  useProject,
  useProjectDisplayName,
  useRotorShape,
} from "@/lib/api/hooks";
import type {
  RotorAnalysisKind,
  RotorBearingPayload,
  RotorCampbellPayload,
  RotorComplianceReport,
  RotorCriticalSpeedMapPayload,
  RotorMode,
  RotorResultBackend,
} from "@/lib/api/types";
import { fmtNumber } from "@/lib/utils";

interface PageProps {
  params: Promise<{ id: string }>;
}

/**
 * Rotor dynamics page. Top pane shows the rotor sketch + bearings; clicking
 * a bearing pops the K-C editor in the right rail. Bottom pane is a tabbed
 * set of result plots. All five runs (Lateral / Torsional / Critical-speed
 * map / Campbell / Unbalance) post to the same `/rotor` endpoint with
 * different `analysis` enums and poll the job to completion.
 */
export default function RotorPage({ params }: PageProps) {
  const { id } = use(params);
  const { data: project } = useProject(id);
  const projectName = useProjectDisplayName(id);
  const { data: shape } = useRotorShape(id);

  const [bearings, setBearings] = useState<BearingDef[]>([]);
  const [selectedBearingId, setSelectedBearingId] = useState<string | undefined>(
    undefined,
  );
  const [modes, setModes] = useState<RotorMode[]>([]);
  const [campbell, setCampbell] = useState<RotorCampbellPayload | undefined>();
  const [csmPayload, setCsmPayload] = useState<
    RotorCriticalSpeedMapPayload | undefined
  >();
  const [compliance, setCompliance] = useState<
    RotorComplianceReport | undefined
  >();
  const [speedRangeRpm, setSpeedRangeRpm] = useState<[number, number]>([
    1000, 60000,
  ]);
  const [running, setRunning] = useState<RotorAnalysisKind | null>(null);
  const [lastAnalysis, setLastAnalysis] = useState<string | null>(null);
  const [downloadingPdf, setDownloadingPdf] = useState(false);

  // Seed bearings from shape on first load.
  useEffect(() => {
    if (!shape) return;
    if (bearings.length === 0 && shape.sections.length > 0) {
      const b = bearingsFromShape(shape);
      setBearings(b);
      if (!selectedBearingId && b[0]) setSelectedBearingId(b[0].id);
    }
  }, [shape, bearings.length, selectedBearingId]);

  const selectedBearing = useMemo(
    () => bearings.find((b) => b.id === selectedBearingId),
    [bearings, selectedBearingId],
  );

  const updateBearing = useCallback(
    (next: BearingDef) => {
      setBearings((cur) => cur.map((b) => (b.id === next.id ? next : b)));
    },
    [],
  );

  const runAnalysis = useCallback(
    async (kind: RotorAnalysisKind) => {
      setRunning(kind);
      const api = getApiClient();
      try {
        const accepted = await api.runRotor(id, {
          analysis: kind,
          speed_range_rpm: speedRangeRpm,
          n_modes: 6,
          bearings: bearings.map(serializeBearing),
        });
        const final = await api.waitForJob(accepted.job_id, 20_000);
        if (final.status !== "done") {
          throw new ApiError(
            500,
            final.error ?? `Rotor analysis ${final.status}.`,
          );
        }
        const result = final.result as RotorResultBackend | undefined;
        if (result?.modes) {
          setModes(result.modes);
          setCampbell(result.campbell);
          setCsmPayload(result.critical_speed_map);
          setCompliance(result.compliance);
          setLastAnalysis(result.analysis ?? kind);
          const failing =
            result.compliance?.criticals.filter((c) => !c.passes).length ?? 0;
          if (failing > 0) {
            toast.warning(
              `${labelFor(kind)} complete · ${failing} API 684 fail${failing > 1 ? "s" : ""}.`,
              {
                description: `${result.modes.length} modes returned; check the compliance panel.`,
              },
            );
          } else {
            toast.success(`${labelFor(kind)} complete.`, {
              description: `${result.modes.length} modes returned.`,
            });
          }
        } else {
          toast.warning(`${labelFor(kind)} returned no modes.`);
        }
      } catch (err) {
        const msg = err instanceof ApiError ? err.message : String(err);
        toast.error(`${labelFor(kind)} failed.`, { description: msg });
      } finally {
        setRunning(null);
      }
    },
    [bearings, id, speedRangeRpm],
  );

  /** Download the PDF compliance report for this project. */
  const downloadPdfReport = useCallback(async () => {
    setDownloadingPdf(true);
    try {
      const { getApiBaseUrl } = await import("@/lib/api/client");
      const url = `${getApiBaseUrl()}/api/projects/${encodeURIComponent(id)}/rotor/report.pdf`;
      const res = await fetch(url, { credentials: "include" });
      if (!res.ok) {
        throw new Error(`PDF request failed: HTTP ${res.status}`);
      }
      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = `rotor-report-${id}.pdf`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(objectUrl);
      toast.success("Rotor dynamics report downloaded.");
    } catch (err) {
      toast.error("PDF download failed.", {
        description: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setDownloadingPdf(false);
    }
  }, [id]);

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        breadcrumb={[
          { label: "Projects", href: "/projects" },
          { label: projectName, href: `/projects/${id}` },
          { label: "Rotor" },
        ]}
        title="Rotor dynamics"
        description="Lumped-disk rotor with bearings. Critical speeds, Campbell, mode shapes, Bode, and stability all run from the same sketch."
        actions={
          <>
            <Button
              variant="outline"
              disabled={running !== null}
              onClick={() => runAnalysis("lateral")}
            >
              {running === "lateral" ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : null}{" "}
              Lateral
            </Button>
            <Button
              variant="outline"
              disabled={running !== null}
              onClick={() => runAnalysis("torsional")}
            >
              {running === "torsional" ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : null}{" "}
              Torsional
            </Button>
            <Button
              className="gap-2"
              disabled={running !== null}
              onClick={() => runAnalysis("critical_speed_map")}
            >
              {running === "critical_speed_map" ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Play className="h-3 w-3" />
              )}
              Critical-speed map
            </Button>
            <Button
              variant="outline"
              className="gap-2"
              disabled={downloadingPdf || running !== null || modes.length === 0}
              title={
                modes.length === 0
                  ? "Run a lateral analysis first to generate the compliance report."
                  : "Download API 684 compliance report (PDF)"
              }
              onClick={downloadPdfReport}
            >
              {downloadingPdf ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Download className="h-3 w-3" />
              )}
              PDF report
            </Button>
          </>
        }
      />

      <div className="flex flex-1 overflow-hidden">
        <div className="flex flex-1 flex-col overflow-hidden">
          {/* Top pane: rotor sketch (60% height) */}
          <div className="basis-3/5 overflow-auto scrollbar-subtle p-5">
            <Card className="p-3">
              <div className="mb-2 flex items-baseline justify-between">
                <h3 className="text-xs font-medium uppercase tracking-wide text-text-muted">
                  Rotor sketch
                </h3>
                <span className="text-xs text-text-muted">
                  Click a bearing to edit its K · C
                </span>
              </div>
              {shape ? (
                <RotorSketch
                  shape={shape}
                  bearings={bearings}
                  selectedBearingId={selectedBearingId}
                  onSelectBearing={setSelectedBearingId}
                />
              ) : (
                <div className="flex h-[140px] items-center justify-center text-xs text-text-muted">
                  Loading rotor shape…
                </div>
              )}
              <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Stat label="Total length" value={fmtMm(shape?.totalLength)} />
                <Stat label="Sections" value={String(shape?.sections.length ?? 0)} />
                <Stat label="Bearings" value={String(bearings.length)} />
                <Stat
                  label="Disks"
                  value={String(
                    (shape?.sections ?? []).filter((s) => s.kind === "disk")
                      .length,
                  )}
                />
              </div>
            </Card>
          </div>

          {/* Bottom pane: result plots (40% height) */}
          <div className="basis-2/5 overflow-auto scrollbar-subtle border-t border-border-subtle p-5">
            <Tabs defaultValue="critical">
              <TabsList>
                <TabsTrigger value="critical">Critical-speed map</TabsTrigger>
                <TabsTrigger value="modes">Mode shapes</TabsTrigger>
                <TabsTrigger value="campbell">Campbell</TabsTrigger>
                <TabsTrigger value="bode">Bode (unbalance)</TabsTrigger>
                <TabsTrigger value="stability">Stability</TabsTrigger>
              </TabsList>
              <TabsContent value="critical">
                <PlotShell>
                  {csmPayload || modes.length > 0 ? (
                    <CriticalSpeedMap csm={csmPayload} modes={modes} />
                  ) : (
                    <PlotPlaceholder
                      label="Run any analysis to populate the critical-speed map."
                      running={running !== null}
                    />
                  )}
                </PlotShell>
              </TabsContent>
              <TabsContent value="modes">
                <PlotShell>
                  {modes.length > 0 && shape ? (
                    <ModeShapes modes={modes} shape={shape} />
                  ) : (
                    <PlotPlaceholder
                      label="Mode shapes are derived from the latest run."
                      running={running !== null}
                    />
                  )}
                </PlotShell>
              </TabsContent>
              <TabsContent value="campbell">
                <PlotShell>
                  {campbell || modes.length > 0 ? (
                    <CampbellDiagram
                      campbell={campbell}
                      modes={modes}
                      speedRangeRpm={speedRangeRpm}
                    />
                  ) : (
                    <PlotPlaceholder
                      label="Campbell needs at least one modal run."
                      running={running !== null}
                    />
                  )}
                </PlotShell>
                <div className="mt-3">
                  <CompliancePanel compliance={compliance} />
                </div>
              </TabsContent>
              <TabsContent value="bode">
                <PlotShell>
                  {modes.length > 0 ? (
                    <BodePlot modes={modes} speedRangeRpm={speedRangeRpm} />
                  ) : (
                    <PlotPlaceholder
                      label="Bode plot needs the modal frequencies."
                      running={running !== null}
                    />
                  )}
                </PlotShell>
              </TabsContent>
              <TabsContent value="stability">
                <PlotShell>
                  {modes.length > 0 ? (
                    <StabilityChart
                      modes={modes}
                      speedRangeRpm={speedRangeRpm}
                    />
                  ) : (
                    <PlotPlaceholder
                      label="Log decrement needs the modal damping ratios."
                      running={running !== null}
                    />
                  )}
                </PlotShell>
              </TabsContent>
            </Tabs>
          </div>
        </div>

        <RightRail width={320}>
          <div className="flex flex-col gap-5 p-4">
            <section>
              <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-text-muted">
                Bearing properties
              </h3>
              {selectedBearing ? (
                <BearingEditor
                  bearing={selectedBearing}
                  onChange={updateBearing}
                />
              ) : (
                <p className="text-xs text-text-muted">
                  Click a bearing in the sketch.
                </p>
              )}
              {bearings.length > 1 && (
                <ul className="mt-2 flex flex-col gap-1 text-xs">
                  {bearings.map((b) => (
                    <li key={b.id}>
                      <button
                        type="button"
                        className={`w-full rounded-sm border px-2 py-1 text-left font-mono ${
                          b.id === selectedBearingId
                            ? "border-brand bg-brand-surface text-brand-text"
                            : "border-border-subtle bg-surface text-text"
                        }`}
                        onClick={() => setSelectedBearingId(b.id)}
                      >
                        {b.label ?? b.id} · K_yy = {b.K_yy.toExponential(2)}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <section>
              <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-text-muted">
                Run controls
              </h3>
              <div className="rounded-md border border-border-subtle bg-surface px-3 py-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-text-muted">Speed range</span>
                  <span className="tabular-nums">
                    {speedRangeRpm[0].toLocaleString()} –{" "}
                    {speedRangeRpm[1].toLocaleString()} rpm
                  </span>
                </div>
                <div className="mt-1 flex justify-between">
                  <span className="text-text-muted">Last analysis</span>
                  <span className="tabular-nums">{lastAnalysis ?? "—"}</span>
                </div>
                <div className="mt-1 flex justify-between">
                  <span className="text-text-muted">Modes</span>
                  <span className="tabular-nums">{modes.length}</span>
                </div>
              </div>
              <div className="mt-2 grid grid-cols-2 gap-2">
                <SpeedField
                  label="min rpm"
                  value={speedRangeRpm[0]}
                  onChange={(n) => setSpeedRangeRpm([n, speedRangeRpm[1]])}
                />
                <SpeedField
                  label="max rpm"
                  value={speedRangeRpm[1]}
                  onChange={(n) => setSpeedRangeRpm([speedRangeRpm[0], n])}
                />
              </div>
            </section>
            {modes.length > 0 && (
              <section>
                <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-text-muted">
                  Modes
                </h3>
                <ul className="flex flex-col gap-0.5 text-xs">
                  {modes.map((m, i) => (
                    <li
                      key={m.mode_index ?? i}
                      className="flex h-6 items-center border-b border-border-subtle/60 last:border-b-0"
                    >
                      <span className="font-mono text-text-muted">
                        {m.shape_name}
                      </span>
                      <span className="ml-auto font-mono tabular-nums">
                        {fmtNumber(m.frequency_hz, { decimals: 1 })} Hz
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>
        </RightRail>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-sm border border-border-subtle bg-surface px-2 py-1.5">
      <div className="text-[10px] uppercase tracking-wide text-text-muted">
        {label}
      </div>
      <div className="font-mono tabular-nums text-sm">{value}</div>
    </div>
  );
}

function fmtMm(v: number | undefined): string {
  if (v === undefined) return "—";
  if (v < 5) return `${(v * 1000).toFixed(0)} mm`;
  return `${v.toFixed(0)} mm`;
}

function labelFor(kind: RotorAnalysisKind): string {
  switch (kind) {
    case "lateral":
      return "Lateral";
    case "torsional":
      return "Torsional";
    case "critical_speed_map":
      return "Critical-speed map";
    case "campbell":
      return "Campbell";
    case "unbalance":
      return "Unbalance";
  }
}

function PlotShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-3 h-[360px] rounded-md border border-border-subtle bg-surface-subtle/30">
      {children}
    </div>
  );
}

function PlotPlaceholder({
  label,
  running,
}: {
  label: string;
  running: boolean;
}) {
  return (
    <div className="flex h-full w-full items-center justify-center text-xs text-text-muted">
      {running ? (
        <span className="inline-flex items-center gap-2">
          <Loader2 className="h-3 w-3 animate-spin" /> Solving…
        </span>
      ) : (
        <span>{label}</span>
      )}
    </div>
  );
}

function serializeBearing(b: BearingDef): RotorBearingPayload {
  const base: RotorBearingPayload = {
    id: b.id,
    axial_position_mm: b.axialPosition,
    K_yy_n_per_m: b.K_yy,
    K_zz_n_per_m: b.K_zz,
    K_yz_n_per_m: b.K_yz,
    K_zy_n_per_m: b.K_zy,
    C_yy_n_s_per_m: b.C_yy,
    C_zz_n_s_per_m: b.C_zz,
    C_yz_n_s_per_m: b.C_yz,
    C_zy_n_s_per_m: b.C_zy,
  };
  if (b.table && b.table.length >= 2) {
    base.table = b.table.map((r) => ({
      rpm: r.rpm,
      K_yy: r.K_yy,
      K_zz: r.K_zz,
      K_yz: r.K_yz,
      K_zy: r.K_zy,
      C_yy: r.C_yy,
      C_zz: r.C_zz,
      C_yz: r.C_yz,
      C_zy: r.C_zy,
    }));
  }
  return base;
}

function SpeedField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <label className="flex flex-col gap-0.5 text-xs">
      <span className="uppercase tracking-wide text-text-muted">{label}</span>
      <input
        type="number"
        className="h-7 rounded-sm border border-border-default bg-surface-input px-2 text-sm tabular-nums focus:outline-none focus:ring-2 focus:ring-border-focus"
        value={value}
        step={1000}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </label>
  );
}
