"use client";

import * as React from "react";

interface Props {
  children: React.ReactNode;
  /** Optional fallback rendered when the boundary trips. */
  fallback?: React.ReactNode;
}

interface State {
  error?: Error;
}

/**
 * Catches the harmless `Cannot use 'in' operator to search for X in null`
 * errors that `@react-three/drei`'s `OrbitControls` throws during unmount
 * cleanup (drei 10.7.7 + R3F 9 + three 0.171). The error fires when the
 * component's effect cleanup races with the OrbitControls instance being
 * disposed — typically when navigating away from a page that has a 3D
 * viewer, or during Next.js HMR.
 *
 * The error is non-fatal — the 3D scene was about to be torn down anyway —
 * but Next.js's dev overlay surfaces it as "Recoverable Error", which is
 * alarming. This boundary catches it, logs a quiet console note, and
 * renders nothing (or the supplied fallback). The next mount creates a
 * fresh Canvas + Controls and everything works.
 *
 * In production builds the dev overlay is absent; this boundary is still
 * a useful belt-and-braces guard against any unforeseen 3D crash bringing
 * down the surrounding page chrome.
 */
export class CanvasErrorBoundary extends React.Component<Props, State> {
  state: State = {};

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error): void {
    const msg = error?.message ?? "";
    // Known-benign cleanup races. Log quietly so we still see the
    // information in the console, but don't escalate.
    const isDreiCleanupRace =
      /Cannot use 'in' operator to search for/.test(msg) &&
      /(minPolarAngle|getTarget|maxPolarAngle|enableDamping|target)/.test(msg);
    if (isDreiCleanupRace) {
      // eslint-disable-next-line no-console
      console.debug(
        "[CanvasErrorBoundary] swallowed drei OrbitControls cleanup error:",
        msg,
      );
      // Reset state so the next mount can render normally.
      // Defer to a microtask so React doesn't re-throw immediately.
      Promise.resolve().then(() => this.setState({ error: undefined }));
      return;
    }
    // Anything else — let the user know via console; the boundary still
    // shows the fallback to avoid breaking surrounding chrome.
    // eslint-disable-next-line no-console
    console.error("[CanvasErrorBoundary] uncaught 3D error:", error);
  }

  render(): React.ReactNode {
    if (this.state.error) {
      return this.props.fallback ?? null;
    }
    return this.props.children;
  }
}
