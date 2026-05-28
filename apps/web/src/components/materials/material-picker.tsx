"use client";

/**
 * Material picker (ADAPT-031).
 *
 * Lightweight `<select>` over the catalogue from `/api/materials`,
 * grouped by family. Used wherever a Cascade component needs a
 * material assignment (rotor sections, recuperator hot/cold path,
 * compressor impeller, turbine disc, fasteners).
 *
 * For v1 we keep the UI deliberately simple: a select, the citation
 * shown beneath as a 1-line caption, and the density / room-T
 * yield strength as informational badges. Advanced features (sort
 * by max service temperature, filter by family chip cloud,
 * temperature-property mini-charts) are queued for v1.1.
 */

import * as React from "react";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { getApiClient } from "@/lib/api";
import type { MaterialRecord } from "@/lib/api/types";

interface MaterialPickerProps {
  /** Current canonical material name (e.g. "Inconel 625"). Empty = unset. */
  value: string;
  onChange(name: string, record: MaterialRecord | undefined): void;
  /** Label shown above the select. Defaults to "Material". */
  label?: string;
  /** Optional id for label-input association. */
  id?: string;
  /** When true, only Ni-based superalloys + steels typical of high-T
   *  service show up. Used by hot-section editors so the operator does
   *  not accidentally specify a Ti alloy for a 900 °C blade. */
  highTempOnly?: boolean;
  /** Disable the control. */
  disabled?: boolean;
}

export function MaterialPicker({
  value,
  onChange,
  label = "Material",
  id = "material-picker",
  highTempOnly = false,
  disabled = false,
}: MaterialPickerProps) {
  const [records, setRecords] = React.useState<MaterialRecord[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getApiClient()
      .listMaterials()
      .then((list) => {
        if (cancelled) return;
        setRecords(list);
        setError(null);
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setError(err.message);
        setRecords([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Filter for hot-section service when requested.
  const filtered = React.useMemo(() => {
    if (!highTempOnly) return records;
    return records.filter(
      (m) =>
        m.family === "Ni-based superalloy" ||
        m.family === "Fe-Ni-Cr superalloy" ||
        // 316L is the borderline acceptable austenitic for 870 °C casings.
        m.name === "316L",
    );
  }, [records, highTempOnly]);

  const byFamily = React.useMemo(() => {
    const m = new Map<string, MaterialRecord[]>();
    for (const r of filtered) {
      const arr = m.get(r.family) ?? [];
      arr.push(r);
      m.set(r.family, arr);
    }
    return [...m.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [filtered]);

  const selected = filtered.find((m) => m.name === value);

  const handleChange = (next: string) => {
    onChange(next, filtered.find((m) => m.name === next));
  };

  return (
    <div className="flex flex-col gap-1">
      <Label htmlFor={id} className="flex items-center gap-1.5">
        <span>{label}</span>
        {selected && (
          <Badge variant="outline" className="font-mono text-[10px]">
            {selected.designation}
          </Badge>
        )}
      </Label>
      <Select
        value={value || ""}
        onValueChange={handleChange}
        disabled={disabled || loading}
      >
        <SelectTrigger id={id}>
          <SelectValue
            placeholder={
              loading ? "Loading materials…" : error ? "(offline)" : "Select…"
            }
          />
        </SelectTrigger>
        <SelectContent>
          {byFamily.map(([family, items]) => (
            <SelectGroup key={family}>
              <SelectLabel>{family}</SelectLabel>
              {items.map((m) => (
                <SelectItem key={m.name} value={m.name}>
                  {m.name}
                </SelectItem>
              ))}
            </SelectGroup>
          ))}
        </SelectContent>
      </Select>
      {selected && (
        <MaterialSummary record={selected} />
      )}
      {error && (
        <p className="text-[11px] text-semantic-danger-text">
          Could not load materials: {error}
        </p>
      )}
    </div>
  );
}

/**
 * One-line summary shown below the picker — density and yield at 293 K,
 * plus the citation. Designed to fit in the right-hand properties
 * panel's 320 px column without wrapping the citation.
 */
function MaterialSummary({ record }: { record: MaterialRecord }) {
  const yieldAt293 = record.yield_strength_MPa[0]?.[1];
  return (
    <div className="flex flex-col gap-1 rounded-md border border-border-subtle bg-surface-raised/60 px-2 py-1.5">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[11px] text-text-muted">
        <span>
          <span className="text-text-muted">ρ</span>{" "}
          <span className="font-mono text-text">
            {Math.round(record.density_kg_per_m3)}
          </span>{" "}
          kg/m³
        </span>
        {yieldAt293 !== undefined && (
          <span>
            <span className="text-text-muted">σ_y(293K)</span>{" "}
            <span className="font-mono text-text">
              {Math.round(yieldAt293)}
            </span>{" "}
            MPa
          </span>
        )}
        {record.max_service_temperature_K !== undefined &&
          record.max_service_temperature_K !== null && (
            <span>
              <span className="text-text-muted">T_max</span>{" "}
              <span className="font-mono text-text">
                {Math.round(record.max_service_temperature_K)}
              </span>{" "}
              K
            </span>
          )}
      </div>
      <p
        className="truncate text-[10px] italic text-text-muted"
        title={record.source}
      >
        {record.source}
      </p>
    </div>
  );
}
