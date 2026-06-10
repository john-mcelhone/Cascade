"""Industry-standard blade-camber and flow-path invariants.

These pin the manufacturability-driven geometry properties that the
pre-fix generator violated (over-wrapped corkscrew blades, rippled
contours — see KG-G-12):

- Meridional contours are monotonic with exact end tangency (axial at a
  CC inducer, radial at the exit) — no interpolation ripples.
- The LE metal angle twists across the span per the velocity-triangle
  relation ``tan β₁ ∝ r`` (shallow at the hub, steep at the shroud).
- Wrap angles land in the range real wheels are milled with (rough
  bounds; the pre-fix hub wrap was ~185° and the implied shroud blade
  was nearly tangential).
- The realized TE metal angle equals the design β₂ on every streamline.
- Blades stay radially inside the design envelope (max radius = r₂).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from cascade.geometry import MeshLOD, impeller_mesh
from cascade.geometry._curves import passage_camber_grid
from cascade.geometry.impeller import (
    _build_meridional_curves as cc_meridional_curves,
    blade_metal_angles as cc_blade_metal_angles,
)
from cascade.geometry.radial_turbine import (
    blade_metal_angles as rit_blade_metal_angles,
)
from cascade.meanline.centrifugal_compressor import CentrifugalCompressorGeometry
from cascade.meanline.radial_turbine import RadialTurbineGeometry


def _cc_geometry() -> CentrifugalCompressorGeometry:
    # Eckardt Rotor A proportions (the canonical CC-1 validation wheel).
    return CentrifugalCompressorGeometry(
        inducer_hub_radius=0.045,
        inducer_tip_radius=0.140,
        impeller_outlet_radius=0.200,
        blade_height_outlet=0.026,
        blade_count=16,
        beta_2_metal_rad=math.pi / 6,  # 30° backsweep
        tip_clearance=3e-4,
    )


def _rit_geometry() -> RadialTurbineGeometry:
    return RadialTurbineGeometry(
        rotor_inlet_radius=0.076,
        rotor_outlet_radius_hub=0.019,
        rotor_outlet_radius_tip=0.0406,
        blade_height_inlet=0.012,
        blade_height_outlet=0.0216,
        blade_count=12,
        inlet_metal_angle_rad=0.0,
        exducer_angle_rad=math.radians(60.0),
        tip_clearance=0.00025,
    )


def _cc_camber(geom, n_m=72, n_span=10):
    z_hub, r_hub, z_sh, r_sh = cc_meridional_curves(geom, n_m)
    b_hub, b_tip, b_te = cc_blade_metal_angles(geom)
    return passage_camber_grid(
        z_hub, r_hub, z_sh, r_sh,
        beta_le_hub_rad=b_hub,
        beta_le_shroud_rad=b_tip,
        beta_te_hub_rad=b_te,
        beta_te_shroud_rad=b_te,
        n_span=n_span,
    )


class TestMeridionalContours:
    def test_monotonic_no_ripples(self) -> None:
        geom = _cc_geometry()
        z_hub, r_hub, z_sh, r_sh = cc_meridional_curves(geom, 72)
        assert bool(np.all(np.diff(z_hub) >= 0))
        assert bool(np.all(np.diff(r_hub) >= 0))
        assert bool(np.all(np.diff(z_sh) >= 0))
        assert bool(np.all(np.diff(r_sh) >= 0))

    def test_end_tangency(self) -> None:
        """Axial tangent at the inducer inlet, radial at the exit — the
        condition that lets the wheel blend smoothly into an axial inlet
        duct and a radial diffuser."""
        geom = _cc_geometry()
        z_hub, r_hub, _, _ = cc_meridional_curves(geom, 144)
        # Inlet: dr/dz → 0 (contour moving axially).
        slope_in = (r_hub[1] - r_hub[0]) / max(z_hub[1] - z_hub[0], 1e-12)
        assert abs(slope_in) < 0.1
        # Exit: dz/dr → 0 (contour moving radially).
        slope_out = (z_hub[-1] - z_hub[-2]) / max(r_hub[-1] - r_hub[-2], 1e-12)
        assert abs(slope_out) < 0.1


class TestBladeMetalAngles:
    def test_cc_le_twist_follows_radius_ratio(self) -> None:
        geom = _cc_geometry()
        b_hub, b_tip, _ = cc_blade_metal_angles(geom)
        assert b_hub < b_tip
        ratio = geom.inducer_hub_radius / geom.inducer_tip_radius
        assert math.tan(b_hub) == pytest.approx(
            ratio * math.tan(b_tip), rel=1e-9
        )

    def test_rit_exducer_twist_follows_radius(self) -> None:
        geom = _rit_geometry()
        _, b_te_hub, b_te_tip = rit_blade_metal_angles(geom)
        assert b_te_hub < b_te_tip
        assert math.tan(b_te_hub) / math.tan(b_te_tip) == pytest.approx(
            geom.rotor_outlet_radius_hub / geom.rotor_outlet_radius_tip,
            rel=1e-9,
        )


class TestCamberWrap:
    def test_wrap_in_millable_range(self) -> None:
        """Real backswept wheels carry roughly 30–110° of hub wrap and
        20–90° at the shroud. The pre-fix generator produced ~185° at
        the hub and copied it to the shroud."""
        _, _, theta = _cc_camber(_cc_geometry())
        wrap_hub = math.degrees(theta[-1, 0])
        wrap_shroud = math.degrees(theta[-1, -1])
        assert 30.0 < wrap_hub < 110.0
        assert 20.0 < wrap_shroud < 90.0
        # The hub streamline turns through more passage than the shroud.
        assert wrap_hub > wrap_shroud

    def test_te_metal_angle_realized_on_every_streamline(self) -> None:
        """arctan(r·dθ/dm) at the TE must equal the design β₂ on hub,
        mid-span and shroud — the camber actually delivers the exit
        metal angle the meanline was scored with."""
        geom = _cc_geometry()
        Z, R, theta = _cc_camber(geom, n_m=144)
        for j in (0, theta.shape[1] // 2, theta.shape[1] - 1):
            dm = math.hypot(
                Z[-1, j] - Z[-2, j], R[-1, j] - R[-2, j]
            )
            dtheta_dm = (theta[-1, j] - theta[-2, j]) / max(dm, 1e-12)
            beta_realized = math.atan(R[-1, j] * dtheta_dm)
            assert beta_realized == pytest.approx(
                geom.beta_2_metal_rad, abs=math.radians(3.0)
            )


class TestBladeEnvelope:
    def test_blades_stay_inside_outlet_radius(self) -> None:
        geom = _cc_geometry()
        m = impeller_mesh(geom, lod=MeshLOD.STANDARD, with_splitter=True)
        v = np.asarray(m.vertices)
        r = np.hypot(v[:, 0], v[:, 1])
        assert r.max() <= geom.impeller_outlet_radius * (1.0 + 1e-6)
