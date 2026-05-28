"use client";

import { Flame } from "lucide-react";
import { BaseNode, type CycleNodeData } from "./base-node";
import type { NodeProps } from "@xyflow/react";

/** Combustor — heat addition at near-constant total pressure. */
export function BurnerNode(props: NodeProps) {
  return (
    <BaseNode
      {...props}
      data={props.data as CycleNodeData}
      family="Combustor"
      icon={<Flame className="h-3.5 w-3.5 text-semantic-warning" />}
    />
  );
}
