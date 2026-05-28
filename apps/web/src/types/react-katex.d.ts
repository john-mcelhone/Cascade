/**
 * `react-katex` ships a single .d.ts that is actually a directory in npm; the
 * package's own typings are unusable in TS. This module shim declares the two
 * components we use.
 */
declare module "react-katex" {
  import type * as React from "react";
  import type { KatexOptions } from "katex";

  export interface KaTeXProps {
    math?: string;
    children?: string;
    block?: boolean;
    errorColor?: string;
    renderError?: (error: Error) => React.ReactNode;
    settings?: KatexOptions;
    as?: React.ElementType;
  }

  export const InlineMath: React.FC<KaTeXProps>;
  export const BlockMath: React.FC<KaTeXProps>;
}
