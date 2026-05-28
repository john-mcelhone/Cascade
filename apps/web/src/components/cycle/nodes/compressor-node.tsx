"use client";

import { ArrowUpRight } from "lucide-react";
import { BaseNode, type CycleNodeData } from "./base-node";
import type { NodeProps } from "@xyflow/react";

/**
 * Compressor — adds total pressure at the cost of shaft work.
 * Visually marked with an ascending arrow (low → high pressure).
 */
export function CompressorNode(props: NodeProps) {
  return (
    <BaseNode
      {...props}
      data={props.data as CycleNodeData}
      family="Compressor"
      icon={<ArrowUpRight className="h-3.5 w-3.5" />}
    />
  );
}
