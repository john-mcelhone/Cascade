"use client";

import { Cog } from "lucide-react";
import { BaseNode, type CycleNodeData } from "./base-node";
import type { NodeProps } from "@xyflow/react";

/**
 * Shaft — couples one or more turbines to one or more compressors at a
 * common rotational speed. Shaft-only ports (no mass flow).
 */
export function ShaftNode(props: NodeProps) {
  return (
    <BaseNode
      {...props}
      data={props.data as CycleNodeData}
      family="Shaft"
      icon={<Cog className="h-3.5 w-3.5" />}
      accent="bg-semantic-warning-surface/30"
    />
  );
}
