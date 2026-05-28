/**
 * Procedural impeller used as a placeholder while the canonical mesh is
 * streaming from the API. The shape is deliberately calm and engineering-
 * grade: a hub disk + tapered shroud + a fan of straight radial blades.
 * It scales with the active rotor outlet radius so the silhouette stays
 * roughly the same size as the real candidate.
 *
 * Returns a `THREE.Group` ready to add to a scene. The caller owns the
 * disposal lifecycle — see `disposeGroup` below.
 */

import * as THREE from "three";

export interface ProceduralImpellerOpts {
  /** Outlet tip radius in metres. */
  rTip?: number;
  /** Number of main blades. */
  bladeCount?: number;
  /** Hub-to-tip ratio at the rotor outlet (0..1). */
  hubFraction?: number;
  /** Outlet thickness (axial), in metres. */
  thickness?: number;
}

export function createProceduralImpeller(
  opts: ProceduralImpellerOpts = {},
): THREE.Group {
  const rTip = opts.rTip ?? 0.030;
  const bladeCount = Math.max(6, Math.min(opts.bladeCount ?? 12, 28));
  const hubFraction = opts.hubFraction ?? 0.35;
  const thickness = opts.thickness ?? 0.012;

  const group = new THREE.Group();
  group.name = "procedural-impeller";

  // Back-disk
  const diskGeom = new THREE.CylinderGeometry(rTip, rTip, thickness * 0.4, 64);
  const diskMat = new THREE.MeshStandardMaterial({
    color: 0x9aa1ab,
    metalness: 0.6,
    roughness: 0.4,
  });
  const disk = new THREE.Mesh(diskGeom, diskMat);
  disk.position.y = -thickness * 0.2;
  group.add(disk);

  // Hub stub (cone)
  const hubGeom = new THREE.ConeGeometry(rTip * hubFraction, thickness * 1.6, 48);
  const hubMat = new THREE.MeshStandardMaterial({
    color: 0xaeb4be,
    metalness: 0.5,
    roughness: 0.45,
  });
  const hub = new THREE.Mesh(hubGeom, hubMat);
  hub.position.y = thickness * 0.5;
  group.add(hub);

  // Blades — flat triangular plates extruded along the axis. They wrap a
  // gentle backsweep so the silhouette suggests a centrifugal wheel.
  const bladeMat = new THREE.MeshStandardMaterial({
    color: 0xc4c9d1,
    metalness: 0.7,
    roughness: 0.35,
    side: THREE.DoubleSide,
  });

  for (let i = 0; i < bladeCount; i++) {
    const theta = (i / bladeCount) * Math.PI * 2;
    const shape = new THREE.Shape();
    shape.moveTo(rTip * hubFraction, 0);
    shape.lineTo(rTip, thickness * 0.0);
    shape.lineTo(rTip * 0.85, thickness * 1.4);
    shape.lineTo(rTip * hubFraction * 0.9, thickness * 1.3);
    shape.closePath();

    const geom = new THREE.ExtrudeGeometry(shape, {
      depth: thickness * 0.05,
      bevelEnabled: false,
      steps: 1,
    });
    geom.rotateX(Math.PI / 2);
    const blade = new THREE.Mesh(geom, bladeMat);
    blade.rotation.y = theta;
    group.add(blade);
  }

  // Wireframe overlay — a soft ground ring at the outlet, so the
  // placeholder reads as "an impeller about to be rendered" instead of
  // "broken geometry".
  const ringGeom = new THREE.TorusGeometry(rTip * 1.01, rTip * 0.005, 4, 96);
  ringGeom.rotateX(Math.PI / 2);
  const ringMat = new THREE.LineBasicMaterial({
    color: 0x7a808a,
    transparent: true,
    opacity: 0.7,
  });
  const ring = new THREE.LineSegments(
    new THREE.EdgesGeometry(ringGeom),
    ringMat,
  );
  group.add(ring);

  return group;
}

/**
 * Free every geometry and material under a group. Three.js does not
 * track GPU resources via JS GC, so manual disposal is the only way to
 * avoid leaks on rapid candidate switches.
 */
export function disposeGroup(group: THREE.Object3D): void {
  group.traverse((obj) => {
    const mesh = obj as THREE.Mesh;
    if (mesh.geometry) mesh.geometry.dispose();
    const mat = mesh.material as
      | THREE.Material
      | THREE.Material[]
      | undefined;
    if (Array.isArray(mat)) {
      mat.forEach((m) => m.dispose());
    } else {
      mat?.dispose();
    }
  });
}
