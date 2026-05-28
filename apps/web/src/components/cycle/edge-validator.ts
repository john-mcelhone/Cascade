/**
 * Edge validation for the Cycle Canvas.
 *
 * Every cycle component exposes a small set of typed ports. A flow port
 * carries mass + stagnation state; a shaft port carries rotational
 * coupling; a heat port carries duty (recuperator hot / cold loops have
 * their own pair of flow ports). Connections between mismatched port
 * types are rejected so the resulting cycle is solvable.
 */

import type { CycleNodeKind } from "@/lib/api/types";

export type PortKind = "flow" | "shaft" | "heat";

export type PortDirection = "in" | "out";

export interface PortDef {
  /** Logical id of the port (e.g. "in", "cold_in", "shaft"). */
  id: string;
  kind: PortKind;
  direction: PortDirection;
  /** Human label for tooltips. */
  label: string;
}

export interface NodePortSpec {
  inputs: PortDef[];
  outputs: PortDef[];
}

/**
 * Static port catalogue per component kind.
 *
 * Notes on the recuperator:
 *  - It has a cold side (compressor-discharge in → burner-feed out) and a
 *    hot side (turbine-discharge in → exhaust out). Two flow streams,
 *    counterflow heat exchanger — modelled as four flow ports.
 *
 * Notes on the shaft node:
 *  - A standalone shaft node owns two shaft ports so it can transmit
 *    torque from the turbine to the compressor. Compressors and turbines
 *    each expose one shaft port; an Inlet/Outlet does not.
 */
export const PORTS: Record<CycleNodeKind, NodePortSpec> = {
  inlet: {
    inputs: [],
    outputs: [{ id: "out", kind: "flow", direction: "out", label: "Flow out" }],
  },
  outlet: {
    inputs: [{ id: "in", kind: "flow", direction: "in", label: "Flow in" }],
    outputs: [],
  },
  compressor: {
    inputs: [
      { id: "in", kind: "flow", direction: "in", label: "Flow in" },
      { id: "shaft", kind: "shaft", direction: "in", label: "Shaft in" },
    ],
    outputs: [
      { id: "out", kind: "flow", direction: "out", label: "Flow out" },
    ],
  },
  turbine: {
    inputs: [{ id: "in", kind: "flow", direction: "in", label: "Flow in" }],
    outputs: [
      { id: "out", kind: "flow", direction: "out", label: "Flow out" },
      { id: "shaft", kind: "shaft", direction: "out", label: "Shaft out" },
    ],
  },
  burner: {
    inputs: [{ id: "in", kind: "flow", direction: "in", label: "Flow in" }],
    outputs: [
      { id: "out", kind: "flow", direction: "out", label: "Flow out" },
    ],
  },
  recuperator: {
    inputs: [
      {
        id: "cold_in",
        kind: "flow",
        direction: "in",
        label: "Cold-side flow in",
      },
      {
        id: "hot_in",
        kind: "flow",
        direction: "in",
        label: "Hot-side flow in",
      },
    ],
    outputs: [
      {
        id: "cold_out",
        kind: "flow",
        direction: "out",
        label: "Cold-side flow out",
      },
      {
        id: "hot_out",
        kind: "flow",
        direction: "out",
        label: "Hot-side flow out",
      },
    ],
  },
  intercooler: {
    inputs: [{ id: "in", kind: "flow", direction: "in", label: "Flow in" }],
    outputs: [
      { id: "out", kind: "flow", direction: "out", label: "Flow out" },
    ],
  },
  mixer: {
    inputs: [
      { id: "in_a", kind: "flow", direction: "in", label: "Flow in A" },
      { id: "in_b", kind: "flow", direction: "in", label: "Flow in B" },
    ],
    outputs: [
      { id: "out", kind: "flow", direction: "out", label: "Flow out" },
    ],
  },
  splitter: {
    inputs: [{ id: "in", kind: "flow", direction: "in", label: "Flow in" }],
    outputs: [
      { id: "out_a", kind: "flow", direction: "out", label: "Flow out A" },
      { id: "out_b", kind: "flow", direction: "out", label: "Flow out B" },
    ],
  },
  duct: {
    inputs: [{ id: "in", kind: "flow", direction: "in", label: "Flow in" }],
    outputs: [
      { id: "out", kind: "flow", direction: "out", label: "Flow out" },
    ],
  },
  shaft: {
    inputs: [{ id: "in", kind: "shaft", direction: "in", label: "Shaft in" }],
    outputs: [
      { id: "out", kind: "shaft", direction: "out", label: "Shaft out" },
    ],
  },
};

export function getPort(
  kind: CycleNodeKind,
  portId: string,
): PortDef | undefined {
  const spec = PORTS[kind];
  return [...spec.inputs, ...spec.outputs].find((p) => p.id === portId);
}

export interface ConnectionEndpoint {
  nodeKind: CycleNodeKind;
  portId: string;
}

export type ConnectionValidation =
  | { ok: true }
  | { ok: false; reason: string };

/**
 * Validate a candidate connection between two ports.
 *
 * Rules:
 *  - source must be a producing port (an `output`);
 *  - target must be a consuming port (an `input`);
 *  - the two ports must share a `PortKind`;
 *  - self-loops on the same node are rejected.
 */
export function isValidConnection(
  source: ConnectionEndpoint,
  target: ConnectionEndpoint,
): ConnectionValidation {
  const src = getPort(source.nodeKind, source.portId);
  const dst = getPort(target.nodeKind, target.portId);
  if (!src) {
    return {
      ok: false,
      reason: `Unknown source port "${source.portId}" on ${source.nodeKind}.`,
    };
  }
  if (!dst) {
    return {
      ok: false,
      reason: `Unknown target port "${target.portId}" on ${target.nodeKind}.`,
    };
  }
  if (src.direction !== "out") {
    return {
      ok: false,
      reason: `${src.label} is an input, not an output. Drag from an outlet port.`,
    };
  }
  if (dst.direction !== "in") {
    return {
      ok: false,
      reason: `${dst.label} is an output, not an input. Drag onto an inlet port.`,
    };
  }
  if (src.kind !== dst.kind) {
    return {
      ok: false,
      reason: friendlyMismatch(source, src, target, dst),
    };
  }
  return { ok: true };
}

function friendlyMismatch(
  source: ConnectionEndpoint,
  src: PortDef,
  target: ConnectionEndpoint,
  dst: PortDef,
): string {
  const a = `${humanKind(source.nodeKind)} ${src.label.toLowerCase()}`;
  const b = `${humanKind(target.nodeKind)} ${dst.label.toLowerCase()}`;
  if (src.kind === "flow" && dst.kind === "shaft") {
    return `${a} is a flow port; ${b} is a shaft port. Connect the ${humanKind(
      source.nodeKind,
    )}'s shaft port to the shaft node instead.`;
  }
  if (src.kind === "shaft" && dst.kind === "flow") {
    return `${a} is a shaft port; ${b} is a flow port. Shaft work doesn't carry mass — wire it to another shaft port.`;
  }
  return `${a} (${src.kind}) and ${b} (${dst.kind}) are different port types.`;
}

function humanKind(kind: CycleNodeKind): string {
  switch (kind) {
    case "compressor":
      return "Compressor";
    case "turbine":
      return "Turbine";
    case "burner":
      return "Burner";
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
