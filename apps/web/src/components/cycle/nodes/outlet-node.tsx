"use client";

import { LogOut } from "lucide-react";
import { BaseNode, type CycleNodeData } from "./base-node";
import type { NodeProps } from "@xyflow/react";

/** Outlet — boundary sink (exhaust to ambient, dump to a reservoir, etc.). */
export function OutletNode(props: NodeProps) {
  return (
    <BaseNode
      {...props}
      data={props.data as CycleNodeData}
      family="Outlet"
      icon={<LogOut className="h-3.5 w-3.5" />}
      accent="bg-surface-subtle"
    />
  );
}
