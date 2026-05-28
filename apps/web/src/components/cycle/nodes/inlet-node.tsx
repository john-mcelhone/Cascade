"use client";

import { LogIn } from "lucide-react";
import { BaseNode, type CycleNodeData } from "./base-node";
import type { NodeProps } from "@xyflow/react";

/** Inlet — boundary source carrying P, T, ṁ, and composition. */
export function InletNode(props: NodeProps) {
  return (
    <BaseNode
      {...props}
      data={props.data as CycleNodeData}
      family="Inlet"
      icon={<LogIn className="h-3.5 w-3.5" />}
      accent="bg-semantic-success-surface/40"
    />
  );
}
