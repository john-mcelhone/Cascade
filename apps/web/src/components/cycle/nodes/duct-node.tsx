"use client";

import { Minus } from "lucide-react";
import { BaseNode, type CycleNodeData } from "./base-node";
import type { NodeProps } from "@xyflow/react";

/** Duct — a constant-pressure-loss segment. */
export function DuctNode(props: NodeProps) {
  return (
    <BaseNode
      {...props}
      data={props.data as CycleNodeData}
      family="Duct"
      icon={<Minus className="h-3.5 w-3.5" />}
    />
  );
}
