import type { Config } from "tailwindcss";

/**
 * Cascade Tailwind theme.
 * Every value here maps to a CSS variable defined in globals.css.
 * Both light and dark modes share the same Tailwind class names; the
 * variable values swap when [data-theme="dark"] is set on <html>.
 *
 * Source of truth for raw colors / sizes: /tokens.json.
 */
const config: Config = {
  darkMode: ["class", '[data-theme="dark"]'],
  content: [
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // App-level backgrounds
        background: "rgb(var(--background) / <alpha-value>)",
        foreground: "rgb(var(--text-default) / <alpha-value>)",

        // Brand teal
        brand: {
          DEFAULT: "rgb(var(--brand-default) / <alpha-value>)",
          hover: "rgb(var(--brand-hover) / <alpha-value>)",
          pressed: "rgb(var(--brand-pressed) / <alpha-value>)",
          surface: "rgb(var(--brand-surface) / <alpha-value>)",
          text: "rgb(var(--brand-text) / <alpha-value>)",
          accent: "rgb(var(--brand-accent) / <alpha-value>)",
        },

        // Surfaces
        surface: {
          DEFAULT: "rgb(var(--surface-default) / <alpha-value>)",
          subtle: "rgb(var(--surface-subtle) / <alpha-value>)",
          raised: "rgb(var(--surface-raised) / <alpha-value>)",
          input: "rgb(var(--surface-input) / <alpha-value>)",
          computed: "rgb(var(--surface-computed) / <alpha-value>)",
        },

        // Text tokens
        text: {
          DEFAULT: "rgb(var(--text-default) / <alpha-value>)",
          muted: "rgb(var(--text-muted) / <alpha-value>)",
          subtle: "rgb(var(--text-subtle) / <alpha-value>)",
          disabled: "rgb(var(--text-disabled) / <alpha-value>)",
          inverse: "rgb(var(--text-inverse) / <alpha-value>)",
          bound: "rgb(var(--text-bound) / <alpha-value>)",
        },

        // Borders
        border: {
          DEFAULT: "rgb(var(--border-default) / <alpha-value>)",
          subtle: "rgb(var(--border-subtle) / <alpha-value>)",
          strong: "rgb(var(--border-strong) / <alpha-value>)",
          focus: "rgb(var(--border-focus) / <alpha-value>)",
        },

        // Semantic
        semantic: {
          success: {
            DEFAULT: "rgb(var(--success-default) / <alpha-value>)",
            surface: "rgb(var(--success-surface) / <alpha-value>)",
            border: "rgb(var(--success-border) / <alpha-value>)",
            text: "rgb(var(--success-text) / <alpha-value>)",
          },
          warning: {
            DEFAULT: "rgb(var(--warning-default) / <alpha-value>)",
            surface: "rgb(var(--warning-surface) / <alpha-value>)",
            border: "rgb(var(--warning-border) / <alpha-value>)",
            text: "rgb(var(--warning-text) / <alpha-value>)",
          },
          danger: {
            DEFAULT: "rgb(var(--danger-default) / <alpha-value>)",
            surface: "rgb(var(--danger-surface) / <alpha-value>)",
            border: "rgb(var(--danger-border) / <alpha-value>)",
            text: "rgb(var(--danger-text) / <alpha-value>)",
          },
          info: {
            DEFAULT: "rgb(var(--info-default) / <alpha-value>)",
            surface: "rgb(var(--info-surface) / <alpha-value>)",
            border: "rgb(var(--info-border) / <alpha-value>)",
            text: "rgb(var(--info-text) / <alpha-value>)",
          },
        },

        // Categorical chart palette (12)
        chart: {
          1: "rgb(var(--chart-1) / <alpha-value>)",
          2: "rgb(var(--chart-2) / <alpha-value>)",
          3: "rgb(var(--chart-3) / <alpha-value>)",
          4: "rgb(var(--chart-4) / <alpha-value>)",
          5: "rgb(var(--chart-5) / <alpha-value>)",
          6: "rgb(var(--chart-6) / <alpha-value>)",
          7: "rgb(var(--chart-7) / <alpha-value>)",
          8: "rgb(var(--chart-8) / <alpha-value>)",
          9: "rgb(var(--chart-9) / <alpha-value>)",
          10: "rgb(var(--chart-10) / <alpha-value>)",
          11: "rgb(var(--chart-11) / <alpha-value>)",
          12: "rgb(var(--chart-12) / <alpha-value>)",
        },
      },

      fontFamily: {
        sans: [
          "var(--font-sans)",
          "Inter",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        mono: [
          "var(--font-mono)",
          "JetBrains Mono",
          "ui-monospace",
          "SF Mono",
          "Menlo",
          "Consolas",
          "monospace",
        ],
      },

      fontSize: {
        // Pairs: [size, lineHeight] mirroring tokens.json type.size + type.lineHeight
        xs: ["11px", "16px"],
        sm: ["12px", "18px"],
        base: ["14px", "20px"],
        md: ["16px", "24px"],
        lg: ["20px", "28px"],
        xl: ["28px", "36px"],
        "2xl": ["40px", "48px"],
        // Display sizes for marketing / onboarding / hero surfaces. Tight
        // tracking + leading are applied at the call site.
        "3xl": ["52px", "58px"],
        "4xl": ["68px", "72px"],
        "5xl": ["88px", "92px"],
      },

      spacing: {
        // 8-step scale from tokens.json space.*
        // Tailwind defaults stay available; these are our semantic names.
        // NOTE: this scale is for gaps/padding/margins only. Keys 5-8
        // diverge from Tailwind's defaults (24/32/48/64 vs 20/24/28/32),
        // and height/width derive from spacing — so the matching keys are
        // pinned back to Tailwind's defaults under `width`/`height` below.
        // Without that, every h-7 control renders 48px instead of the
        // design system's documented 28px dense height.
        "1": "4px",
        "2": "8px",
        "3": "12px",
        "4": "16px",
        "5": "24px",
        "6": "32px",
        "7": "48px",
        "8": "64px",
      },

      borderRadius: {
        none: "0",
        sm: "4px",
        DEFAULT: "4px",
        md: "6px",
        lg: "10px",
        full: "9999px",
      },

      boxShadow: {
        z1: "var(--shadow-z1)",
        z2: "var(--shadow-z2)",
        z3: "var(--shadow-z3)",
        z4: "var(--shadow-z4)",
        glow: "var(--shadow-glow)",
      },

      transitionDuration: {
        fast: "100ms",
        base: "150ms",
        medium: "200ms",
        snap: "50ms",
        exit: "120ms",
      },

      transitionTimingFunction: {
        out: "cubic-bezier(0.4, 0, 0.2, 1)",
        in: "cubic-bezier(0.4, 0, 1, 1)",
      },

      // Layout shell sizes — plus Tailwind's default sizing steps for the
      // keys the spacing token scale above would otherwise hijack. Control
      // dimensions (h-5…h-8, w-5…w-8) must follow Tailwind's 4px grid:
      // h-6 = 24px dense rows, h-7 = 28px buttons/inputs, h-8 = 32px nav.
      width: {
        rail: "240px",
        "rail-collapsed": "64px",
        "5": "1.25rem",
        "6": "1.5rem",
        "7": "1.75rem",
        "8": "2rem",
      },
      height: {
        topbar: "44px",
        bottombar: "32px",
        "5": "1.25rem",
        "6": "1.5rem",
        "7": "1.75rem",
        "8": "2rem",
      },

      // 8 px dotted canvas background (Cycle Canvas)
      backgroundImage: {
        "dotted-grid":
          "radial-gradient(circle at 1px 1px, rgb(var(--border-subtle) / 0.6) 1px, transparent 0)",
      },
      backgroundSize: {
        grid: "8px 8px",
      },

      keyframes: {
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "fade-in-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "scale-in": {
          "0%": { opacity: "0", transform: "scale(0.97)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        "pulse-ring": {
          "0%": { boxShadow: "0 0 0 0 rgb(var(--brand-default) / 0.5)" },
          "70%": { boxShadow: "0 0 0 8px rgb(var(--brand-default) / 0)" },
          "100%": { boxShadow: "0 0 0 0 rgb(var(--brand-default) / 0)" },
        },
      },
      animation: {
        "fade-in": "fade-in 100ms cubic-bezier(0.4, 0, 0.2, 1)",
        "fade-in-up": "fade-in-up 480ms cubic-bezier(0.16, 1, 0.3, 1) both",
        "scale-in": "scale-in 200ms cubic-bezier(0.16, 1, 0.3, 1) both",
        "pulse-ring": "pulse-ring 2s cubic-bezier(0.4, 0, 0.2, 1) infinite",
      },
    },
  },
  plugins: [],
};

export default config;
