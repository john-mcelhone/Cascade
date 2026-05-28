"""W-14: Engine-order list from meanline blade count.

Verifies that the Campbell diagram engine-order list is automatically built
from blade counts (blade-pass excitation frequencies) rather than the old
hardcoded [1.0, 2.0].

Acceptance criteria tested here:
- AC1: A project with a 15-blade turbine (blade_counts=[15]) produces a
  Campbell diagram with 15.0 in the engine_orders list.
- AC2: A project with both a 15-blade turbine and an 11-blade compressor
  (blade_counts=[15, 11]) has both 15.0 and 11.0 in engine_orders.
- AC3: Explicit engine_orders override takes full precedence; blade_counts
  is ignored when engine_orders is provided.
- AC4: The base orders 1.0 and 2.0 are always present (unbalance + ovality).
"""

from __future__ import annotations

import pytest

# Import the helper directly for focused unit tests on the engine-order logic.
from routers.rotor import _build_engine_orders

pytestmark = pytest.mark.validation


# ---------------------------------------------------------------------------
# Unit tests for _build_engine_orders helper
# ---------------------------------------------------------------------------


def test_default_engine_orders_are_1x_and_2x() -> None:
    """Without blade_counts, engine orders default to [1.0, 2.0]."""
    eos = _build_engine_orders()
    assert 1.0 in eos
    assert 2.0 in eos


def test_blade_count_15_adds_15x() -> None:
    """AC1: blade_counts=[15] adds 15.0 to the engine-order list."""
    eos = _build_engine_orders(blade_counts=[15])
    assert 15.0 in eos, f"Expected 15.0 in engine_orders; got {eos}"


def test_blade_counts_15_and_11_adds_both() -> None:
    """AC2: blade_counts=[15, 11] adds both 15.0 and 11.0 to engine-orders."""
    eos = _build_engine_orders(blade_counts=[15, 11])
    assert 15.0 in eos, f"Expected 15.0 in engine_orders; got {eos}"
    assert 11.0 in eos, f"Expected 11.0 in engine_orders; got {eos}"


def test_blade_counts_always_includes_1x_and_2x() -> None:
    """AC4: 1x and 2x are always present even with custom blade_counts."""
    eos = _build_engine_orders(blade_counts=[15])
    assert 1.0 in eos, f"Expected 1.0 (unbalance) in engine_orders; got {eos}"
    assert 2.0 in eos, f"Expected 2.0 (ovality) in engine_orders; got {eos}"


def test_engine_orders_override_takes_precedence() -> None:
    """AC3: Explicit engine_orders overrides blade_counts entirely."""
    # blade_counts=[15, 11] is provided but should be ignored.
    eos = _build_engine_orders(
        blade_counts=[15, 11],
        engine_orders_override=[1.0, 2.0, 5.0],
    )
    assert eos == [1.0, 2.0, 5.0], (
        f"Expected [1.0, 2.0, 5.0] from override; got {eos}"
    )
    assert 15.0 not in eos, "blade_counts should be ignored when engine_orders is provided."
    assert 11.0 not in eos, "blade_counts should be ignored when engine_orders is provided."


def test_engine_orders_are_sorted_ascending() -> None:
    """Engine-order list is sorted ascending with no duplicates."""
    eos = _build_engine_orders(blade_counts=[15, 11, 2, 1])
    # 1.0 and 2.0 come from base; 1 and 2 from blade_counts are deduplicated.
    assert eos == sorted(eos), f"Engine orders should be sorted ascending; got {eos}"
    assert len(eos) == len(set(eos)), f"Engine orders should have no duplicates; got {eos}"


def test_duplicate_blade_counts_deduplicated() -> None:
    """Duplicate blade count entries do not create duplicate engine-order lines."""
    eos = _build_engine_orders(blade_counts=[15, 15, 11])
    count_15 = eos.count(15.0)
    assert count_15 == 1, f"Expected 15.0 to appear once; got {count_15} times in {eos}"


def test_zero_blade_count_ignored() -> None:
    """A zero or negative blade count in blade_counts is silently ignored."""
    eos = _build_engine_orders(blade_counts=[0, -1, 15])
    assert 0.0 not in eos, "blade_count=0 should not appear in engine_orders."
    assert 15.0 in eos, "blade_count=15 should appear in engine_orders."


def test_empty_blade_counts_gives_base_orders() -> None:
    """Empty blade_counts list gives only [1.0, 2.0]."""
    eos = _build_engine_orders(blade_counts=[])
    assert eos == [1.0, 2.0], f"Expected [1.0, 2.0] for empty blade_counts; got {eos}"


# ---------------------------------------------------------------------------
# AC1/AC2 end-to-end: Campbell payload includes blade-pass intersections
# ---------------------------------------------------------------------------


def test_campbell_payload_includes_15x_engine_order() -> None:
    """AC1: _run_campbell_payload returns engine_orders containing 15.0."""
    # We test the Campbell helper function directly, passing blade_counts.
    # This avoids the full HTTP layer while still exercising the real path.
    from cascade.rotor import LinearBearing, build_rotor_model, run_campbell
    from cascade.units import LumpedDisk, Q, RotorSection, RotorShape
    from routers.rotor import _run_campbell_payload

    sec = RotorSection(
        diameter_outer=Q(0.02, "m"),
        diameter_inner=Q(0.0, "m"),
        length=Q(0.4, "m"),
        density=Q(7850.0, "kg/m^3"),
        axial_position=Q(0.0, "m"),
        material="STEEL_AISI4340",
    )
    disk = LumpedDisk(
        mass=Q(2.5, "kg"),
        inertia_polar=Q(2.5e-3, "kg*m^2"),
        inertia_diametrical=Q(1.25e-3, "kg*m^2"),
        axial_position=Q(0.2, "m"),
    )
    shape = RotorShape(sections=[sec], disks=[disk])
    K_b = 5.0e7
    brg1 = LinearBearing(
        name="b1", axial_position=Q(0.0, "m"),
        K_yy=Q(K_b, "N/m"), K_zz=Q(K_b, "N/m"),
        C_yy=Q(1.0e3, "N*s/m"), C_zz=Q(1.0e3, "N*s/m"),
    )
    brg2 = LinearBearing(
        name="b2", axial_position=Q(0.4, "m"),
        K_yy=Q(K_b, "N/m"), K_zz=Q(K_b, "N/m"),
        C_yy=Q(1.0e3, "N*s/m"), C_zz=Q(1.0e3, "N*s/m"),
    )
    model = build_rotor_model(shape, [brg1, brg2], elements_per_section=10)

    payload = _run_campbell_payload(
        model,
        speed_lo=0.0,
        speed_hi=60_000.0,
        n_modes=4,
        n_speeds=8,
        blade_counts=[15],
    )

    eos = payload["engine_orders"]
    assert 15.0 in eos, (
        f"Expected 15.0 in engine_orders after blade_counts=[15]; got {eos}"
    )
    assert 1.0 in eos, f"Expected 1.0 (base) in engine_orders; got {eos}"
    assert 2.0 in eos, f"Expected 2.0 (base) in engine_orders; got {eos}"


def test_campbell_payload_15_and_11_blade_counts() -> None:
    """AC2: blade_counts=[15, 11] puts both in engine_orders."""
    from cascade.rotor import LinearBearing, build_rotor_model
    from cascade.units import LumpedDisk, Q, RotorSection, RotorShape
    from routers.rotor import _run_campbell_payload

    sec = RotorSection(
        diameter_outer=Q(0.02, "m"),
        diameter_inner=Q(0.0, "m"),
        length=Q(0.4, "m"),
        density=Q(7850.0, "kg/m^3"),
        axial_position=Q(0.0, "m"),
        material="STEEL_AISI4340",
    )
    disk = LumpedDisk(
        mass=Q(2.5, "kg"),
        inertia_polar=Q(2.5e-3, "kg*m^2"),
        inertia_diametrical=Q(1.25e-3, "kg*m^2"),
        axial_position=Q(0.2, "m"),
    )
    shape = RotorShape(sections=[sec], disks=[disk])
    K_b = 5.0e7
    brg1 = LinearBearing(
        name="b1", axial_position=Q(0.0, "m"),
        K_yy=Q(K_b, "N/m"), K_zz=Q(K_b, "N/m"),
        C_yy=Q(1.0e3, "N*s/m"), C_zz=Q(1.0e3, "N*s/m"),
    )
    brg2 = LinearBearing(
        name="b2", axial_position=Q(0.4, "m"),
        K_yy=Q(K_b, "N/m"), K_zz=Q(K_b, "N/m"),
        C_yy=Q(1.0e3, "N*s/m"), C_zz=Q(1.0e3, "N*s/m"),
    )
    model = build_rotor_model(shape, [brg1, brg2], elements_per_section=10)

    payload = _run_campbell_payload(
        model,
        speed_lo=0.0,
        speed_hi=60_000.0,
        n_modes=4,
        n_speeds=8,
        blade_counts=[15, 11],
    )

    eos = payload["engine_orders"]
    assert 15.0 in eos, f"Expected 15.0 in engine_orders; got {eos}"
    assert 11.0 in eos, f"Expected 11.0 in engine_orders; got {eos}"


def test_campbell_payload_override_takes_precedence() -> None:
    """AC3: explicit engine_orders override trumps blade_counts."""
    from cascade.rotor import LinearBearing, build_rotor_model
    from cascade.units import LumpedDisk, Q, RotorSection, RotorShape
    from routers.rotor import _run_campbell_payload

    sec = RotorSection(
        diameter_outer=Q(0.02, "m"),
        diameter_inner=Q(0.0, "m"),
        length=Q(0.4, "m"),
        density=Q(7850.0, "kg/m^3"),
        axial_position=Q(0.0, "m"),
        material="STEEL_AISI4340",
    )
    disk = LumpedDisk(
        mass=Q(2.5, "kg"),
        inertia_polar=Q(2.5e-3, "kg*m^2"),
        inertia_diametrical=Q(1.25e-3, "kg*m^2"),
        axial_position=Q(0.2, "m"),
    )
    shape = RotorShape(sections=[sec], disks=[disk])
    K_b = 5.0e7
    brg1 = LinearBearing(
        name="b1", axial_position=Q(0.0, "m"),
        K_yy=Q(K_b, "N/m"), K_zz=Q(K_b, "N/m"),
        C_yy=Q(1.0e3, "N*s/m"), C_zz=Q(1.0e3, "N*s/m"),
    )
    brg2 = LinearBearing(
        name="b2", axial_position=Q(0.4, "m"),
        K_yy=Q(K_b, "N/m"), K_zz=Q(K_b, "N/m"),
        C_yy=Q(1.0e3, "N*s/m"), C_zz=Q(1.0e3, "N*s/m"),
    )
    model = build_rotor_model(shape, [brg1, brg2], elements_per_section=10)

    payload = _run_campbell_payload(
        model,
        speed_lo=0.0,
        speed_hi=60_000.0,
        n_modes=4,
        n_speeds=8,
        blade_counts=[15, 11],  # should be ignored because override is provided
        engine_orders_override=[1.0, 2.0, 5.0],
    )

    eos = payload["engine_orders"]
    assert eos == [1.0, 2.0, 5.0], f"Expected [1.0, 2.0, 5.0] from override; got {eos}"
    assert 15.0 not in eos, "blade_counts should be ignored when engine_orders_override is set."
