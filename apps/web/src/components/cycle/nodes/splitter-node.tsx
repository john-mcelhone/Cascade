"use client";

import { GitBranch } from "lucide-react";
import { BaseNode, type CycleNodeData } from "./base-node";
import type { NodeProps } from "@xyflow/react";

/** Splitter — divides one flow stream into two by mass-flow fraction. */
export function SplitterNode(props: NodeProps) {
  return (
    <BaseNode
      {...props}
      data={props.data as CycleNodeData}
      family="Splitter"
      icon={<GitBranch className="h-3.5 w-3.5" />}
    />
  );
}
