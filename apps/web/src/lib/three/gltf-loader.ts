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

function disposeScene(scene: THREE.Group) {
  scene.traverse((obj) => {
    const mesh = obj as THREE.Mesh;
    if (mesh.geometry) mesh.geometry.dispose();
    const mat = mesh.material as THREE.Material | THREE.Material[] | undefined;
    if (Array.isArray(mat)) mat.forEach((m) => m.dispose());
    else mat?.dispose();
  });
}

/** Candidate identity of a geometry URL — two LODs of the same candidate
 *  share a key (the path without the query string). */
function meshKey(u: string): string {
  return u.split("?")[0];
}

export function useGltfStream(url: string | null): UseGltfStreamResult {
  const [current, setCurrent] = useState<LoadedGltf | null>(null);
  const [previous, setPrevious] = useState<LoadedGltf | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [crossfade, setCrossfade] = useState(1);
  const rafRef = useRef<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  // Always-fresh mirror of `current` — the load callbacks below close over
  // a stale `current` (the effect deliberately excludes it from deps), so
  // every read inside them goes through this ref instead.
  const currentRef = useRef<LoadedGltf | null>(null);

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
            //   (a) outgoing is non-null → we are SWITCHING meshes; run the
            //       200 ms opacity crossfade from 0 → 1 on the new mesh
            //       while the old fades 1 → 0.4 → unmount.
            //   (b) outgoing is null → first pick, no outgoing mesh to fade.
            //       Show the new mesh at full opacity IMMEDIATELY so there
            //       is no blank gap between the procedural placeholder
            //       disappearing (when loading → false) and the canonical
            //       mesh becoming visible. Without this, opacity sits at 0
            //       for a frame or two and the user sees a flicker.
            const outgoing = currentRef.current;
            // If an older `previous` is still mid-fade (its crossfade never
            // reached 1 before this load landed), it would be silently
            // dropped by the overwrite below — dispose it or its GPU
            // buffers leak on every interrupted fade.
            setPrevious((oldPrev) => {
              if (oldPrev && oldPrev !== outgoing) {
                setTimeout(() => disposeScene(oldPrev.scene), 16);
              }
              return outgoing;
            });
            currentRef.current = { scene, url, isStub };
            setCurrent(currentRef.current);
            setLoading(false);

            if (!outgoing) {
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
            failLoad(err);
          },
        );
      } catch (err) {
        if (cancelled || (err instanceof DOMException && err.name === "AbortError")) {
          return;
        }
        failLoad(err);
      }
    };

    // Failure policy, keyed on candidate identity (the URL path, ignoring
    // the lod query):
    //   - Failed LOD UPGRADE of the mesh already on screen (same key,
    //     different url): keep the good mesh, log, no error overlay —
    //     correct geometry must not be replaced by a false failure banner.
    //   - Failed load for a DIFFERENT candidate: surface the error and
    //     clear the stale mesh so the old wheel never renders under the
    //     new candidate's HUD. Any mid-fade `previous` is stale by the
    //     same argument — clear and dispose it, and reset the crossfade
    //     so the steady-state invariant (crossfade=1 when idle) holds.
    const failLoad = (err: unknown) => {
      setLoading(false);
      const cur = currentRef.current;
      if (cur && cur.url !== url && meshKey(cur.url) === meshKey(url)) {
        console.warn(`gltf: LOD upgrade failed for ${url}; keeping ${cur.url}`, err);
        return;
      }
      setError(err instanceof Error ? err : new Error(String(err)));
      if (cur && cur.url !== url) {
        currentRef.current = null;
        setCurrent(null);
        setTimeout(() => disposeScene(cur.scene), 16);
      }
      setPrevious((prev) => {
        if (prev) setTimeout(() => disposeScene(prev.scene), 16);
        return null;
      });
      setCrossfade(1);
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
      setTimeout(() => disposeScene(prev.scene), 16);
    }
  }, [crossfade, previous]);

  // Unmount: free whatever is still on the GPU (the per-url cleanup above
  // only aborts in-flight work; it must not dispose the rendered scene).
  useEffect(() => {
    return () => {
      const cur = currentRef.current;
      currentRef.current = null;
      if (cur) setTimeout(() => disposeScene(cur.scene), 16);
    };
  }, []);

  return { current, previous, loading, error, crossfade };
}
