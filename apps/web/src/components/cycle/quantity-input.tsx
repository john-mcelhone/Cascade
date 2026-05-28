"use client";

import * as React from "react";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

/**
 * A numeric input with an attached unit dropdown. Pure presentation —
 * the parent owns the canonical (SI) value and reads/writes via
 * value/onChange.
 */
export interface QuantityInputProps {
  value: number | undefined;
  unit: string;
  units: string[];
  onValueChange: (v: number) => void;
  onUnitChange?: (u: string) => void;
  min?: number;
  max?: number;
  step?: number;
  placeholder?: string;
  disabled?: boolean;
  /** When true, the input is highlighted yellow per design system §11. */
  userEditable?: boolean;
  error?: string;
  id?: string;
}

export function QuantityInput({
  value,
  unit,
  units,
  onValueChange,
  onUnitChange,
  min,
  max,
  step = 0.01,
  placeholder,
  disabled,
  userEditable = true,
  error,
  id,
}: QuantityInputProps) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-stretch gap-1">
        <Input
          id={id}
          type="number"
          value={value ?? ""}
          step={step}
          min={min}
          max={max}
          disabled={disabled}
          placeholder={placeholder}
          data-input={userEditable ? "true" : undefined}
          onChange={(e) => {
            const next = e.target.value;
            if (next === "") return;
            const num = Number(next);
            if (Number.isFinite(num)) onValueChange(num);
          }}
          className={cn(
            "flex-1",
            error && "border-semantic-danger focus:ring-semantic-danger",
          )}
        />
        {units.length === 1 ? (
          <div className="flex h-7 items-center rounded-sm border border-border-subtle bg-surface-computed px-2 text-xs text-text-muted">
            {unit}
          </div>
        ) : (
          <Select
            value={unit}
            disabled={disabled}
            onValueChange={(u) => onUnitChange?.(u)}
          >
            <SelectTrigger className="h-7 w-[80px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {units.map((u) => (
                <SelectItem key={u} value={u}>
                  {u}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>
      {error && (
        <p className="text-[11px] text-semantic-danger-text">{error}</p>
      )}
    </div>
  );
}

/**
 * Computed-only display: value + unit + copy button. Background is the
 * design-system computed surface to telegraph "not editable".
 */
export function ComputedValue({
  value,
  unit,
  formatter = (v) => v.toFixed(3).replace(/\.?0+$/, ""),
}: {
  value: number | undefined;
  unit: string;
  formatter?: (v: number) => string;
}) {
  const display =
    value === undefined || !Number.isFinite(value) ? "—" : formatter(value);
  return (
    <div className="flex h-7 items-center justify-between rounded-sm border border-border-subtle bg-surface-computed px-2 text-sm tabular-nums text-text">
      <span>{display}</span>
      <span className="text-xs text-text-muted">{unit}</span>
    </div>
  );
}
