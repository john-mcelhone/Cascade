"use client";

import { GitMerge } from "lucide-react";
import { BaseNode, type CycleNodeData } from "./base-node";
import type { NodeProps } from "@xyflow/react";

/** Mixer — combines two flow streams into one. */
export function MixerNode(props: NodeProps) {
  return (
    <BaseNode
      {...props}
      data={props.data as CycleNodeData}
      family="Mixer"
      icon={<GitMerge className="h-3.5 w-3.5" />}
    />
  );
}
