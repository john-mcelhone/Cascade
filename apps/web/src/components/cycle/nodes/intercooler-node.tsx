"use client";

import { Snowflake } from "lucide-react";
import { BaseNode, type CycleNodeData } from "./base-node";
import type { NodeProps } from "@xyflow/react";

/** Intercooler — heat rejection between compressor stages. */
export function IntercoolerNode(props: NodeProps) {
  return (
    <BaseNode
      {...props}
      data={props.data as CycleNodeData}
      family="Intercooler"
      icon={<Snowflake className="h-3.5 w-3.5 text-semantic-info" />}
    />
  );
}
