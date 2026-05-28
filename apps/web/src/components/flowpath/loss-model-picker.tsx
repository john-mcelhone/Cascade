"use client";

import { useEffect, useState } from "react";
import { BookOpen, ChevronRight } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useFlowPathStore } from "@/lib/flowpath/store";
import { listLossModels, type ServerLossModel } from "@/lib/api/flowpath";

/**
 * Loss model picker. Fetches the catalogue from `/api/loss-models` on
 * mount. Falls back to the bundled FALLBACK_LOSS_MODELS if the API
 * server is unreachable (so the front-end stays reviewable offline).
 *
 * The selected card shows the citation, machine class, and a "(?)"
 * button that opens a dialog with the full citation block, validity
 * envelope, and per-loss-component calibration sliders.
 */
export function LossModelPicker() {
  const lossModelName = useFlowPathStore((s) => s.lossModelName);
  const setLossModel = useFlowPathStore((s) => s.setLossModel);
  const lossScales = useFlowPathStore((s) => s.lossScales);
  const setLossScale = useFlowPathStore((s) => s.setLossScale);

  const [models, setModels] = useState<ServerLossModel[]>([]);

  useEffect(() => {
    let cancelled = false;
    listLossModels().then((m) => {
      if (!cancelled) setModels(m);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const selected =
    models.find((m) => m.name === lossModelName) ??
    models[0] ??
    undefined;

  // Whenever the selected model has scale factors the store doesn't know
  // about yet, seed them with their defaults (1.0).
  useEffect(() => {
    if (!selected) return;
    for (const [key, defVal] of Object.entries(selected.scale_factors ?? {})) {
      if (lossScales[key] === undefined) {
        setLossScale(key, defVal);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected?.name]);

  return (
    <div className="px-2 py-2 space-y-2">
      <Select value={selected?.name} onValueChange={setLossModel}>
        <SelectTrigger aria-label="Loss model" className="h-7">
          <SelectValue placeholder="Choose a loss model…" />
        </SelectTrigger>
        <SelectContent>
          {models.map((m) => (
            <SelectItem key={m.name} value={m.name}>
              {prettifyModelName(m.name)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {selected && (
        <div className="rounded-sm border border-border-subtle bg-surface-subtle/40 p-2 text-xs">
          <div className="mb-1 flex items-center justify-between">
            <Badge variant="brand" className="capitalize">
              {selected.machine_class.replace(/_/g, " ")}
            </Badge>
            <DetailsDialog
              model={selected}
              lossScales={lossScales}
              setLossScale={setLossScale}
            />
          </div>
          <p className="text-text-subtle">{selected.description}</p>
          <p className="mt-1 text-[10px] text-text-muted italic">
            {selected.citation}
          </p>
        </div>
      )}
    </div>
  );
}

function prettifyModelName(name: string): string {
  return name
    .replace(/-/g, " ")
    .replace(/\bv\d+\b/, "")
    .replace(/\b(\w)/g, (m) => m.toUpperCase())
    .trim();
}

interface DetailsDialogProps {
  model: ServerLossModel;
  lossScales: Record<string, number>;
  setLossScale: (component: string, value: number) => void;
}

function DetailsDialog({ model, lossScales, setLossScale }: DetailsDialogProps) {
  const scaleEntries = Object.entries(model.scale_factors ?? {});
  return (
    <Dialog>
      <DialogTrigger asChild>
        <button
          type="button"
          aria-label="Open loss model details"
          className="inline-flex items-center gap-1 rounded-sm px-1 py-px text-[10px] text-text-muted hover:bg-surface-subtle hover:text-text"
        >
          <BookOpen className="h-3 w-3" /> details
        </button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{prettifyModelName(model.name)}</DialogTitle>
          <DialogDescription>
            Mean-line loss model · {model.machine_class.replace(/_/g, " ")}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <Section title="Description">
            <p className="text-sm text-text">{model.description || "—"}</p>
          </Section>

          <Section title="Citation">
            <p className="text-xs italic text-text-subtle">{model.citation}</p>
          </Section>

          <Section title="Loss decomposition (representative)">
            <pre className="overflow-auto rounded-sm border border-border-subtle bg-surface-computed p-2 font-mono text-[11px] leading-relaxed text-text">
              {LOSS_EQUATION_TEX[model.name] ?? DEFAULT_LOSS_EQUATION}
            </pre>
            <p className="mt-1 text-[10px] text-text-muted">
              Rendered as LaTeX source — install <code>katex</code> for symbol
              display.
            </p>
          </Section>

          {Object.keys(model.validity_envelope ?? {}).length > 0 && (
            <Section title="Validity envelope">
              <div className="grid grid-cols-3 gap-2 text-xs font-mono">
                {Object.entries(model.validity_envelope ?? {}).map(([key, val]) => (
                  <div
                    key={key}
                    className="rounded-sm border border-border-subtle bg-surface-subtle/40 px-2 py-1"
                  >
                    <div className="text-[10px] uppercase tracking-wide text-text-muted">
                      {key}
                    </div>
                    <div className="tabular-nums text-text">
                      {typeof val === "number"
                        ? val.toExponential(2)
                        : String(val)}
                    </div>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {scaleEntries.length > 0 && (
            <Section title="Calibration scales">
              <div className="space-y-2">
                {scaleEntries.map(([component, def]) => {
                  const value = lossScales[component] ?? def;
                  return (
                    <div key={component} className="flex items-center gap-3">
                      <span className="w-28 truncate text-xs text-text-muted">
                        {component.replace(/_/g, " ")}
                      </span>
                      <Slider
                        aria-label={`${component} scale factor`}
                        min={0.5}
                        max={1.5}
                        step={0.01}
                        value={[value]}
                        onValueChange={(v) =>
                          setLossScale(component, v[0] ?? def)
                        }
                        className="flex-1"
                      />
                      <span className="w-12 text-right font-mono text-xs text-text">
                        {value.toFixed(2)}
                      </span>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 text-text-muted"
                        onClick={() => setLossScale(component, def)}
                        aria-label={`Reset ${component} to literature default`}
                      >
                        reset
                      </Button>
                    </div>
                  );
                })}
              </div>
            </Section>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="mb-1 flex items-center gap-1 text-xs font-medium uppercase tracking-wide text-text-muted">
        <ChevronRight className="h-3 w-3" /> {title}
      </h3>
      {children}
    </section>
  );
}

const DEFAULT_LOSS_EQUATION = `% Generic mean-line decomposition
\\Delta h_{loss} = \\sum_i k_i \\, \\Delta h_{loss,i}
\\eta_{tt} = 1 - \\sum_i k_i \\, \\Delta h_{loss,i} / \\Delta h_{ideal}`;

const LOSS_EQUATION_TEX: Record<string, string> = {
  "whitfield-baines-radial-v1": `% Whitfield & Baines (1990) — radial turbine, sum of seven losses.
\\Delta h_{inc}     = k_{inc} \\cdot \\tfrac{1}{2} W_{rel,1}^2 \\sin^2(\\alpha_{inc})
\\Delta h_{pass}    = k_{pass} \\cdot c_f \\cdot \\tfrac{L_h}{D_h} \\cdot \\tfrac{1}{2} \\bar{W}^2
\\Delta h_{tipcl}   = k_{tip} \\cdot \\tfrac{\\tau}{h_2} \\cdot \\tfrac{1}{2} U_2^2
\\Delta h_{disc}    = k_{disc} \\cdot 0.02 \\cdot \\rho \\, U_2^3 \\, r_2^2 / \\dot{m}
\\Delta h_{exit}    = k_{exit} \\cdot \\tfrac{1}{2} C_3^2
\\eta_{tt} = 1 - \\frac{\\sum \\Delta h_{loss}}{\\Delta h_{ideal}}`,
  "aungier-centrifugal-v1": `% Aungier (2000) — centrifugal compressor, seven losses.
\\Delta h_{inc}     = k_{inc} \\cdot \\tfrac{1}{2} W_1^2 (1 - \\cos\\beta_{inc})
\\Delta h_{bl}      = k_{bl} \\cdot 0.05 \\cdot \\Delta W / W_{avg}
\\Delta h_{sf}      = k_{sf} \\cdot 4 c_f \\, L_{ch}/D_h \\, \\tfrac{1}{2} \\bar{W}^2
\\Delta h_{mix}     = k_{mix} \\cdot \\tfrac{1}{2}(C_w - C_{w,wake})^2
\\Delta h_{recirc}  = k_{rc} \\cdot 8e^{-5} \\, U_2^2 \\, \\sinh(\\phi)
\\Delta h_{leak}    = k_{lk} \\cdot \\dot{m}_{lk}/\\dot{m} \\cdot U_2^2`,
};
