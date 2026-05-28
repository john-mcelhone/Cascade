"use client";

import { ArrowDownRight } from "lucide-react";
import { BaseNode, type CycleNodeData } from "./base-node";
import type { NodeProps } from "@xyflow/react";

/**
 * Turbine — extracts shaft work from a high-energy stream.
 * Visually marked with a descending arrow (high → low pressure).
 */
export function TurbineNode(props: NodeProps) {
  return (
    <BaseNode
      {...props}
      data={props.data as CycleNodeData}
      family="Turbine"
      icon={<ArrowDownRight className="h-3.5 w-3.5" />}
    />
  );
}
