"use client";

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three-stdlib";

export interface LoadedGltf {
  /** The single scene/group ready to add to a parent. */
  scene: THREE.Group;
  /** Source URL. */
  url: string;
  /** Server flagged the response as a stub (empty mesh). */
  isStub: boolean;
}

export interface UseGltfStreamResult {
  current: LoadedGltf | null;
  previous: LoadedGltf | null;
  loading: boolean;
  error: Error | null;
  /** Crossfade progress 0..1; reaches 1 when previous fades out. */
  crossfade: number;
}

/**
 * Stream a glTF URL with a 200 ms opacity crossfade between the previous
 * mesh and the new mesh. On every URL change the hook:
 *
 *  1. Keeps the previous `LoadedGltf` reachable via `previous`.
 *  2. Fetches the new URL through GLTFLoader.
 *  3. When the new scene arrives, exposes it as `current` and animates
 *     `crossfade` 0 → 1 over `CROSSFADE_MS`.
 *  4. On unmount (or url=null) disposes both scenes.
 *
 * The caller renders both `current` and `previous` simultaneously while
 * `crossfade` < 1 (typical viewer pattern: lerp opacity with the value).
 */
const CROSSFADE_MS = 200;

export function useGltfStream(url: string | null): UseGltfStreamResult {
  const [current, setCurrent] = useState<LoadedGltf | null>(null);
  const [previous, setPrevious] = useState<LoadedGltf | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [crossfade, setCrossfade] = useState(1);
  const rafRef = useRef<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!url) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    abortRef.current?.abort();
    abortRef.current = new AbortController();
    const { signal } = abortRef.current;

    const loader = new GLTFLoader();
    let cancelled = false;

    const fetchAndDecode = async () => {
      try {
        const resp = await fetch(url, { signal });
        if (!resp.ok) {
          throw new Error(`gltf ${url}: ${resp.status}`);
        }
        const isStub = resp.headers.get("X-Cascade-Stub") === "true";
        const buf = await resp.arrayBuffer();
        if (cancelled) return;
        loader.parse(
          buf,
          "",
          (gltf) => {
            if (cancelled) return;
            const scene = gltf.scene as THREE.Group;
            // Capture the outgoing mesh BEFORE setCurrent. There are two
            // distinct cases:
            //   (a) `current` is non-null → we are SWITCHING meshes; run the
            //       200 ms opacity crossfade from 0 → 1 on the new mesh
            //       while the old fades 1 → 0.4 → unmount.
            //   (b) `current` is null → first pick, no outgoing mesh to fade.
            //       Show the new mesh at full opacity IMMEDIATELY so there
            //       is no blank gap between the procedural placeholder
            //       disappearing (when loading → false) and the canonical
            //       mesh becoming visible. Without this, opacity sits at 0
            //       for a frame or two and the user sees a flicker.
            const hasOutgoing = current !== null;
            setPrevious(current);
            setCurrent({ scene, url, isStub });
            setLoading(false);

            if (!hasOutgoing) {
              // First-pick: skip the fade, snap to fully opaque so the
              // mesh is visible the instant the procedural goes away.
              setCrossfade(1);
              return;
            }

            // Switching meshes: animate opacity 0 → 1 over CROSSFADE_MS.
            const start = performance.now();
            setCrossfade(0);
            const tick = (now: number) => {
              if (cancelled) return;
              const t = Math.min(1, (now - start) / CROSSFADE_MS);
              setCrossfade(t);
              if (t < 1) rafRef.current = requestAnimationFrame(tick);
            };
            rafRef.current = requestAnimationFrame(tick);
          },
          (err) => {
            if (cancelled) return;
            setError(err instanceof Error ? err : new Error(String(err)));
            setLoading(false);
          },
        );
      } catch (err) {
        if (cancelled || (err instanceof DOMException && err.name === "AbortError")) {
          return;
        }
        setError(err instanceof Error ? err : new Error(String(err)));
        setLoading(false);
      }
    };

    fetchAndDecode();

    return () => {
      cancelled = true;
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      abortRef.current?.abort();
    };
    // Intentionally exclude `current` — including it would cycle.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url]);

  // Drop the "previous" scene once the crossfade completes so we stop
  // rendering and disposing it.
  useEffect(() => {
    if (crossfade >= 1 && previous) {
      const prev = previous;
      setPrevious(null);
      // Defer disposal to next tick so the renderer has finished the frame.
      setTimeout(() => {
        prev.scene.traverse((obj) => {
          const mesh = obj as THREE.Mesh;
          if (mesh.geometry) mesh.geometry.dispose();
          const mat = mesh.material as THREE.Material | THREE.Material[] | undefined;
          if (Array.isArray(mat)) mat.forEach((m) => m.dispose());
          else mat?.dispose();
        });
      }, 16);
    }
  }, [crossfade, previous]);

  return { current, previous, loading, error, crossfade };
}
