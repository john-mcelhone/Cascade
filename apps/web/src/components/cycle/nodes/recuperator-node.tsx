"use client";

import { ArrowLeftRight } from "lucide-react";
import { BaseNode, type CycleNodeData } from "./base-node";
import type { NodeProps } from "@xyflow/react";

/**
 * Recuperator — counterflow gas-gas heat exchanger. Two flow streams
 * (cold / hot), four flow ports.
 */
export function RecuperatorNode(props: NodeProps) {
  return (
    <BaseNode
      {...props}
      data={props.data as CycleNodeData}
      family="Recuperator"
      icon={<ArrowLeftRight className="h-3.5 w-3.5" />}
    />
  );
}
