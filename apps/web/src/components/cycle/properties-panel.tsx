"use client";

import * as React from "react";
import {
  useForm,
  type FieldValues,
  type Path,
  type UseFormReturn,
} from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z, type ZodObject, type ZodRawShape } from "zod";
import {
  AlertTriangle,
  Box,
  ChevronDown,
  ChevronRight,
  HelpCircle,
  Info,
  MoreHorizontal,
  Save,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { QuantityInput, ComputedValue } from "./quantity-input";
import { MaterialPicker } from "@/components/materials/material-picker";
import { getProjectSettings, getRawComponents } from "@/lib/api/flowpath";
import type {
  CycleNode,
  CycleNodeKind,
  Project,
  WorkingFluid,
} from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { useCycleUiStore } from "./store";

/* ---------------------------------------------------------------------------
 * Param schemas — typed per component kind (discriminated union mirrors the
 * Python dataclasses in `src/cascade/cycle/components.py`).
 *
 * Naming convention: each key matches the corresponding kwarg on the Python
 * dataclass except where the UI needs a derived form (e.g. *_K for absolute
 * temperatures the QuantityInput converts to other units). Keys live in
 * `node.params` and are persisted via the API client through the `.cascade`
 * TOML serializer (ADAPT-014).
 * ------------------------------------------------------------------------- */

export interface CompressorParams {
  kind: "compressor";
  // essentials
  pressure_ratio: number;
  efficiency_isentropic: number;
  /**
   * Efficiency-evaluation mode (mirrors the Python `EfficiencyMode` literal).
   * `live_meanline` (ADAPT-036) runs the Aungier centrifugal mean-line
   * solver inside each cycle iteration so η reacts to the operating point —
   * the live co-simulation behaviour. Requires a geometry on the
   * Analysis page.
   */
  efficiency_mode: "isentropic" | "polytropic" | "live_meanline";
  geometry_type: "centrifugal" | "axial";
  // advanced
  mechanical_efficiency: number;
  shaft_id: number;
  /** Optional mass-flow override [kg/s]. 0 ⇒ inherit from boundary. */
  mass_flow_override_kg_s?: number;
  /** Optional inlet temperature constraint [K]. 0 ⇒ inherit from boundary. */
  inlet_temperature_K?: number;
  bleed_fraction_customer: number;
  bleed_fraction_cooling: number;
}

export interface TurbineParams {
  kind: "turbine";
  pressure_ratio: number;
  efficiency_isentropic: number;
  /**
   * Efficiency-evaluation mode (mirrors the Python `EfficiencyMode` literal).
   * `live_meanline` (ADAPT-036) runs the Whitfield-Baines radial-inflow
   * mean-line solver inside each cycle iteration.
   */
  efficiency_mode: "isentropic" | "polytropic" | "live_meanline";
  geometry_type: "radial" | "axial";
  mechanical_efficiency: number;
  shaft_id: number;
  cooling_flow_fraction: number;
}

export interface BurnerParams {
  kind: "burner";
  // essentials
  outlet_temperature_K: number;
  pressure_drop_fraction: number;
  combustion_efficiency: number;
  spec_mode: "outlet_temperature" | "fuel_mass_flow";
  fuel_species: "CH4" | "JP-4" | "JP-8" | "generic";
  // advanced
  fuel_lhv_MJ_per_kg: number;
  fuel_mass_flow_kg_s: number;
}

export interface RecuperatorParams {
  kind: "recuperator";
  effectiveness: number;
  cold_pressure_drop_fraction: number;
  hot_pressure_drop_fraction: number;
  heat_transfer_area_m2: number;
}

export interface IntercoolerParams {
  kind: "intercooler";
  temperature_drop_K: number;
  pressure_drop_fraction: number;
  coolant_temperature_K: number;
  effectiveness: number;
}

export interface MixerParams {
  kind: "mixer";
  n_inputs: number;
  pressure_drop_fraction: number;
}

export interface SplitterParams {
  kind: "splitter";
  split_fraction: number;
  pressure_drop_fraction: number;
}

export interface InletParams {
  kind: "inlet";
  pressure_total_kPa: number;
  temperature_total_K: number;
  mass_flow_kg_s: number;
  pressure_loss_fraction: number;
}

export interface OutletParams {
  kind: "outlet";
  pressure_loss_fraction: number;
}

export interface DuctParams {
  kind: "duct";
  pressure_drop_fraction: number;
}

export interface ShaftParams {
  kind: "shaft";
  speed_krpm: number;
  mechanical_efficiency: number;
}

/** Discriminated union over the cycle-canvas component kinds. */
export type ComponentParams =
  | CompressorParams
  | TurbineParams
  | BurnerParams
  | RecuperatorParams
  | IntercoolerParams
  | MixerParams
  | SplitterParams
  | InletParams
  | OutletParams
  | DuctParams
  | ShaftParams;

interface PropertiesPanelProps {
  node?: CycleNode;
  project?: Project;
  /** Result for this node (e.g. shaft work, outlet T/P/ṁ) if available. */
  result?: {
    shaftWork?: number;
    outletTemperature?: number;
    outletPressure?: number;
    outletMassFlow?: number;
  };
  onPatch(
    componentId: string,
    patch: {
      label?: string;
      params?: Record<string, number | string | boolean>;
    },
  ): Promise<void>;
  onDelete(componentId: string): Promise<void>;
  onProjectSettingsChange?(patch: {
    workingFluid?: WorkingFluid;
    ambient?: { Pt?: number; Tt?: number };
  }): void;
}

/**
 * Right-side panel. When nothing is selected, edits project-wide
 * settings (working fluid, ambient BCs). When a node is selected,
 * exposes that node's parameters via react-hook-form + zod.
 */
export function PropertiesPanel({
  node,
  project,
  result,
  onPatch,
  onDelete,
  onProjectSettingsChange,
}: PropertiesPanelProps) {
  return (
    <aside className="flex w-[320px] shrink-0 flex-col overflow-hidden border-l border-border-subtle bg-surface-subtle/40">
      <div className="border-b border-border-subtle px-3 py-2.5">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
          {node ? "Component" : "Project"}
        </h2>
        <p className="mt-0.5 text-sm text-text">
          {node
            ? `${humanKind(node.kind)} · ${node.label}`
            : project?.name ?? "—"}
        </p>
      </div>

      <div className="flex-1 overflow-auto scrollbar-subtle p-3">
        {node ? (
          <NodeForm
            key={node.id}
            node={node}
            project={project}
            result={result}
            onPatch={onPatch}
            onDelete={onDelete}
          />
        ) : (
          <ProjectForm
            project={project}
            onChange={onProjectSettingsChange}
          />
        )}
      </div>
    </aside>
  );
}

/* ---------------------------------------------------------------------------
 * Project-wide settings (when nothing selected)
 * ------------------------------------------------------------------------- */

function ProjectForm({
  project,
  onChange,
}: {
  project?: Project;
  onChange?: PropertiesPanelProps["onProjectSettingsChange"];
}) {
  const [fluid, setFluid] = React.useState<WorkingFluid>(
    project?.workingFluid ?? "air",
  );
  const [pt, setPt] = React.useState(101.3);
  const [tt, setTt] = React.useState(288);

  React.useEffect(() => {
    if (project) setFluid(project.workingFluid);
  }, [project]);

  return (
    <div className="flex flex-col gap-4">
      <section className="flex flex-col gap-2">
        <Label htmlFor="working-fluid">Working fluid</Label>
        <Select
          value={fluid}
          onValueChange={(v) => {
            const f = v as WorkingFluid;
            setFluid(f);
            onChange?.({ workingFluid: f });
          }}
        >
          <SelectTrigger id="working-fluid">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="air">Air</SelectItem>
            <SelectItem value="co2">CO₂ (sCO₂)</SelectItem>
            <SelectItem value="n2">N₂</SelectItem>
            <SelectItem value="h2">H₂</SelectItem>
            <SelectItem value="methane">Methane</SelectItem>
          </SelectContent>
        </Select>
        <p className="text-[11px] text-text-muted">
          Mixture is set on the inlet component; the working-fluid choice
          is a project-level default.
        </p>
      </section>

      <section className="flex flex-col gap-2">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
          Ambient
        </h3>
        <FieldRow label="Pt" symbol="ambient pressure">
          <QuantityInput
            value={pt}
            unit="kPa"
            units={["kPa", "bar", "psi"]}
            onValueChange={(v) => {
              setPt(v);
              onChange?.({ ambient: { Pt: v } });
            }}
          />
        </FieldRow>
        <FieldRow label="Tt" symbol="ambient temperature">
          <QuantityInput
            value={tt}
            unit="K"
            units={["K", "°C", "°F"]}
            onValueChange={(v) => {
              setTt(v);
              onChange?.({ ambient: { Tt: v } });
            }}
          />
        </FieldRow>
      </section>

      <section className="flex flex-col gap-1 rounded-md border border-dashed border-border-subtle p-3 text-[11px] text-text-muted">
        Select a component on the canvas to edit its parameters here. With
        nothing selected, this panel edits the project defaults.
      </section>
    </div>
  );
}

/* ---------------------------------------------------------------------------
 * Per-kind parameter descriptors
 *
 * Each kind has two arrays:
 *  - `essentials`: shown by default (typical engineering knobs)
 *  - `advanced`:   collapsed; surfaced via "Show advanced" toggle
 *
 * Plus a per-kind zod schema for validation, and a small `readonlyBadges`
 * array for the geometry-type badge etc. that the user shouldn't edit
 * inline (cycle-level designators).
 * ------------------------------------------------------------------------- */

type FieldKind = "quantity" | "fraction" | "integer" | "select" | "radio";

interface ParamField {
  key: string;
  label: string;
  symbol?: string;
  units: string[];
  defaultUnit: string;
  min?: number;
  max?: number;
  step?: number;
  /** UI control flavour. Defaults to "quantity". */
  kind?: FieldKind;
  /** Options for select / radio fields. */
  options?: Array<{ value: string; label: string }>;
  /** Tooltip + citation rendered next to the label. */
  tooltip?: string;
  /** Convert raw param value to display value in the default unit. */
  toDisplay?: (raw: number) => number;
  /** Convert the display value (in the default unit) back to raw param value. */
  fromDisplay?: (v: number) => number;
  /**
   * Engineering default the form pre-fills when `node.params[key]` is
   * absent. Used so a field with `min > 0` (e.g. `mechanical_efficiency`,
   * `shaft_id`) doesn't start at 0 and trip its zod validator on first
   * open — that produces the "Cannot save — fix the highlighted field"
   * toast even before the user touches anything. Optional; falls back to
   * `min ?? 0`.
   */
  defaultValue?: number;
  /**
   * `false` means the value is *persisted* (PATCH lands, survives refresh)
   * but NOT consumed by today's cycle solver. We badge these fields with
   * a "preview" pill so the user doesn't expect their edit to change η.
   * Audit referenced: `_build_recuperated_spec` in `apps/api/routers/cycle.py`.
   * Defaults to `true` (wired).
   */
  wired?: boolean;
}

interface KindSchema {
  essentials: ParamField[];
  advanced: ParamField[];
  /** Readonly-badge fields, displayed as informational pills next to the
   *  title. Each renders the param value as a Badge — they aren't editable. */
  readonlyBadges?: Array<{ key: string; prefix?: string }>;
  /** Composite zod schema (essentials + advanced + selects). May carry
   *  cross-field refinements (e.g. the burner's fuel-flow gt(0) only when
   *  fuel mode is active), hence the wider type. */
  zod: z.ZodTypeAny;
  /**
   * When set, this entire kind is a "preview" — values save & round-trip
   * but the Brayton-cycle solver in `_build_recuperated_spec` doesn't
   * consume them yet. Shows a banner at the top of the form.
   */
  previewBanner?: string;
}

/** Tiny helper: scalar field for a unit-less ratio / fraction. */
const dimensionless = (
  key: string,
  label: string,
  symbol: string,
  min: number,
  max: number,
  step = 0.01,
  tooltip?: string,
): ParamField => ({
  key,
  label,
  symbol,
  units: ["—"],
  defaultUnit: "—",
  min,
  max,
  step,
  kind: "fraction",
  tooltip,
});

/** Tiny helper: percentage knob — stored as a fraction (0..1) but displayed
 *  with the "%" unit hint so engineers see "3 %" not "0.03". */
const percentFraction = (
  key: string,
  label: string,
  symbol: string,
  maxFrac: number,
  tooltip?: string,
): ParamField => ({
  key,
  label,
  symbol,
  units: ["%"],
  defaultUnit: "%",
  min: 0,
  max: maxFrac * 100,
  step: 0.1,
  kind: "fraction",
  toDisplay: (raw) => raw * 100,
  fromDisplay: (v) => v / 100,
  tooltip,
});

const SCHEMAS: Record<CycleNodeKind, KindSchema> = {
  compressor: {
    readonlyBadges: [{ key: "geometry_type", prefix: "type" }],
    essentials: [
      {
        key: "pressure_ratio",
        label: "Pressure ratio",
        symbol: "π_c",
        units: ["—"],
        defaultUnit: "—",
        min: 1.01,
        max: 50,
        step: 0.01,
        kind: "fraction",
        defaultValue: 3.0,
        tooltip:
          "Total-to-total pressure ratio Pt_out / Pt_in. Refusal envelope hard-capped at 60 (SPEC_SHEET §13).",
      },
      {
        key: "efficiency_mode",
        label: "Efficiency mode",
        units: [],
        defaultUnit: "",
        kind: "radio",
        options: [
          { value: "isentropic", label: "Isentropic" },
          { value: "polytropic", label: "Polytropic" },
          { value: "live_meanline", label: "Live mean-line" },
        ],
        tooltip:
          "Live mean-line (ADAPT-036) runs the centrifugal mean-line solver inside the cycle — η becomes a function of the operating point. Polytropic accounts for finite-stage compression. Isentropic is the v1 default.",
      },
      {
        key: "efficiency_isentropic",
        label: "Efficiency",
        symbol: "η",
        units: ["—"],
        defaultUnit: "—",
        min: 0.3,
        max: 0.95,
        step: 0.01,
        kind: "fraction",
        defaultValue: 0.82,
        tooltip:
          "Adiabatic efficiency, total-to-total. Typical η ∈ [0.78, 0.88] for centrifugal stages. Ignored when efficiency mode = ‘Live mean-line’.",
      },
    ],
    advanced: [
      {
        key: "mechanical_efficiency",
        label: "Mechanical efficiency",
        symbol: "η_m",
        units: ["—"],
        defaultUnit: "—",
        min: 0.85,
        max: 1,
        step: 0.005,
        kind: "fraction",
        defaultValue: 0.99,
        tooltip:
          "Bearing / windage losses on the shaft. The cycle solver combines compressor and turbine η_m as a product (Walsh & Fletcher §5 convention). Typical 0.97–0.99.",
      },
      {
        key: "shaft_id",
        label: "Shaft id",
        units: ["—"],
        defaultUnit: "—",
        min: 1,
        max: 8,
        step: 1,
        kind: "integer",
        defaultValue: 1,
        tooltip:
          "Spool number this compressor sits on (multi-shaft cycles only). Single-shaft solver ignores shaft_id.",
        wired: false,
      },
      {
        key: "mass_flow_override_kg_s",
        label: "Mass-flow override",
        symbol: "ṁ",
        units: ["kg/s"],
        defaultUnit: "kg/s",
        min: 0,
        max: 5000,
        step: 0.001,
        kind: "quantity",
        defaultValue: 0,
        tooltip:
          "Set non-zero to pin the corrected mass flow at this compressor (otherwise inherited from the inlet boundary). Preview: not yet consumed by the cycle solver.",
        wired: false,
      },
      {
        key: "inlet_temperature_K",
        label: "Inlet temperature constraint",
        symbol: "T_in",
        units: ["K", "°C"],
        defaultUnit: "K",
        min: 0,
        max: 2000,
        step: 1,
        kind: "quantity",
        defaultValue: 0,
        tooltip:
          "Pin the compressor-face stagnation temperature (e.g. after intercooler). 0 = inherit from upstream. Preview: not yet consumed by the cycle solver.",
        wired: false,
      },
      {
        ...percentFraction(
          "bleed_fraction_customer",
          "Customer bleed",
          "β_c",
          0.3,
          "Mass fraction extracted for customer / pneumatic loads. Preview: not yet consumed by the cycle solver.",
        ),
        wired: false,
      },
      {
        ...percentFraction(
          "bleed_fraction_cooling",
          "Cooling bleed",
          "β_b",
          0.3,
          "Mass fraction extracted to cool downstream hot-section blading. Preview: not yet consumed by the cycle solver.",
        ),
        wired: false,
      },
    ],
    // NOTE: percentFraction fields are stored on the form as DISPLAY values
    // (the QuantityInput shows "%"; toDisplay multiplies the raw fraction by
    // 100). Zod runs against the form values, so bounds here MUST also be in
    // display units — e.g. `bleed_fraction_customer` raw range [0, 0.3]
    // becomes [0, 30]. Submitting maps back to raw via fromDisplay.
    zod: z.object({
      pressure_ratio: z.number().gte(1.01).lte(50),
      efficiency_isentropic: z.number().gte(0.3).lte(0.95),
      efficiency_mode: z.enum(["isentropic", "polytropic", "live_meanline"]),
      geometry_type: z.enum(["centrifugal", "axial"]).optional(),
      mechanical_efficiency: z.number().gte(0.85).lte(1),
      shaft_id: z.number().int().gte(1).lte(8),
      mass_flow_override_kg_s: z.number().gte(0).lte(5000).optional(),
      inlet_temperature_K: z.number().gte(0).lte(2000).optional(),
      bleed_fraction_customer: z.number().gte(0).lte(30),
      bleed_fraction_cooling: z.number().gte(0).lte(30),
    }),
  },
  turbine: {
    readonlyBadges: [{ key: "geometry_type", prefix: "type" }],
    essentials: [
      {
        key: "pressure_ratio",
        label: "Pressure ratio",
        symbol: "π_t",
        units: ["—"],
        defaultUnit: "—",
        min: 1.01,
        max: 50,
        step: 0.01,
        kind: "fraction",
        tooltip:
          "Total-to-total expansion ratio P_in / P_out. Often inherited from the burner outlet and compressor PR via shaft balance.",
      },
      {
        key: "efficiency_mode",
        label: "Efficiency mode",
        units: [],
        defaultUnit: "",
        kind: "radio",
        options: [
          { value: "isentropic", label: "Isentropic" },
          { value: "polytropic", label: "Polytropic" },
          { value: "live_meanline", label: "Live mean-line" },
        ],
        tooltip:
          "Live mean-line (ADAPT-036) runs the Whitfield-Baines radial-turbine mean-line solver inside the cycle iteration so η responds to the operating point.",
      },
      {
        key: "efficiency_isentropic",
        label: "Efficiency",
        symbol: "η",
        units: ["—"],
        defaultUnit: "—",
        min: 0.3,
        max: 0.95,
        step: 0.01,
        kind: "fraction",
        defaultValue: 0.85,
        tooltip:
          "Adiabatic total-to-total efficiency. Typical 0.85–0.92 for radial inflow. Ignored when efficiency mode = ‘Live mean-line’.",
      },
    ],
    advanced: [
      {
        key: "mechanical_efficiency",
        label: "Mechanical efficiency",
        symbol: "η_m",
        units: ["—"],
        defaultUnit: "—",
        min: 0.85,
        max: 1,
        step: 0.005,
        kind: "fraction",
        defaultValue: 0.99,
        tooltip:
          "Bearing / windage losses on the shaft. The cycle solver combines compressor and turbine η_m as a product (Walsh & Fletcher §5 convention). Typical 0.97–0.99.",
      },
      {
        key: "shaft_id",
        label: "Shaft id",
        units: ["—"],
        defaultUnit: "—",
        min: 1,
        max: 8,
        step: 1,
        kind: "integer",
        defaultValue: 1,
        tooltip:
          "Spool number this turbine sits on (multi-shaft cycles only). Single-shaft solver ignores shaft_id.",
        wired: false,
      },
      {
        ...percentFraction(
          "cooling_flow_fraction",
          "Cooling-flow fraction",
          "ϕ_cool",
          0.2,
          "Cooling-air mass fraction injected into the turbine row (turbine inlet temperature relief). Preview: not yet consumed by the cycle solver.",
        ),
        wired: false,
      },
    ],
    // See compressor zod note: percentFraction fields validate in DISPLAY
    // units (%). cooling_flow_fraction raw [0, 0.2] → display [0, 20].
    zod: z.object({
      pressure_ratio: z.number().gte(1.01).lte(50),
      efficiency_isentropic: z.number().gte(0.3).lte(0.95),
      efficiency_mode: z.enum(["isentropic", "polytropic", "live_meanline"]),
      geometry_type: z.enum(["radial", "axial"]).optional(),
      mechanical_efficiency: z.number().gte(0.85).lte(1),
      shaft_id: z.number().int().gte(1).lte(8),
      cooling_flow_fraction: z.number().gte(0).lte(20),
    }),
  },
  burner: {
    essentials: [
      {
        key: "spec_mode",
        label: "Spec mode",
        units: [],
        defaultUnit: "",
        kind: "radio",
        options: [
          {
            value: "outlet_temperature",
            label: "Outlet T (TIT)",
          },
          {
            value: "fuel_mass_flow",
            label: "Fuel ṁ",
          },
        ],
        tooltip:
          "Pick which side of the burner energy balance the user pins. Exactly one is required (Walsh & Fletcher §5.10).",
      },
      {
        key: "outlet_temperature_K",
        label: "Outlet temperature (TIT)",
        symbol: "T₄",
        units: ["K", "°C"],
        defaultUnit: "K",
        min: 400,
        max: 2000,
        step: 1,
        kind: "quantity",
        defaultValue: 1100,
        tooltip:
          "Turbine inlet temperature. Refused above 2100 K (uncooled material limit, SPEC_SHEET §13).",
      },
      {
        key: "combustion_efficiency",
        label: "Combustion efficiency",
        symbol: "η_b",
        units: ["—"],
        defaultUnit: "—",
        min: 0.9,
        max: 1,
        step: 0.005,
        kind: "fraction",
        defaultValue: 0.99,
        tooltip:
          "Fraction of LHV released. Typical 0.99 for modern annular combustors.",
      },
      percentFraction(
        "pressure_drop_fraction",
        "Pressure-drop ratio",
        "Δp/p",
        0.1,
        "Combustor pressure drop. Typical 2–5 % (Walsh & Fletcher §5).",
      ),
      {
        key: "fuel_species",
        label: "Fuel species",
        units: [],
        defaultUnit: "",
        kind: "select",
        options: [
          { value: "CH4", label: "Methane (CH₄)" },
          { value: "JP-4", label: "JP-4" },
          { value: "JP-8", label: "JP-8" },
          { value: "generic", label: "Generic hydrocarbon" },
        ],
      },
    ],
    advanced: [
      {
        key: "fuel_lhv_MJ_per_kg",
        label: "Fuel LHV",
        symbol: "LHV",
        units: ["MJ/kg"],
        defaultUnit: "MJ/kg",
        min: 10,
        max: 130,
        step: 0.1,
        kind: "quantity",
        defaultValue: 50.0,
        tooltip:
          "Lower heating value. 50 MJ/kg for CH₄, 43 for JP-8, 120 for H₂.",
      },
      {
        key: "fuel_mass_flow_kg_s",
        label: "Fuel mass flow",
        symbol: "ṁ_f",
        units: ["kg/s"],
        defaultUnit: "kg/s",
        min: 0,
        max: 5,
        step: 0.0001,
        kind: "quantity",
        defaultValue: 0.002,
        tooltip:
          "Fuel injected at the combustor. When spec-mode = 'Fuel ṁ' this drives the energy balance and the solver back-derives the TIT (Walsh & Fletcher §5.10). A 30 kW-class microturbine burns ≈0.002 kg/s of natural gas.",
      },
    ],
    // See compressor zod note: pressure_drop_fraction is a percentFraction
    // (display unit %), so its raw [0, 0.1] becomes display [0, 10].
    zod: z
      .object({
        outlet_temperature_K: z.number().gte(400).lte(2000),
        pressure_drop_fraction: z.number().gte(0).lte(10),
        combustion_efficiency: z.number().gte(0.9).lte(1),
        spec_mode: z.enum(["outlet_temperature", "fuel_mass_flow"]),
        fuel_species: z.enum(["CH4", "JP-4", "JP-8", "generic"]),
        fuel_lhv_MJ_per_kg: z.number().gte(10).lte(130),
        fuel_mass_flow_kg_s: z.number().gte(0).lte(5),
      })
      .superRefine((vals, ctx) => {
        // U7: gt(0) applies only when the fuel value is the ACTIVE spec —
        // in outlet-T mode the field is inactive and a stored 0 is legal.
        if (
          vals.spec_mode === "fuel_mass_flow" &&
          !(vals.fuel_mass_flow_kg_s > 0)
        ) {
          ctx.addIssue({
            code: z.ZodIssueCode.custom,
            path: ["fuel_mass_flow_kg_s"],
            message: "Fuel mass flow must be > 0 in fuel-ṁ mode.",
          });
        }
      }),
  },
  recuperator: {
    essentials: [
      dimensionless(
        "effectiveness",
        "Effectiveness",
        "ε",
        0,
        0.98,
        0.01,
        "ε = (T_cold_out − T_cold_in) / (T_hot_in − T_cold_in). Refused above 0.98 (pinch divergence, SPEC_SHEET §13).",
      ),
      percentFraction(
        "cold_pressure_drop_fraction",
        "Cold-side Δp/p",
        "Δp_c",
        0.1,
        "Pressure loss on the high-pressure / compressor-discharge side.",
      ),
      percentFraction(
        "hot_pressure_drop_fraction",
        "Hot-side Δp/p",
        "Δp_h",
        0.1,
        "Pressure loss on the low-pressure / turbine-exhaust side.",
      ),
    ],
    advanced: [
      {
        key: "heat_transfer_area_m2",
        label: "Heat-transfer area",
        symbol: "A",
        units: ["m²"],
        defaultUnit: "m²",
        min: 0,
        max: 1000,
        step: 0.1,
        kind: "quantity",
        tooltip:
          "Geometric heat-transfer area. Preview: only used by off-design / ε-NTU re-solves (v1.1).",
        wired: false,
      },
    ],
    // See compressor zod note: cold/hot_pressure_drop_fraction are %
    // percentFractions (raw [0, 0.1] → display [0, 10]).
    zod: z.object({
      effectiveness: z.number().gte(0).lte(0.98),
      cold_pressure_drop_fraction: z.number().gte(0).lte(10),
      hot_pressure_drop_fraction: z.number().gte(0).lte(10),
      heat_transfer_area_m2: z.number().gte(0).lte(1000),
    }),
  },
  intercooler: {
    essentials: [
      dimensionless(
        "effectiveness",
        "Effectiveness",
        "ε",
        0,
        0.98,
        0.01,
        "Cold-side ε for the cooling stream. T_out = T_in − ε·(T_in − T_coolant).",
      ),
      {
        key: "coolant_temperature_K",
        label: "Coolant temperature",
        symbol: "T_c",
        units: ["K", "°C"],
        defaultUnit: "K",
        min: 100,
        max: 600,
        step: 1,
        kind: "quantity",
        defaultValue: 300,
      },
      percentFraction(
        "pressure_drop_fraction",
        "Pressure-drop ratio",
        "Δp/p",
        0.1,
        "Typical 2 % for an air-water intercooler.",
      ),
    ],
    advanced: [
      {
        key: "temperature_drop_K",
        label: "Target ΔT",
        symbol: "ΔT",
        units: ["K", "°C"],
        defaultUnit: "K",
        min: 0,
        max: 500,
        step: 1,
        kind: "quantity",
        tooltip:
          "Alternative spec: pin the cooling ΔT directly rather than via ε. Preview: the Intercooler solver currently only consumes effectiveness + coolant_temperature.",
        wired: false,
      },
    ],
    // pressure_drop_fraction is a percentFraction (display %).
    zod: z.object({
      effectiveness: z.number().gte(0).lte(0.98),
      coolant_temperature_K: z.number().gte(100).lte(600),
      pressure_drop_fraction: z.number().gte(0).lte(10),
      temperature_drop_K: z.number().gte(0).lte(500),
    }),
    previewBanner:
      "Intercooler is a v1.1 preview component. Values save but the cycle solver still produces a Brayton result without it (see _build_recuperated_spec).",
  },
  mixer: {
    essentials: [
      {
        key: "n_inputs",
        label: "Number of inputs",
        units: ["—"],
        defaultUnit: "—",
        min: 2,
        max: 6,
        step: 1,
        kind: "integer",
      },
      percentFraction(
        "pressure_drop_fraction",
        "Pressure loss",
        "Δp/p",
        0.05,
      ),
    ],
    advanced: [],
    // pressure_drop_fraction is a percentFraction (display %). Raw [0, 0.05] → display [0, 5].
    zod: z.object({
      n_inputs: z.number().int().gte(2).lte(6),
      pressure_drop_fraction: z.number().gte(0).lte(5),
    }),
    previewBanner:
      "Mixer is a v1.1 preview component. Values save but the cycle solver still produces a Brayton result without it. The canvas also renders a fixed 2-input shape — n_inputs > 2 is persisted but not visualised.",
  },
  splitter: {
    essentials: [
      dimensionless(
        "split_fraction",
        "A-leg mass-flow fraction",
        "β",
        0,
        1,
        0.01,
        "Fraction routed down the ‘A’ branch (the other branch gets 1 − β). Acts as the bleed fraction.",
      ),
      percentFraction(
        "pressure_drop_fraction",
        "Pressure loss",
        "Δp/p",
        0.05,
      ),
    ],
    advanced: [],
    // pressure_drop_fraction is a percentFraction (display %).
    // split_fraction is a `dimensionless` (raw fraction, no display scaling).
    zod: z.object({
      split_fraction: z.number().gte(0).lte(1),
      pressure_drop_fraction: z.number().gte(0).lte(5),
    }),
    previewBanner:
      "Splitter is a v1.1 preview component. Values save but the cycle solver still produces a Brayton result without it.",
  },
  duct: {
    essentials: [
      percentFraction(
        "pressure_drop_fraction",
        "Pressure-drop ratio",
        "Δp/p",
        0.1,
      ),
    ],
    advanced: [],
    // pressure_drop_fraction is a percentFraction (display %).
    zod: z.object({
      pressure_drop_fraction: z.number().gte(0).lte(10),
    }),
  },
  inlet: {
    essentials: [
      {
        key: "pressure_total_kPa",
        label: "Total pressure",
        symbol: "Pt",
        units: ["kPa", "bar", "psi"],
        defaultUnit: "kPa",
        min: 1,
        max: 50000,
        step: 1,
        kind: "quantity",
        defaultValue: 101.325,
      },
      {
        key: "temperature_total_K",
        label: "Total temperature",
        symbol: "Tt",
        units: ["K", "°C"],
        defaultUnit: "K",
        min: 100,
        max: 2000,
        step: 1,
        kind: "quantity",
        defaultValue: 288.15,
      },
      {
        key: "mass_flow_kg_s",
        label: "Mass flow",
        symbol: "ṁ",
        units: ["kg/s"],
        defaultUnit: "kg/s",
        min: 0.001,
        max: 5000,
        step: 0.001,
        kind: "quantity",
        defaultValue: 1.0,
      },
    ],
    advanced: [
      {
        ...percentFraction(
          "pressure_loss_fraction",
          "Inlet pressure loss",
          "Δp/p",
          0.1,
          "Bell-mouth / filter-house loss applied to Pt before C1 (Walsh & Fletcher 1–3 %). Preview: prefer adding a dedicated 'Inlet duct' (Duct) component — the cycle solver consumes that.",
        ),
        wired: false,
      },
    ],
    // pressure_loss_fraction is a percentFraction (display %).
    zod: z.object({
      pressure_total_kPa: z.number().gte(1).lte(50000),
      temperature_total_K: z.number().gte(100).lte(2000),
      mass_flow_kg_s: z.number().gte(0.001).lte(5000),
      pressure_loss_fraction: z.number().gte(0).lte(10),
    }),
  },
  shaft: {
    essentials: [
      {
        key: "speed_krpm",
        label: "Rotational speed",
        symbol: "ω",
        units: ["krpm"],
        defaultUnit: "krpm",
        min: 1,
        max: 250,
        step: 0.1,
        kind: "quantity",
        defaultValue: 60,
      },
      {
        key: "mechanical_efficiency",
        label: "Mechanical efficiency",
        symbol: "η_m",
        units: ["—"],
        defaultUnit: "—",
        min: 0.5,
        max: 1,
        step: 0.005,
        kind: "fraction",
        defaultValue: 0.98,
      },
    ],
    advanced: [],
    zod: z.object({
      speed_krpm: z.number().gte(1).lte(250),
      mechanical_efficiency: z.number().gte(0.5).lte(1),
    }),
    previewBanner:
      "Shaft is a multi-spool primitive. On a single-shaft cycle (the default) the solver picks up η_m and speed from project.settings — the per-component Shaft fields save but don't drive a single-shaft solve.",
  },
  outlet: {
    essentials: [
      {
        ...percentFraction(
          "pressure_loss_fraction",
          "Exhaust pressure loss",
          "Δp/p",
          0.1,
          "Exit-stack / silencer loss applied to Pt at the exhaust. Preview: add a Duct upstream of the outlet to bake an exhaust loss into the solver result.",
        ),
        wired: false,
      },
    ],
    advanced: [],
    // pressure_loss_fraction is a percentFraction (display %).
    zod: z.object({
      pressure_loss_fraction: z.number().gte(0).lte(10),
    }),
  },
};

/* ---------------------------------------------------------------------------
 * Per-node form
 * ------------------------------------------------------------------------- */

function NodeForm({
  node,
  project,
  result,
  onPatch,
  onDelete,
}: {
  node: CycleNode;
  project?: Project;
  result?: PropertiesPanelProps["result"];
  onPatch: PropertiesPanelProps["onPatch"];
  onDelete: PropertiesPanelProps["onDelete"];
}) {
  const schema = SCHEMAS[node.kind];

  /**
   * The form holds *display-unit* numeric values (e.g. 3.0 for a percentage
   * stored as 0.03) plus the verbatim string for select/radio fields.
   *
   * On submit, each field's `fromDisplay` reverses the toDisplay applied at
   * load. The result is shipped to `onPatch` as `Record<string, number |
   * string | boolean>` matching the canonical param shape.
   *
   * Defensive Quantity unwrap: the API client converts backend Quantity
   * dicts to display-unit numbers before they reach this form, but a stray
   * `{value, unit}` may still appear (e.g. an offline-fallback graph or a
   * future field we forgot to register in the translation table). Unwrap
   * to `value` rather than dropping to 0, which would silently fail zod
   * validators that require positive numbers (mass_flow, pressure_ratio).
   */
  const defaults = React.useMemo(() => {
    const out: Record<string, number | string> = {};
    const allFields = [...schema.essentials, ...schema.advanced];
    for (const f of allFields) {
      const raw = node.params?.[f.key];
      if (f.kind === "select" || f.kind === "radio") {
        out[f.key] = typeof raw === "string" ? raw : (f.options?.[0]?.value ?? "");
      } else {
        let num: number | undefined;
        if (typeof raw === "number" && Number.isFinite(raw)) {
          num = raw;
        } else if (
          raw &&
          typeof raw === "object" &&
          "value" in (raw as Record<string, unknown>) &&
          typeof (raw as { value: unknown }).value === "number"
        ) {
          // Stray Quantity dict (offline fallback or future field not yet
          // in the API translation table) — pass the value through. Units
          // are presumed already in the field's display unit.
          num = (raw as { value: number }).value;
        }
        if (num === undefined) {
          // Engineering default. Prefer the schema's explicit defaultValue;
          // otherwise the field's min (so a positive-only field doesn't
          // start at 0 and trip zod); else 0.
          num = f.defaultValue ?? f.min ?? 0;
        }
        out[f.key] = f.toDisplay ? f.toDisplay(num) : num;
      }
    }
    return out;
  }, [node, schema]);

  type Values = typeof defaults;

  const form = useForm<Values>({
    resolver: zodResolver(schema.zod as unknown as ZodObject<ZodRawShape>),
    defaultValues: defaults as FieldValues as Values,
    mode: "onChange",
  });

  // Run validation once on mount so `formState.isValid` reflects reality
  // from the first render (without this, `mode: "onChange"` leaves it
  // false until the user touches a field).
  //
  // Deliberately mount-only. NodeForm already has `key={node.id}` on its
  // parent — when the user picks a different node, this whole component
  // remounts with fresh defaults already injected via `useForm`. Calling
  // `form.reset(defaults)` on every render of the SAME node was the
  // root cause of "Save button doesn't stay highlighted": React Flow
  // mutates its `nodes` array on any mouse move, which changed the
  // `node` reference upstream, which invalidated the `defaults` memo,
  // which fired this effect, which wiped the user's in-progress edits
  // AND the dirty flag.
  React.useEffect(() => {
    void form.trigger();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const [label, setLabel] = React.useState(node.label);
  // Resync local label state only when the label string itself changes
  // (not on every parent re-render that hands us a new node reference).
  React.useEffect(() => setLabel(node.label), [node.label]);

  const [showAdvanced, setShowAdvanced] = React.useState(false);
  const [dirty, setDirty] = React.useState(false);

  // ---- U7: Burner spec-mode plumbing -------------------------------------
  // Which side of the energy balance is pinned. Watching the form (not
  // node.params) means section membership and the disabled treatment react
  // immediately as the user flips the radio, before Save.
  const burnerSpecMode =
    node.kind === "burner"
      ? (form.watch("spec_mode" as Path<Values>) as unknown as string)
      : undefined;
  const fuelModeActive = burnerSpecMode === "fuel_mass_flow";

  // Dynamic section membership: in fuel mode the fuel-flow field is an
  // essential (it IS the burner spec), not an advanced extra. This is
  // membership promotion — not auto-expanding the Advanced section.
  const { essentialFields, advancedFields } = React.useMemo(() => {
    if (node.kind !== "burner" || !fuelModeActive) {
      return {
        essentialFields: schema.essentials,
        advancedFields: schema.advanced,
      };
    }
    const fuelField = schema.advanced.find(
      (f) => f.key === "fuel_mass_flow_kg_s",
    );
    if (!fuelField) {
      return {
        essentialFields: schema.essentials,
        advancedFields: schema.advanced,
      };
    }
    const essentials = [...schema.essentials];
    const modeIdx = essentials.findIndex((f) => f.key === "spec_mode");
    essentials.splice(modeIdx + 1, 0, fuelField);
    return {
      essentialFields: essentials,
      advancedFields: schema.advanced.filter(
        (f) => f.key !== "fuel_mass_flow_kg_s",
      ),
    };
  }, [node.kind, schema, fuelModeActive]);

  // The mode-INACTIVE field stays visible but disabled (text.disabled
  // treatment + a tooltip naming which mode activates it). It is NOT a
  // preview field — both values are persisted and solver-wired; only one
  // is the active spec at a time.
  const inactiveFieldKey =
    node.kind === "burner"
      ? fuelModeActive
        ? "outlet_temperature_K"
        : "fuel_mass_flow_kg_s"
      : undefined;
  const inactiveFieldReason = fuelModeActive
    ? "Back-derived by the solver in fuel-ṁ mode. Active in 'Outlet T (TIT)' spec mode — switch to edit it; the stored value is retained."
    : "Active in 'Fuel ṁ' spec mode — switch the spec mode to edit it; the stored value is retained.";

  // Fuel-mass-flow mode needs a real fuel stream. Air-standard / pure-fluid
  // projects run the burner as a heat exchanger (no combustion), so the
  // radio is disabled with an explanatory tooltip (the backend refuses the
  // same combination synchronously with a 422). Mirrors the backend's
  // three forcing sources: project settings flag, burner param, pure fluid.
  const fuelModeUnavailable =
    node.kind === "burner" &&
    ((project !== undefined && project.workingFluid !== "air") ||
      project?.airStandard === true ||
      node.params?.air_standard === true);
  const specModeOptionDisabled = fuelModeUnavailable
    ? {
        fuel_mass_flow:
          "Fuel mass-flow mode requires a combustion working fluid.",
      }
    : undefined;
  // -------------------------------------------------------------------------

  // ---- U9: rotor geometry presence (live mean-line messaging) -------------
  // Read via the RAW components endpoint: the cycle page's param
  // translation (KIND_TRANSLATIONS) deliberately does not surface
  // geometry_params, and this panel's form schema / PATCH path must not
  // grow it either — the candidate-detail handoff endpoint is the only
  // writer (U8). The conditional note / chip below the efficiency-mode
  // radio replaces the old warn-on-pick toast, which guessed.
  const isRotor = node.kind === "compressor" || node.kind === "turbine";
  const [geometryStatus, setGeometryStatus] =
    React.useState<RotorGeometryStatus>({ state: "unknown" });
  const projectId = project?.id;
  React.useEffect(() => {
    if (!isRotor || !projectId) return;
    const ctrl = new AbortController();
    void (async () => {
      try {
        const [components, settings] = await Promise.all([
          getRawComponents(projectId, ctrl.signal),
          getProjectSettings(projectId, ctrl.signal),
        ]);
        // The panel may have moved to another node while the fetch was in
        // flight — a slow response for node A must not land on node B.
        if (ctrl.signal.aborted) return;
        const rawComp = components.find((c) => c.id === node.id);
        const gp = rawComp?.params?.geometry_params;
        if (
          gp &&
          typeof gp === "object" &&
          !Array.isArray(gp) &&
          Object.keys(gp).length > 0
        ) {
          setGeometryStatus({
            state: "attached",
            keyCount: Object.keys(gp).length,
            sourceCandidateId: geometrySourceCandidateId(
              rawComp?.params,
              settings.active_candidate_id,
            ),
          });
        } else {
          setGeometryStatus({ state: "absent" });
        }
      } catch {
        // Backend unreachable — render neither note nor chip rather than
        // guessing at geometry presence.
        if (!ctrl.signal.aborted) setGeometryStatus({ state: "unknown" });
      }
    })();
    return () => ctrl.abort();
  }, [isRotor, projectId, node.id]);

  // Watch the in-form mode so the no-geometry note reacts as the user
  // flips the radio, before Save.
  const rotorEfficiencyMode = isRotor
    ? (form.watch("efficiency_mode" as Path<Values>) as unknown as string)
    : undefined;
  // -------------------------------------------------------------------------

  // Mirror local `dirty` into the global Cycle UI store so the Run button
  // (a sibling subtree) can warn the user that the solver will run against
  // un-flushed backend values. Also drives a `beforeunload` listener so an
  // accidental tab-close doesn't silently nuke in-progress edits.
  const setUnsavedEdits = useCycleUiStore((s) => s.setUnsavedEdits);
  React.useEffect(() => {
    setUnsavedEdits(dirty);
    return () => setUnsavedEdits(false);
  }, [dirty, setUnsavedEdits]);
  React.useEffect(() => {
    if (!dirty) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);

  // ADAPT-031: per-component material assignment. Lives outside the
  // react-hook-form because the picker has its own loading state and
  // we want the citation to render even when the form is pristine.
  const materialKindAccepts = MATERIAL_AWARE_KINDS.has(node.kind);
  const initialMaterial =
    typeof node.params?.material === "string"
      ? (node.params.material as string)
      : defaultMaterialFor(node.kind);
  const [material, setMaterial] = React.useState<string>(initialMaterial);
  React.useEffect(() => {
    setMaterial(initialMaterial);
  }, [initialMaterial]);

  // Debounced "needs re-solve" badge. Lights up 300 ms after the last edit
  // so the user knows their change hasn't propagated to the result yet.
  const [needsResolve, setNeedsResolve] = React.useState(false);
  const debounce = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  React.useEffect(() => {
    const sub = form.watch((_v, info) => {
      if (info.type !== "change") return;
      setDirty(true);
      if (debounce.current) clearTimeout(debounce.current);
      debounce.current = setTimeout(() => {
        setNeedsResolve(true);
      }, 300);

      // B19: Burner.fuel_species changes auto-update fuel_lhv (and on
      // unwired radios, B10/B11, surface a toast so the user knows the
      // option is preview-only).
      const name = info.name as string | undefined;
      if (node.kind === "burner" && name === "fuel_species") {
        const species = (
          form.getValues() as unknown as { fuel_species?: string }
        ).fuel_species;
        const lhv = FUEL_LHV_DEFAULTS[species ?? ""];
        if (typeof lhv === "number") {
          form.setValue(
            "fuel_lhv_MJ_per_kg" as Path<typeof defaults>,
            lhv as unknown as (typeof defaults)["fuel_lhv_MJ_per_kg"],
            { shouldDirty: true, shouldValidate: true },
          );
        }
      }
      // U7: fuel-mass-flow mode is fully wired — entering it seeds a
      // kind-typical default (~0.002 kg/s, the C30-class natural-gas
      // flow) when the field is empty, so the user lands on a solvable
      // value instead of a zod error.
      if (node.kind === "burner" && name === "spec_mode") {
        const vals = form.getValues() as unknown as {
          spec_mode?: string;
          fuel_mass_flow_kg_s?: number;
        };
        if (vals.spec_mode === "fuel_mass_flow") {
          const cur = vals.fuel_mass_flow_kg_s;
          if (typeof cur !== "number" || !Number.isFinite(cur) || cur <= 0) {
            form.setValue(
              "fuel_mass_flow_kg_s" as Path<typeof defaults>,
              0.002 as unknown as (typeof defaults)["fuel_mass_flow_kg_s"],
              { shouldDirty: true, shouldValidate: true },
            );
          }
        }
      }
      // U9: live_meanline no longer warns on pick — the conditional
      // geometry note / chip below the mode radio carries the messaging
      // (it knows whether geometry is actually attached; the old B12-era
      // toast guessed). Polytropic keeps its preview-only warning.
      if (
        (node.kind === "compressor" || node.kind === "turbine") &&
        name === "efficiency_mode"
      ) {
        const mode = (
          form.getValues() as unknown as { efficiency_mode?: string }
        ).efficiency_mode;
        if (mode === "polytropic") {
          toast.warning("Polytropic mode is preview-only", {
            description:
              "Cycle solver still uses isentropic η on this code path. Run the Analysis page mean-line solver for polytropic.",
          });
        }
      }
    });
    return () => {
      sub.unsubscribe();
      // The 300 ms "needs re-solve" timer would otherwise fire setState
      // after unmount (or after the panel re-keyed to another node).
      if (debounce.current) clearTimeout(debounce.current);
    };
  }, [form, node.kind, defaults]);

  const submit = form.handleSubmit(
    async (values) => {
      const params: Record<string, number | string | boolean> = {};
      const allFields = [...schema.essentials, ...schema.advanced];
      for (const f of allFields) {
        const v = (values as Record<string, unknown>)[f.key];
        if (f.kind === "select" || f.kind === "radio") {
          if (typeof v === "string" && v.length > 0) params[f.key] = v;
        } else {
          const n = typeof v === "number" ? v : Number(v);
          if (!Number.isFinite(n)) continue;
          params[f.key] = f.fromDisplay ? f.fromDisplay(n) : n;
        }
      }
      // Preserve any read-only badge fields untouched (geometry_type etc.)
      for (const b of schema.readonlyBadges ?? []) {
        const raw = node.params?.[b.key];
        if (raw !== undefined) params[b.key] = raw;
      }
      // ADAPT-031: persist material selection if this kind accepts one.
      if (materialKindAccepts && material) {
        params.material = material;
      }
      try {
        await onPatch(node.id, { label, params });
        // Re-baseline both dirty signals:
        //  - `setDirty(false)` clears the manual flag fed from `form.watch`.
        //  - `form.reset(values)` rebases RHF's `formState.isDirty` so the
        //    just-saved values become the new "clean" baseline.
        setDirty(false);
        form.reset(values, {
          keepValues: false,
          keepDirty: false,
          keepErrors: false,
        });
        setNeedsResolve(false);
        toast.success("Component saved.");
      } catch (err) {
        toast.error("Could not save", {
          description: (err as Error).message,
        });
      }
    },
    // Invalid-form handler. Surface the first field error so the user
    // can see WHY the form refused — without this, a default value that
    // silently fails zod (e.g. zero where positive is required) just
    // sits there with a grey button and no explanation.
    (errors) => {
      const firstKey = Object.keys(errors)[0];
      const firstErr = firstKey
        ? (errors[firstKey as keyof typeof errors] as { message?: string })
        : undefined;
      const allFields = [...schema.essentials, ...schema.advanced];
      const label = allFields.find((f) => f.key === firstKey)?.label ?? firstKey;
      toast.error("Cannot save — fix the highlighted field", {
        description: label
          ? `${label}: ${firstErr?.message ?? "invalid value"}`
          : (firstErr?.message ?? "validation failed"),
      });
    },
  );

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
      className="flex flex-col gap-4"
    >
      {/* --- Header --- */}
      <section className="flex flex-col gap-2">
        <Label htmlFor="node-label">Label</Label>
        <Input
          id="node-label"
          value={label}
          data-input="true"
          onChange={(e) => {
            setLabel(e.target.value);
            setDirty(true);
          }}
        />
        {(schema.readonlyBadges?.length ?? 0) > 0 && (
          <div className="flex flex-wrap items-center gap-1">
            {schema.readonlyBadges?.map((b) => {
              const v = node.params?.[b.key];
              if (v === undefined) return null;
              return (
                <Badge key={b.key} variant="outline">
                  {b.prefix && (
                    <span className="text-text-muted">{b.prefix}:</span>
                  )}
                  <span className="font-mono">{String(v)}</span>
                </Badge>
              );
            })}
          </div>
        )}
        {needsResolve && (
          <Badge variant="warning" className="self-start">
            needs re-solve
          </Badge>
        )}
      </section>

      {/* --- Preview banner (whole-kind not wired to solver) --- */}
      {schema.previewBanner && (
        <div className="flex items-start gap-2 rounded-md border border-semantic-warning/40 bg-semantic-warning-surface/40 p-2 text-[11px] text-text">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-semantic-warning-text" />
          <span className="leading-snug">{schema.previewBanner}</span>
        </div>
      )}

      {/* --- Material (ADAPT-031) --- */}
      {materialKindAccepts && (
        <FormSection title="Material">
          <MaterialPicker
            id={`material-${node.id}`}
            value={material}
            highTempOnly={
              node.kind === "turbine" ||
              node.kind === "burner" ||
              node.kind === "recuperator"
            }
            onChange={(name) => {
              setMaterial(name);
              setDirty(true);
              setNeedsResolve(true);
            }}
          />
        </FormSection>
      )}

      {/* --- Essentials --- */}
      {essentialFields.length > 0 && (
        <FormSection title="Essentials">
          {essentialFields.map((f) => (
            <React.Fragment key={f.key}>
              <FieldRenderer
                field={f}
                form={form}
                disabled={f.key === inactiveFieldKey}
                disabledReason={
                  f.key === inactiveFieldKey ? inactiveFieldReason : undefined
                }
                optionDisabled={
                  f.key === "spec_mode" ? specModeOptionDisabled : undefined
                }
              />
              {/* U9: conditional geometry messaging below the mode radio. */}
              {f.key === "efficiency_mode" && isRotor && (
                <RotorGeometryNote
                  kind={node.kind as "compressor" | "turbine"}
                  mode={rotorEfficiencyMode}
                  status={geometryStatus}
                />
              )}
            </React.Fragment>
          ))}
        </FormSection>
      )}

      {/* --- Advanced (collapsed) --- */}
      {advancedFields.length > 0 && (
        <FormSection
          title="Advanced"
          collapsible
          open={showAdvanced}
          onToggle={() => setShowAdvanced((v) => !v)}
        >
          {showAdvanced &&
            advancedFields.map((f) => (
              <FieldRenderer
                key={f.key}
                field={f}
                form={form}
                disabled={f.key === inactiveFieldKey}
                disabledReason={
                  f.key === inactiveFieldKey ? inactiveFieldReason : undefined
                }
              />
            ))}
        </FormSection>
      )}

      {result && (
        <FormSection title="Last-run result">
          {typeof result.shaftWork === "number" && (
            <FieldRow label="Shaft work">
              <ComputedValue value={result.shaftWork} unit="kW" />
            </FieldRow>
          )}
          {typeof result.outletTemperature === "number" && (
            <FieldRow label="Outlet Tt">
              <ComputedValue value={result.outletTemperature} unit="K" />
            </FieldRow>
          )}
          {typeof result.outletPressure === "number" && (
            <FieldRow label="Outlet Pt">
              <ComputedValue value={result.outletPressure} unit="kPa" />
            </FieldRow>
          )}
          {typeof result.outletMassFlow === "number" && (
            <FieldRow label="Outlet ṁ">
              <ComputedValue value={result.outletMassFlow} unit="kg/s" />
            </FieldRow>
          )}
        </FormSection>
      )}

      <div className="mt-2 flex items-center justify-between gap-2">
        <Button
          type="submit"
          className="gap-1.5"
          // Belt-and-braces dirty check. The manual `dirty` state is driven
          // by `form.watch`'s `info.type === "change"` callback — robust
          // for QuantityInput / Select / Radio fields that go through
          // `form.setValue(..., { shouldDirty: true })`. If watch somehow
          // misses an event (e.g. RHF resubscribed mid-keystroke because
          // the parent passed a new `node` reference), `formState.isDirty`
          // still flips because RHF tracks each field's diff against its
          // defaultValues baseline independently. Either signal enables
          // Save — guaranteeing the button lights up the moment the user
          // changes anything.
          disabled={
            form.formState.isSubmitting ||
            (!dirty && !form.formState.isDirty)
          }
        >
          <Save className="h-3.5 w-3.5" /> Save
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon">
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem
              onSelect={async (e) => {
                e.preventDefault();
                try {
                  await onDelete(node.id);
                  toast.success("Component removed.");
                } catch (err) {
                  toast.error("Could not remove", {
                    description: (err as Error).message,
                  });
                }
              }}
              className="text-semantic-danger-text focus:bg-semantic-danger-surface"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Delete component
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </form>
  );
}

/* ---------------------------------------------------------------------------
 * U9 — rotor geometry messaging below the efficiency-mode radio.
 * ------------------------------------------------------------------------- */

type RotorGeometryStatus =
  | { state: "unknown" }
  | { state: "absent" }
  | { state: "attached"; keyCount: number; sourceCandidateId?: string };

/**
 * Provenance for the geometry chip. Prefers the per-component
 * `geometry_source_candidate_id` param written by send-to-cycle (exact
 * provenance for the geometry actually attached) over the project-level pin
 * (`active_candidate_id`), which may name a different candidate than the
 * one sent. The params key is optional — projects written before it existed
 * fall back to the pin.
 *
 * Mirrored (plain JS) by src/__tests__/efficiency-sources.test.mjs.
 */
function geometrySourceCandidateId(
  params: Record<string, unknown> | undefined,
  activeCandidateId: unknown,
): string | undefined {
  const fromParams = params?.geometry_source_candidate_id;
  if (typeof fromParams === "string" && fromParams) return fromParams;
  return typeof activeCandidateId === "string" && activeCandidateId
    ? activeCandidateId
    : undefined;
}

/**
 * Conditional messaging for the live mean-line mode (replaces the B12-era
 * warn-on-pick toast):
 *   - geometry attached → a read-only chip (key count + source candidate
 *     when one is pinned), shown regardless of the selected mode;
 *   - no geometry AND live mean-line selected → an info note pointing at
 *     the candidate-detail handoff;
 *   - presence unknown (backend unreachable) → nothing, rather than a
 *     guess.
 */
function RotorGeometryNote({
  kind,
  mode,
  status,
}: {
  kind: "compressor" | "turbine";
  mode?: string;
  status: RotorGeometryStatus;
}) {
  if (status.state === "attached") {
    return (
      <div className="flex items-center gap-1.5 self-start rounded-sm border border-border-subtle bg-surface-subtle/60 px-2 py-1 text-[11px] text-text-muted">
        <Box className="h-3 w-3 shrink-0" aria-hidden="true" />
        <span>
          Geometry attached · {status.keyCount}{" "}
          {status.keyCount === 1 ? "key" : "keys"}
          {status.sourceCandidateId && (
            <>
              {" · candidate "}
              <span className="font-mono">
                {status.sourceCandidateId.slice(0, 8)}
              </span>
            </>
          )}
        </span>
      </div>
    );
  }
  if (status.state === "absent" && mode === "live_meanline") {
    return (
      <div className="flex items-start gap-2 rounded-sm border border-border-subtle bg-surface-subtle/40 p-2 text-[11px] leading-snug text-text">
        <Info
          className="mt-0.5 h-3.5 w-3.5 shrink-0 text-text-muted"
          aria-hidden="true"
        />
        <span>
          {kind === "compressor"
            ? "Live mean-line needs compressor geometry — open a candidate in Flow Path and use “Send to cycle”."
            : "Live mean-line needs turbine geometry attached to this component — no geometry is attached."}{" "}
          Until then the solve falls back to constant isentropic η, and the
          result panel flags the fallback.
        </span>
      </div>
    );
  }
  return null;
}

/* ---------------------------------------------------------------------------
 * Section + field primitives
 * ------------------------------------------------------------------------- */

function FormSection({
  title,
  children,
  collapsible,
  open,
  onToggle,
}: {
  title: string;
  children: React.ReactNode;
  collapsible?: boolean;
  open?: boolean;
  onToggle?: () => void;
}) {
  return (
    <section className="flex flex-col gap-3">
      {collapsible ? (
        <button
          type="button"
          onClick={onToggle}
          className="-mx-1 flex items-center gap-1 rounded-sm px-1 py-0.5 text-left text-xs font-semibold uppercase tracking-wide text-text-muted hover:bg-surface-subtle/60"
        >
          {open ? (
            <ChevronDown className="h-3 w-3" />
          ) : (
            <ChevronRight className="h-3 w-3" />
          )}
          {title}
        </button>
      ) : (
        <h3 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
          {title}
        </h3>
      )}
      {children}
    </section>
  );
}

function FieldRenderer<TValues extends FieldValues>({
  field,
  form,
  disabled,
  disabledReason,
  optionDisabled,
}: {
  field: ParamField;
  form: UseFormReturn<TValues>;
  /** Mode-inactive treatment (U7): visible, text.disabled, tooltip. */
  disabled?: boolean;
  disabledReason?: string;
  /** Per-option disable map for radio fields: value → tooltip reason. */
  optionDisabled?: Record<string, string>;
}) {
  const kind = field.kind ?? "quantity";
  if (kind === "select") return <SelectField field={field} form={form} />;
  if (kind === "radio")
    return (
      <RadioField field={field} form={form} optionDisabled={optionDisabled} />
    );
  return (
    <FormQuantityField
      field={field}
      form={form}
      disabled={disabled}
      disabledReason={disabledReason}
    />
  );
}

function SelectField<TValues extends FieldValues>({
  field,
  form,
}: {
  field: ParamField;
  form: UseFormReturn<TValues>;
}) {
  const value = form.watch(field.key as Path<TValues>) as unknown as string;
  return (
    <div className="flex flex-col gap-1">
      <FieldLabel field={field} />
      <Select
        value={value ?? ""}
        onValueChange={(v) =>
          form.setValue(
            field.key as Path<TValues>,
            v as unknown as TValues[Path<TValues>],
            { shouldDirty: true, shouldValidate: true },
          )
        }
      >
        <SelectTrigger id={`f-${field.key}`}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {(field.options ?? []).map((o) => (
            <SelectItem key={o.value} value={o.value}>
              {o.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

function RadioField<TValues extends FieldValues>({
  field,
  form,
  optionDisabled,
}: {
  field: ParamField;
  form: UseFormReturn<TValues>;
  /** value → tooltip reason for options that can't be picked here. */
  optionDisabled?: Record<string, string>;
}) {
  const value = form.watch(field.key as Path<TValues>) as unknown as string;
  const set = (v: string) =>
    form.setValue(
      field.key as Path<TValues>,
      v as unknown as TValues[Path<TValues>],
      { shouldDirty: true, shouldValidate: true },
    );
  return (
    <div className="flex flex-col gap-1">
      <FieldLabel field={field} />
      <div
        role="radiogroup"
        className="inline-flex rounded-sm border border-border-subtle bg-surface-raised p-0.5"
      >
        {(field.options ?? []).map((o) => {
          const active = value === o.value;
          const reason = optionDisabled?.[o.value];
          if (reason) {
            // Disabled-but-discoverable: keep the button focusable
            // (aria-disabled, not the `disabled` attribute, which would
            // drop it from the tab order) so the explanatory tooltip
            // fires on hover AND keyboard focus.
            return (
              <Tooltip key={o.value}>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    role="radio"
                    aria-checked={active}
                    aria-disabled="true"
                    onClick={(e) => e.preventDefault()}
                    className="cursor-not-allowed rounded-sm px-2 py-0.5 text-xs font-medium text-text-disabled"
                  >
                    {o.label}
                  </button>
                </TooltipTrigger>
                <TooltipContent>{reason}</TooltipContent>
              </Tooltip>
            );
          }
          return (
            <button
              key={o.value}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => set(o.value)}
              className={cn(
                "rounded-sm px-2 py-0.5 text-xs font-medium transition-colors duration-fast",
                active
                  ? "bg-brand-surface text-brand-text"
                  : "text-text-muted hover:text-text",
              )}
            >
              {o.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function FormQuantityField<TValues extends FieldValues>({
  field,
  form,
  disabled,
  disabledReason,
}: {
  field: ParamField;
  form: UseFormReturn<TValues>;
  /** Mode-inactive treatment (U7): visible, text.disabled, tooltip. */
  disabled?: boolean;
  disabledReason?: string;
}) {
  const value = form.watch(field.key as Path<TValues>) as unknown as number;
  const error = form.formState.errors[field.key]?.message as string | undefined;
  const [unit, setUnit] = React.useState(field.defaultUnit);
  const set = (n: number) =>
    form.setValue(
      field.key as Path<TValues>,
      n as unknown as TValues[Path<TValues>],
      {
        shouldDirty: true,
        shouldValidate: true,
      },
    );
  /**
   * Unit dropdown change: convert the *visible* number from the previous
   * unit into the new one so the user doesn't see "101.325 bar" after
   * swapping from kPa. The form's canonical value is always re-stored in
   * the new unit (it is just a number — the unit lives in this local
   * useState).
   *
   * If the conversion is unknown the value passes through unchanged
   * (best-effort). We deliberately don't try to be exhaustive: the units
   * list per field is small and curated upstream.
   */
  const onUnitChange = (next: string) => {
    if (next === unit) return;
    const converted = convertDisplay(value, unit, next);
    if (Number.isFinite(converted) && converted !== value) {
      set(converted);
    }
    setUnit(next);
  };
  const input = (
    <QuantityInput
      id={`f-${field.key}`}
      value={value}
      unit={unit}
      units={field.units}
      onValueChange={set}
      onUnitChange={onUnitChange}
      min={field.min}
      max={field.max}
      step={field.step}
      error={disabled ? undefined : error}
      disabled={disabled}
    />
  );
  if (disabled && disabledReason) {
    // Mode-inactive field (U7): stays visible with the text.disabled token
    // treatment so the retained value is never hidden, and the wrapper is
    // focusable so the "which mode activates this" tooltip fires on hover
    // AND keyboard focus (a disabled <input> drops out of the tab order).
    return (
      <div className="flex flex-col gap-1">
        <FieldLabel field={field} disabled />
        <Tooltip>
          <TooltipTrigger asChild>
            <div
              tabIndex={0}
              aria-label={`${field.label} (inactive in this spec mode)`}
              className="rounded-sm outline-none focus-visible:ring-1 focus-visible:ring-border-default [&_input]:text-text-disabled"
            >
              {input}
            </div>
          </TooltipTrigger>
          <TooltipContent>{disabledReason}</TooltipContent>
        </Tooltip>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-1">
      <FieldLabel field={field} />
      {input}
    </div>
  );
}

/**
 * Display-unit conversion table used by FormQuantityField. Mirrors the
 * api-client `quantityToUnit` but operates on the *display* numbers
 * (e.g. kPa ↔ bar ↔ psi for inlet pressure, K ↔ °C for temperatures).
 *
 * Best-effort: unknown pairs pass through unchanged. Keep this list
 * consistent with the `units` arrays declared per field in SCHEMAS.
 */
function convertDisplay(v: number, from: string, to: string): number {
  if (!Number.isFinite(v) || from === to) return v;
  const key = `${from}->${to}`;
  switch (key) {
    // Pressure
    case "kPa->bar":
      return v / 100;
    case "bar->kPa":
      return v * 100;
    case "kPa->psi":
      return v * 0.1450377;
    case "psi->kPa":
      return v / 0.1450377;
    case "bar->psi":
      return v * 14.50377;
    case "psi->bar":
      return v / 14.50377;
    // Temperature (absolute, total)
    case "K->°C":
      return v - 273.15;
    case "°C->K":
      return v + 273.15;
    default:
      return v;
  }
}

function FieldLabel({
  field,
  disabled,
}: {
  field: ParamField;
  disabled?: boolean;
}) {
  return (
    <Label htmlFor={`f-${field.key}`} className="flex items-center gap-1.5">
      <span className={disabled ? "text-text-disabled" : undefined}>
        {field.label}
      </span>
      {field.symbol && (
        <span
          className={cn(
            "font-mono text-[11px]",
            disabled ? "text-text-disabled" : "text-text-muted",
          )}
        >
          {field.symbol}
        </span>
      )}
      {field.wired === false && (
        <Tooltip>
          <TooltipTrigger asChild>
            <Badge
              variant="outline"
              className="border-semantic-warning/40 bg-semantic-warning-surface/40 px-1 py-0 text-[9px] uppercase tracking-wide text-semantic-warning-text"
            >
              preview
            </Badge>
          </TooltipTrigger>
          <TooltipContent>
            Saves & round-trips, but the Brayton-cycle solver doesn&apos;t
            consume this field yet.
          </TooltipContent>
        </Tooltip>
      )}
      {field.tooltip && (
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              aria-label="Field help"
              className="text-text-muted transition-colors hover:text-text"
              tabIndex={-1}
            >
              <HelpCircle className="h-3 w-3" />
            </button>
          </TooltipTrigger>
          <TooltipContent>{field.tooltip}</TooltipContent>
        </Tooltip>
      )}
    </Label>
  );
}

function FieldRow({
  label,
  symbol,
  children,
}: {
  label: string;
  symbol?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <Label className={cn("flex items-center gap-2 text-xs text-text-muted")}>
        <span>{label}</span>
        {symbol && (
          <span className="font-mono text-[11px]">{symbol}</span>
        )}
      </Label>
      {children}
    </div>
  );
}

/* ---------------------------------------------------------------------------
 * Material-picker helpers (ADAPT-031)
 *
 * Which node kinds carry a material assignment, and what the
 * engineering default is. The recuperator default of Inconel 625 was
 * specifically flagged by the Concepts NREC review (the Capstone C30
 * recuperator is HX / Inconel 625, not 4340 steel).
 * ------------------------------------------------------------------------- */

const MATERIAL_AWARE_KINDS = new Set<CycleNodeKind>([
  "compressor",
  "turbine",
  "burner",
  "recuperator",
  "intercooler",
]);

/**
 * Engineering LHV defaults per fuel species. Used by the Burner form to
 * auto-update `fuel_lhv_MJ_per_kg` when the user picks a different
 * species — without this, JP-8 stays at CH4's 50 MJ/kg until the user
 * notices and edits manually.
 *
 * Citations:
 *   - CH4: 50.0 MJ/kg (NIST WebBook lower-heating value, 298 K).
 *   - JP-4: 43.5 MJ/kg (NATO STANAG 3747, broad-cut kerosene).
 *   - JP-8: 43.0 MJ/kg (MIL-DTL-83133 kerosene).
 *   - "generic" leaves the user value untouched.
 */
const FUEL_LHV_DEFAULTS: Record<string, number | undefined> = {
  CH4: 50.0,
  "JP-4": 43.5,
  "JP-8": 43.0,
  generic: undefined,
};

function defaultMaterialFor(kind: CycleNodeKind): string {
  switch (kind) {
    case "turbine":
      // Hot-section turbine wheel — IN-718 is the aero-engine standard.
      return "Inconel 718";
    case "burner":
      return "Haynes 282";
    case "recuperator":
      // Capstone-class microturbine recuperators: Inconel 625 / HX.
      return "Inconel 625";
    case "intercooler":
      return "316L";
    case "compressor":
    default:
      // Compressor impeller — 17-4PH is the workhorse for centrifugal
      // pumps and compressor wheels.
      return "17-4PH";
  }
}

function humanKind(kind: CycleNodeKind): string {
  switch (kind) {
    case "compressor":
      return "Compressor";
    case "turbine":
      return "Turbine";
    case "burner":
      return "Combustor";
    case "recuperator":
      return "Recuperator";
    case "intercooler":
      return "Intercooler";
    case "mixer":
      return "Mixer";
    case "splitter":
      return "Splitter";
    case "duct":
      return "Duct";
    case "inlet":
      return "Inlet";
    case "outlet":
      return "Outlet";
    case "shaft":
      return "Shaft";
  }
}
