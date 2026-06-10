import type { Metadata } from "next";
import { Inter, JetBrains_Mono, Fraunces } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { AppShell } from "@/components/shell/app-shell";

const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  display: "swap",
});

// Display serif for marketing / onboarding headlines only — the dense
// workspace stays Inter. Optical sizing gives the display cut at large
// sizes; weights are set at the call site.
const fraunces = Fraunces({
  variable: "--font-display",
  subsets: ["latin"],
  style: ["normal", "italic"],
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "Cascade",
    template: "%s — Cascade",
  },
  description:
    "Cascade is the web-native turbomachinery design environment for small engineering teams.",
  applicationName: "Cascade",
  authors: [{ name: "American Turbines" }],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      // next-themes writes [data-theme] on <html> at runtime; SSR mismatch is expected.
      suppressHydrationWarning
      className={`${inter.variable} ${jetbrainsMono.variable} ${fraunces.variable} h-full`}
    >
      <body className="min-h-full font-sans bg-background text-text">
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
