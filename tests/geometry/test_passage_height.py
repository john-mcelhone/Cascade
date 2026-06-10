"""Regression tests: passage height at the radial end of the channel.

Historically the mesh generator dropped ``blade_height_outlet`` (centrifugal)
and ``blade_height_inlet`` (radial turbine): the shroud curve terminated a
bare tip-clearance away from the hub, collapsing the radial-end passage to
~0.4 mm and rendering every impeller as a bladeless dome (KG-G-10, closed).

These tests pin the corrected convention: at a radial station the passage
height and the clearance offset are both axial, so the hub→shroud gap at the
radial end must equal ``blade_height + tip_clearance`` (blades loft all the
way to the casing curve; no discrete tip gap is modeled — see KG-G-05).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from cascade.geometry import MeshLOD, impeller_mesh
from cascade.geometry.impeller import (
    LOD_RESOLUTION,
    _build_meridional_curves as cc_meridional_curves,
)
from cascade.geometry.radial_turbine import (
    _build_meridional_curves as rit_meridional_curves,
)
from cascade.meanline.centrifugal_compressor import CentrifugalCompressorGeometry
from cascade.meanline.radial_turbine import RadialTurbineGeometry


def _cc_geometry(blade_height_outlet: float = 0.012) -> CentrifugalCompressorGeometry:
    return CentrifugalCompressorGeometry(
        inducer_hub_radius=0.018,
        inducer_tip_radius=0.050,
        impeller_outlet_radius=0.100,
        blade_height_outlet=blade_height_outlet,
        blade_count=20,
        beta_2_metal_rad=math.pi / 3,
        tip_clearance=0.0005,
    )


def _rit_geometry() -> RadialTurbineGeometry:
    return RadialTurbineGeometry(
        rotor_inlet_radius=0.090,
        rotor_outlet_radius_hub=0.012,
        rotor_outlet_radius_tip=0.050,
        blade_height_inlet=0.012,
        blade_height_outlet=0.038,
        blade_count=14,
        inlet_metal_angle_rad=0.0,
        exducer_angle_rad=math.radians(60.0),
        tip_clearance=0.0005,
    )


def _gap(z_hub, r_hub, z_shroud, r_shroud, idx: int) -> float:
    return math.hypot(z_hub[idx] - z_shroud[idx], r_hub[idx] - r_shroud[idx])


class TestCurveLevelPassageHeight:
    @pytest.mark.parametrize("b2", [0.005, 0.012, 0.026])
    @pytest.mark.parametrize(
        "n_meridional", sorted({n for n, _ in LOD_RESOLUTION.values()})
    )
    def test_cc_te_passage_equals_b2_plus_clearance(
        self, b2: float, n_meridional: int
    ) -> None:
        geom = _cc_geometry(blade_height_outlet=b2)
        z_hub, r_hub, z_sh, r_sh = cc_meridional_curves(geom, n_meridional)
        assert _gap(z_hub, r_hub, z_sh, r_sh, -1) == pytest.approx(
            b2 + geom.tip_clearance, rel=1e-6
        )
        # The shroud must end at full outlet radius (no radial clearance
        # subtraction at a radial exit — the clearance there is axial).
        assert r_sh[-1] == pytest.approx(geom.impeller_outlet_radius, rel=1e-9)

    def test_cc_shroud_z_monotonic(self) -> None:
        # The interior control points scale with the shortened axial span;
        # the sampled shroud must not fold back on itself.
        geom = _cc_geometry(blade_height_outlet=0.026)
        _, _, z_sh, _ = cc_meridional_curves(geom, 36)
        assert bool(np.all(np.diff(z_sh) > 0.0))

    def test_rit_le_passage_equals_b1_plus_clearance(self) -> None:
        geom = _rit_geometry()
        z_hub, r_hub, z_sh, r_sh = rit_meridional_curves(geom, 20)
        assert _gap(z_hub, r_hub, z_sh, r_sh, 0) == pytest.approx(
            geom.blade_height_inlet + geom.tip_clearance, rel=1e-6
        )

    def test_rit_exducer_passage_preserved(self) -> None:
        # The axial end was already correct (passage height enters via the
        # hub/shroud radii); pin it against regression.
        geom = _rit_geometry()
        z_hub, r_hub, z_sh, r_sh = rit_meridional_curves(geom, 20)
        expected = (
            geom.rotor_outlet_radius_tip
            - geom.rotor_outlet_radius_hub
            - geom.tip_clearance
        )
        assert _gap(z_hub, r_hub, z_sh, r_sh, -1) == pytest.approx(
            expected, rel=1e-6
        )

    def test_degenerate_blade_height_raises(self) -> None:
        # b2 + clearance leaves under 5% of the axial length (0.06 m for
        # this r2) — the contour builder must refuse rather than loft a
        # collapsed passage.
        geom = _cc_geometry(blade_height_outlet=0.058)
        with pytest.raises(ValueError, match="degenerate shroud"):
            cc_meridional_curves(geom, 20)


class TestMeshLevelPassageHeight:
    @pytest.mark.parametrize("lod", [MeshLOD.PREVIEW, MeshLOD.STANDARD, MeshLOD.HIGH])
    def test_cc_rim_z_span_matches_b2(self, lod: MeshLOD) -> None:
        geom = _cc_geometry()
        m = impeller_mesh(
            geom, lod=lod, with_splitter=False, with_back_face=True,
            with_shroud=False,
        )
        v = m.vertices
        rim = v[np.hypot(v[:, 0], v[:, 1]) > 0.995 * geom.impeller_outlet_radius]
        z_span = rim[:, 2].max() - rim[:, 2].min()
        assert z_span == pytest.approx(
            geom.blade_height_outlet + geom.tip_clearance, rel=0.05
        )

    @pytest.mark.parametrize("lod", [MeshLOD.PREVIEW, MeshLOD.STANDARD, MeshLOD.HIGH])
    def test_rit_rim_z_span_matches_b1(self, lod: MeshLOD) -> None:
        geom = _rit_geometry()
        m = impeller_mesh(
            geom, lod=lod, with_splitter=False, with_back_face=True,
            with_shroud=False,
        )
        v = m.vertices
        rim = v[np.hypot(v[:, 0], v[:, 1]) > 0.995 * geom.rotor_inlet_radius]
        z_span = rim[:, 2].max() - rim[:, 2].min()
        assert z_span == pytest.approx(
            geom.blade_height_inlet + geom.tip_clearance, rel=0.05
        )

    @pytest.mark.parametrize("lod", [MeshLOD.PREVIEW, MeshLOD.STANDARD, MeshLOD.HIGH])
    def test_cc_watertight_preserved_all_lods(self, lod: MeshLOD) -> None:
        geom = _cc_geometry()
        m = impeller_mesh(
            geom, lod=lod, with_splitter=False, with_back_face=True,
            with_shroud=False,
        )
        assert m.is_watertight
        assert m.is_winding_consistent
