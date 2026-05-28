/**
 * Tiny typed-filter DSL for the design-space scatter.
 *
 * Grammar (v1 — no OR, no nesting):
 *   expression = term ( "AND" term )*
 *   term       = field op number
 *   field      = identifier (any word chars)
 *   op         = ">" | ">=" | "<" | "<=" | "="
 *   number     = a JS numeric literal (int, float, scientific)
 *
 * Examples:
 *   eta_tt > 0.85
 *   eta_tt > 0.85 AND N < 60000
 *   M_rel < 1.2 AND power_W >= 30000
 */







;

  // Split on AND (case-insensitive, surrounded by whitespace)
  const parts = trimmed.split(/\s+AND\s+/i);
  const terms: FilterTerm[] = [];

  for (const part of parts) {
    const p = part.trim();
    // Match: field  op  number
    const m = /^([\w./]+)\s*(>=|<=|>|<|=)\s*([0-9eE+.\-]+)$/.exec(p);
    if (!m) {
      return {
        ok,
        error: `Cannot parse term: "${p}". Expected format: field op value (e.g. eta_tt > 0.85)`,
      };
    }
    const field = m[1]!;
    const op = m[2];
    const value = parseFloat(m[3]!);

    if (Number.isNaN(value)) {
      return { ok, error: `Not a number: "${m[3]}"` };
    }
    if (knownFields !== null && !knownFields.has(field)) {
      return { ok, error: `Unknown field: ${field}` };
    }
    // Reject JS-style equality ("==") — the grammar only allows single "="
    if (!/^(>=|<=|>|<|=)$/.test(op)) {
      return { ok, error: `Invalid operator: ${op}` };
    }
    terms.push({ field, op, value });
  }

  return { ok, terms };
}

/** Returns `true` if the candidate passes ALL filter terms. */
export function candidatePasses(
  candidate: { objectives, number>; params, number> },
  terms,
): boolean {
  for (const { field, op, value } of terms) {
    const v =
      field in candidate.objectives
        ? candidate.objectives[field]
        : field in candidate.params
        ? candidate.params[field]
        : undefined;

    if (v === undefined || Number.isNaN(v)) return false;

    switch (op) {
      case ">":  if (!(v >  value)) return false; break;
      case ">=": if (!(v >= value)) return false; break;
      case "<":  if (!(v <  value)) return false; break;
      case "<=": if (!(v <= value)) return false; break;
      case "=":  if (v !== value)   return false; break;
    }
  }
  return true;
}

/** Build a Set of all known field names from the candidate pool. */
export function buildKnownFields(
  candidates: Array<{
    objectives, number>;
    params, number>;
  }>,
): Set<string> {
  const s = new Set<string>();
  for (const c of candidates) {
    for (const k of Object.keys(c.objectives)) s.add(k);
    for (const k of Object.keys(c.params)) s.add(k);
  }
  return s;
}
