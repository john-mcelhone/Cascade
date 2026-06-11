/**
 * Tiny zero-dependency syntax tokenizer for the docs code blocks.
 *
 * This is deliberately not a full grammar — it's a line-oriented scanner
 * with ordered regex rules per language, enough to make Python, shell,
 * TOML, JSON, and HTTP samples pleasant to read. Unknown languages fall
 * through to plain text. Colors map onto the app's chart palette so code
 * stays legible in both themes.
 */

export type TokenType =
  | "plain"
  | "comment"
  | "string"
  | "keyword"
  | "number"
  | "function"
  | "property"
  | "builtin"
  | "operator"
  | "prompt"
  | "decorator";

export interface Token {
  type: TokenType;
  text: string;
}

interface Rule {
  /** Pattern tried at the current scan position (compiled sticky). */
  pattern: RegExp;
  type: TokenType;
}

function rules(defs: Array<[string, TokenType]>): Rule[] {
  return defs.map(([src, type]) => ({
    pattern: new RegExp(src, "y"),
    type,
  }));
}

const PY_RULES = rules([
  ["#.*", "comment"],
  ['"""[\\s\\S]*?"""', "string"],
  ["'''[\\s\\S]*?'''", "string"],
  ['f?"(?:[^"\\\\\\n]|\\\\.)*"', "string"],
  ["f?'(?:[^'\\\\\\n]|\\\\.)*'", "string"],
  ["@[\\w.]+", "decorator"],
  [
    "\\b(?:import|from|as|def|class|return|if|elif|else|for|while|with|try|except|finally|raise|assert|lambda|yield|pass|break|continue|in|is|not|and|or|del|global|nonlocal|async|await|match|case)\\b",
    "keyword",
  ],
  ["\\b(?:True|False|None|self|cls)\\b", "builtin"],
  [
    "\\b(?:print|len|range|enumerate|zip|list|dict|set|tuple|str|int|float|bool|type|isinstance|repr|min|max|sum|abs|round|sorted|open)\\b(?=\\()",
    "builtin",
  ],
  ["\\b[A-Za-z_][\\w]*(?=\\()", "function"],
  ["\\b\\d[\\d_]*(?:\\.[\\d_]+)?(?:[eE][+-]?\\d+)?\\b", "number"],
  ["[=+\\-*/%<>!&|^~]+", "operator"],
]);

const SHELL_RULES = rules([
  ["#.*", "comment"],
  ["^\\$\\s", "prompt"],
  ['"(?:[^"\\\\\\n]|\\\\.)*"', "string"],
  ["'[^'\\n]*'", "string"],
  ["\\$\\{?[\\w]+\\}?", "property"],
  [
    "^(?:make|cascade|pip|python|python3|uv|git|curl|cd|ls|cat|mkdir|npm|pnpm|node|source|export)\\b",
    "function",
  ],
  ["(?<=\\s)--?[\\w-]+", "keyword"],
  ["\\b\\d[\\d_]*(?:\\.[\\d_]+)?\\b", "number"],
]);

const TOML_RULES = rules([
  ["#.*", "comment"],
  ["^\\s*\\[[^\\]\\n]*\\]", "keyword"],
  ['"(?:[^"\\\\\\n]|\\\\.)*"', "string"],
  ["'[^'\\n]*'", "string"],
  ["^\\s*[\\w.-]+(?=\\s*=)", "property"],
  ["\\b(?:true|false)\\b", "builtin"],
  [
    "[+-]?\\b\\d[\\d_]*(?:\\.[\\d_]+)?(?:[eE][+-]?\\d+)?\\b",
    "number",
  ],
  ["=", "operator"],
]);

const JSON_RULES = rules([
  ['"(?:[^"\\\\]|\\\\.)*"(?=\\s*:)', "property"],
  ['"(?:[^"\\\\]|\\\\.)*"', "string"],
  ["\\b(?:true|false|null)\\b", "builtin"],
  ["-?\\b\\d+(?:\\.\\d+)?(?:[eE][+-]?\\d+)?\\b", "number"],
]);

const HTTP_RULES = rules([
  ["#.*", "comment"],
  ["^(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\\b", "keyword"],
  ["^[A-Za-z-]+(?=:)", "property"],
  ["\\b\\d{3}\\b", "number"],
  ["/[\\w/{}.~-]*", "string"],
]);

const FILTER_RULES = rules([
  ["\\b(?:AND)\\b", "keyword"],
  ["(?:>=|<=|>|<|=)", "operator"],
  ["\\b\\d[\\d_]*(?:\\.[\\d_]+)?(?:[eE][+-]?\\d+)?\\b", "number"],
  ["[\\w.]+", "property"],
]);

const LANGS: Record<string, Rule[]> = {
  python: PY_RULES,
  py: PY_RULES,
  bash: SHELL_RULES,
  sh: SHELL_RULES,
  shell: SHELL_RULES,
  toml: TOML_RULES,
  json: JSON_RULES,
  http: HTTP_RULES,
  filter: FILTER_RULES,
};

/** Tokenize one language's source. Falls back to a single plain token. */
export function tokenize(code: string, lang: string): Token[] {
  const ruleset = LANGS[lang.toLowerCase()];
  if (!ruleset) return [{ type: "plain", text: code }];

  const tokens: Token[] = [];
  let pos = 0;
  let plainStart = 0;

  const flushPlain = (end: number) => {
    if (end > plainStart) {
      tokens.push({ type: "plain", text: code.slice(plainStart, end) });
    }
  };

  // Multiline-aware: ^ anchors need per-line scanning for prompt/section
  // rules, so we feed the scanner line fragments but keep multiline
  // strings working by retrying docstring rules against the full tail.
  while (pos < code.length) {
    let matched = false;
    for (const rule of ruleset) {
      rule.pattern.lastIndex = pos;
      // Emulate ^ by only allowing anchored rules at line starts.
      if (rule.pattern.source.startsWith("^")) {
        if (pos !== 0 && code[pos - 1] !== "\n") continue;
        // Re-compile-free trick: sticky regex with ^ works with the 'm'
        // semantics only if we test the slice.
        const tail = code.slice(pos);
        const m = new RegExp(rule.pattern.source, "").exec(tail);
        if (m && m.index === 0 && m[0].length > 0) {
          flushPlain(pos);
          tokens.push({ type: rule.type, text: m[0] });
          pos += m[0].length;
          plainStart = pos;
          matched = true;
          break;
        }
        continue;
      }
      const m = rule.pattern.exec(code);
      if (m && m[0].length > 0) {
        flushPlain(pos);
        tokens.push({ type: rule.type, text: m[0] });
        pos = rule.pattern.lastIndex;
        plainStart = pos;
        matched = true;
        break;
      }
    }
    if (!matched) pos += 1;
  }
  flushPlain(code.length);
  return tokens;
}

/** Tailwind classes per token type — theme-aware via design tokens. */
export const TOKEN_CLASS: Record<TokenType, string> = {
  plain: "",
  comment: "text-text-muted italic",
  string: "text-semantic-success-text",
  keyword: "text-chart-4 font-medium",
  number: "text-chart-2",
  function: "text-chart-6",
  property: "text-chart-1 dark:text-chart-11",
  builtin: "text-chart-5",
  operator: "text-text-subtle",
  prompt: "text-text-muted select-none",
  decorator: "text-chart-7",
};
