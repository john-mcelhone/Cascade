"use client";

import { useMemo, useState } from "react";
import { useTheme } from "next-themes";
import type { Data } from "plotly.js";
import { Slider } from "@/components/ui/slider";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Plot, defaultPlotLayout } from "@/components/plot/plotly-host";
import { WidgetFrame } from "./widget-frame";
import { cn } from "@/lib/utils";

/**
 * Chapter 5 — LossBreakdownExplorer.
 *
 * Three reference loss models, each with plausible per-bucket defaults
 * pulled from the canonical citation. The user picks a model, drags
 * scale-factor sliders (0.5 → 1.5) on each loss bucket, and watches the
 * net stage efficiency update live.
 *
 * The default loss numbers below are *pedagogical*. Real Cascade runs use
 * the canonical correlation evaluators in `cascade.meanline.losses` and
 * carry the citation through the run record. The numbers here are calibrated
 * to add up to a realistic 0.85 ± 0.02 efficiency, so the user sees a
 * plausible figure as a starting point.
 */

interface LossBucket {
  /** Display name of the bucket. */
  name: string;
  /** Default % efficiency penalty for this bucket. */
  defaultPct: number;
  /** Citation source attached to this bucket. */
  citation: string;
  /** Citation body — equation + page, shown in the popover. */
  citationBody: string;
}

interface LossModelDef {
  id: string;
  label: string;
  family: string;
  citation: string;
  buckets: LossBucket[];
}

const MODELS: LossModelDef[] = [
  {
    id: "whitfield-baines",
    label: "Whitfield–Baines 1990",
    family: "Radial-inflow turbine",
    citation:
      "Whitfield, A. & Baines, N. C., Design of Radial Turbomachines, Longman 1990, Ch. 6.",
    buckets: [
      {
        name: "Incidence",
        defaultPct: 1.5,
        citation: "Whitfield & Baines 1990, §6.4.1",
        citationBody:
          "Δh_inc = ½·W₁²·sin²(β₁,flow − β₁,blade). Empirical n ≈ 2 for radial-inflow rotors.",
      },
      {
        name: "Profile (passage)",
        defaultPct: 4.2,
        citation: "Whitfield & Baines 1990, §6.4.2 (Rohlik 1968 form)",
        citationBody:
          "Δh_pass = K_p · ½ · ((W₁²+W₂²)/2). K_p ≈ 0.3 from Rohlik NASA TN-D-4384 (1968) fit.",
      },
      {
        name: "Secondary",
        defaultPct: 2.0,
        citation: "Wood 1963 + W&B 1990 §6.4.3",
        citationBody:
          "Δh_sec = K_s · (W₂/U₂)² · (r_2t/r_1)² · ½·U₂². K_s ≈ 0.04–0.10.",
      },
      {
        name: "Tip clearance",
        defaultPct: 2.5,
        citation: "Whitfield & Baines 1990, §6.4.4",
        citationBody:
          "Δh_tip = ½·ρ·(U₂³/8π)·Z·[K_a·ε_a·C_a/b_a + K_r·ε_r·C_r/b_r + K_ar·√(ε_a·ε_r·C_a·C_r/(b_a·b_r))].",
      },
      {
        name: "Trailing-edge",
        defaultPct: 0.8,
        citation: "Whitfield & Baines 1990, §6.4.5 (Glassman 1972)",
        citationBody:
          "Δh_TE includes a mixing loss tied to TE thickness / pitch.",
      },
      {
        name: "Disc friction",
        defaultPct: 0.6,
        citation: "Daily & Nece 1960 + W&B 1990 §6.4.6",
        citationBody:
          "Δh_df = K_df · ρ·U₂³·D₂²/(8·ṁ). K_df from Daily & Nece 1960 chart for the disc Re regime.",
      },
      {
        name: "Recirculation",
        defaultPct: 0.4,
        citation: "Coppage 1956 + W&B 1990 §6.4.7",
        citationBody:
          "Δh_rec = 8e-5·sinh(3.5·α₂′³)·DF²·U₂². Coppage WADC TR-55-257.",
      },
    ],
  },
  {
    id: "aungier",
    label: "Aungier 2000 (centrifugal)",
    family: "Centrifugal compressor",
    citation:
      "Aungier, R. H., Centrifugal Compressors: A Strategy for Aerodynamic Design and Analysis, ASME Press 2000.",
    buckets: [
      {
        name: "Incidence",
        defaultPct: 1.2,
        citation: "Aungier 2000, Eq. 6.41",
        citationBody:
          "Incidence loss bucket calibrated against the Eckardt A/O rotor test database.",
      },
      {
        name: "Profile (skin friction)",
        defaultPct: 4.5,
        citation: "Aungier 2000, Eq. 6.42",
        citationBody:
          "Δh_sf = 4·c_f·L_hyd/D_hyd · ½·W̄². Skin-friction coefficient from Conrad-Raghuram diffuser data.",
      },
      {
        name: "Diffusion (blade loading)",
        defaultPct: 3.0,
        citation: "Aungier 2000, Eq. 6.43",
        citationBody:
          "Blade-loading loss correlated against equivalent diffusion factor (Lieblein 1953).",
      },
      {
        name: "Clearance",
        defaultPct: 2.0,
        citation: "Aungier 2000, Eq. 6.45",
        citationBody:
          "Δh_cl = 0.6·ε/b₂·U₂·V_θ₂. Linear in tip-clearance fraction ε/b₂.",
      },
      {
        name: "Recirculation",
        defaultPct: 0.5,
        citation: "Coppage 1956 (per Aungier §6.7)",
        citationBody:
          "Δh_rec = 8e-5·sinh(3.5·α₂′³)·DF²·U₂². Active above DF ≈ 2.",
      },
      {
        name: "Disc friction",
        defaultPct: 0.7,
        citation: "Daily & Nece 1960 (per Aungier §6.8)",
        citationBody:
          "Δh_df = K_df·ρ·U₂³·D₂²/(8·ṁ); K_df from Daily-Nece regime chart.",
      },
      {
        name: "Mixing (vaneless diffuser)",
        defaultPct: 0.8,
        citation: "Aungier 2000, §6.9",
        citationBody:
          "Mixing between jet and wake at impeller exit; depends on slip + diffuser width.",
      },
    ],
  },
  {
    id: "kacker-okapuu",
    label: "Kacker–Okapuu 1982 (axial)",
    family: "Axial turbine",
    citation:
      "Kacker, S. C. & Okapuu, U., A Mean Line Prediction Method for Axial Flow Turbine Efficiency, ASME J. Eng. Power, Vol. 104, Jan. 1982, pp. 111-119.",
    buckets: [
      {
        name: "Profile (Y_p)",
        defaultPct: 3.2,
        citation: "Kacker–Okapuu 1982, Eq. 6",
        citationBody:
          "Y_p modified from Ainley-Mathieson chart + Mach correction. Form: Y_p = 0.914·(2/3·Y_p,AMDC·K_Re·K_M + ΔY_TE).",
      },
      {
        name: "Secondary (Y_s)",
        defaultPct: 2.6,
        citation: "Kacker–Okapuu 1982, Eq. 8",
        citationBody:
          "Y_s = 1.2·Y_s,AMDC·K_s. AMDC form Y_s = 0.0334·(C_L/s)²·(c/h)·(cos²α₂)/(cos²α_m).",
      },
      {
        name: "Tip clearance (Y_tc)",
        defaultPct: 2.4,
        citation: "Kacker–Okapuu 1982, Eq. 14",
        citationBody:
          "Y_tc = 0.5·(ε/h)·C_L²·(cos²α₂)/(cos²α_m). Shrouded rotor (k=0.37) or unshrouded (k=0.50).",
      },
      {
        name: "Trailing-edge (Y_TE)",
        defaultPct: 0.9,
        citation: "Kacker–Okapuu 1982, Eq. 7 + Fig. 14",
        citationBody:
          "Y_TE = (φ²_TE) · K_M from chart in K-O 1982 Figure 14, function of TE thickness ratio.",
      },
      {
        name: "Shock (Y_shock)",
        defaultPct: 0.7,
        citation: "K-O 1982 Eq. 9 + Moustapha et al. 2003 App. A",
        citationBody:
          "Y_shock active for M₁,rel > 0.4 or M₂ > 1. The 2003 K-O update fixes the original chart.",
      },
      {
        name: "Disc friction",
        defaultPct: 0.4,
        citation: "Daily & Nece 1960 (per K-O §3)",
        citationBody:
          "Windage on the disc back face. Small for axial — large for high-RPM single-stage radials.",
      },
      {
        name: "Cooling (Y_cool)",
        defaultPct: 0.3,
        citation: "Young & Wilcock 2002 (refinement of K-O)",
        citationBody:
          "Cooled-blade penalty. Active above 2% coolant fraction. Deferred to v1.1 — fixed bucket here.",
      },
    ],
  },
];

const DEFAULT_MODEL_ID = "whitfield-baines";

export function LossBreakdownExplorer() {
  const [modelId, setModelId] = useState(DEFAULT_MODEL_ID);
  const model = useMemo(
    () => MODELS.find((m) => m.id === modelId) ?? MODELS[0],
    [modelId],
  );
  const [scales, setScales] = useState<number[]>(() =>
    model.buckets.map(() => 1.0),
  );
  const { resolvedTheme } = useTheme();
  const theme = resolvedTheme === "dark" ? "dark" : "light";

  // Reset scales when the model changes — number of buckets may differ.
  function onModelChange(id: string) {
    setModelId(id);
    const next = MODELS.find((m) => m.id === id);
    if (next) setScales(next.buckets.map(() => 1.0));
  }

  const lossPcts = useMemo(
    () => model.buckets.map((b, i) => b.defaultPct * scales[i]),
    [model.buckets, scales],
  );
  const totalLossPct = useMemo(
    () => lossPcts.reduce((a, b) => a + b, 0),
    [lossPcts],
  );
  const netEta = Math.max(0, 100 - totalLossPct);

  const traces: Data[] = useMemo(() => {
    const palette = [
      "rgb(var(--chart-1))",
      "rgb(var(--chart-2))",
      "rgb(var(--chart-4))",
      "rgb(var(--chart-5))",
      "rgb(var(--chart-6))",
      "rgb(var(--chart-7))",
      "rgb(var(--chart-8))",
      "rgb(var(--chart-9))",
    ];
    const indexed = model.buckets.map((b, i) => ({
      name: b.name,
      pct: lossPcts[i],
      color: palette[i % palette.length],
    }));
    indexed.sort((a, b) => b.pct - a.pct);
    return [
      {
        type: "bar",
        orientation: "h",
        x: indexed.map((b) => b.pct),
        y: indexed.map((b) => b.name),
        marker: { color: indexed.map((b) => b.color) },
        hovertemplate: "%{y}: %{x:.2f} pp<extra></extra>",
      } satisfies Data,
    ];
  }, [model.buckets, lossPcts]);

  const layout = useMemo(
    () => ({
      ...defaultPlotLayout(theme),
      xaxis: {
        ...defaultPlotLayout(theme).xaxis,
        title: { text: "Efficiency penalty, percentage points", standoff: 6 },
      },
      yaxis: {
        ...defaultPlotLayout(theme).yaxis,
        automargin: true,
      },
      bargap: 0.25,
      margin: { l: 110, r: 16, t: 14, b: 50 },
    }),
    [theme],
  );

  return (
    <WidgetFrame
      label="Loss breakdown"
      caption="net η updates as you scale each bucket"
      onReset={() => setScales(model.buckets.map(() => 1.0))}
      bodyHeight="640px"
    >
      <div className="grid h-full grid-cols-1 gap-3 p-3 lg:grid-cols-[320px_1fr]">
        <div className="flex flex-col gap-3 overflow-y-auto pr-1 scrollbar-subtle">
          <div className="flex flex-col gap-1.5">
            <Label className="text-sm">Loss model</Label>
            <Select value={modelId} onValueChange={onModelChange}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {MODELS.map((m) => (
                  <SelectItem key={m.id} value={m.id}>
                    {m.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-text-muted">{model.family}</p>
            <p className="text-[10px] font-mono text-text-muted">
              Source: {model.citation}
            </p>
          </div>

          <div className="h-px bg-border-subtle" />

          <div className="flex flex-col gap-2">
            {model.buckets.map((b, i) => (
              <ScaleRow
                key={b.name}
                bucket={b}
                value={scales[i]}
                effective={lossPcts[i]}
                onChange={(v) => {
                  setScales((curr) => {
                    const out = [...curr];
                    out[i] = v;
                    return out;
                  });
                }}
              />
            ))}
          </div>
        </div>

        <div className="flex min-h-0 flex-col gap-3">
          <div className="grid grid-cols-2 gap-2">
            <Readout
              label="Total loss"
              value={totalLossPct.toFixed(1)}
              unit="pp"
              tone="warning"
            />
            <Readout
              label="Net η"
              value={netEta.toFixed(1)}
              unit="%"
              tone={netEta > 85 ? "good" : "warning"}
            />
          </div>
          <div className="min-h-0 flex-1 rounded-sm border border-border-subtle bg-background">
            <Plot
              data={traces}
              layout={layout}
              config={{ displayModeBar: false, responsive: true }}
            />
          </div>
        </div>
      </div>
    </WidgetFrame>
  );
}

function ScaleRow({
  bucket,
  value,
  effective,
  onChange,
}: {
  bucket: LossBucket;
  value: number;
  effective: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="rounded-sm border border-border-subtle bg-surface-subtle/40 px-2 py-2">
      <div className="flex items-baseline justify-between gap-2">
        <Popover>
          <PopoverTrigger asChild>
            <button
              type="button"
              className="text-left text-sm leading-tight text-text underline decoration-dotted decoration-text-muted/60 underline-offset-4 hover:decoration-brand"
            >
              {bucket.name}
            </button>
          </PopoverTrigger>
          <PopoverContent className="w-80 max-w-[90vw]" sideOffset={4}>
            <div className="flex flex-col gap-2 text-sm">
              <span className="font-medium text-text">{bucket.name}</span>
              <span className="text-xs font-mono text-text-muted">
                {bucket.citation}
              </span>
              <p className="border-t border-border-subtle pt-2 text-sm leading-relaxed text-text-muted">
                {bucket.citationBody}
              </p>
            </div>
          </PopoverContent>
        </Popover>
        <span className="font-mono text-xs tabular-nums text-text-muted">
          {effective.toFixed(2)} pp · ×{value.toFixed(2)}
        </span>
      </div>
      <Slider
        className="mt-2"
        min={0.5}
        max={1.5}
        step={0.01}
        value={[value]}
        onValueChange={(v) => onChange(v[0])}
      />
    </div>
  );
}

function Readout({
  label,
  value,
  unit,
  tone,
}: {
  label: string;
  value: string;
  unit: string;
  tone?: "good" | "warning";
}) {
  return (
    <div className="flex items-baseline justify-between gap-2 rounded-sm border border-border-subtle bg-surface-computed px-2 py-1.5">
      <span className="text-xs text-text-muted">{label}</span>
      <span
        className={cn(
          "font-mono text-md tabular-nums",
          tone === "good"
            ? "text-semantic-success-text"
            : tone === "warning"
              ? "text-semantic-warning-text"
              : "text-text",
        )}
      >
        {value}
        {unit && <span className="ml-1 text-xs text-text-muted">{unit}</span>}
      </span>
    </div>
  );
}
