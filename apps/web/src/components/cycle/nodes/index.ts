"use client";

import type { NodeTypes } from "@xyflow/react";
import { CompressorNode } from "./compressor-node";
import { TurbineNode } from "./turbine-node";
import { BurnerNode } from "./burner-node";
import { RecuperatorNode } from "./recuperator-node";
import { IntercoolerNode } from "./intercooler-node";
import { MixerNode } from "./mixer-node";
import { SplitterNode } from "./splitter-node";
import { DuctNode } from "./duct-node";
import { InletNode } from "./inlet-node";
import { OutletNode } from "./outlet-node";
import { ShaftNode } from "./shaft-node";

export const cycleNodeTypes: NodeTypes = {
  compressor: CompressorNode,
  turbine: TurbineNode,
  burner: BurnerNode,
  recuperator: RecuperatorNode,
  intercooler: IntercoolerNode,
  mixer: MixerNode,
  splitter: SplitterNode,
  duct: DuctNode,
  inlet: InletNode,
  outlet: OutletNode,
  shaft: ShaftNode,
};

export type { CycleNodeData } from "./base-node";
