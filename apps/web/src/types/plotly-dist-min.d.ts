/**
 * `plotly.js-dist-min` ships no TypeScript declarations. The runtime export
 * shape matches `plotly.js`, so we re-export those types and treat the
 * default import as the same factory-ready Plotly object.
 */

declare module "plotly.js-dist-min" {
  import type Plotly from "plotly.js";
  const _default: typeof Plotly;
  export default _default;
  // Re-export the runtime members in case anything reaches for them.
  export * from "plotly.js";
}
