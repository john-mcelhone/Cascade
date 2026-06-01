"""Independent verification — materials database property bounds.

Oracles are textbook physical bounds for engineering alloys (ASM Handbook,
MMPDS / MIL-HDBK-5, manufacturer datasheets) and universal material-physics
constraints:
  - density of a structural alloy: 1500-20000 kg/m^3
  - Poisson's ratio strictly in (0, 0.5)
  - yield strength < ultimate tensile strength (ductile metal, same temperature)
  - Young's modulus 50-450 GPa, and monotonically softening with temperature
"""

from __future__ import annotations

import pytest

from cascade.materials.database import MATERIALS

NAMES = sorted(MATERIALS.keys())


def _room_temp_value(curve):  # noqa: ANN001, ANN202
    """First (lowest-temperature) point of a (T_K, value) property curve."""
    return min(curve, key=lambda tv: tv[0])[1]


@pytest.mark.parametrize("name", NAMES)
def test_density_physically_plausible(name: str) -> None:
    rho = MATERIALS[name].density_kg_per_m3
    assert 1500.0 < rho < 20000.0


@pytest.mark.parametrize("name", NAMES)
def test_poisson_ratio_in_open_unit_interval(name: str) -> None:
    nu = MATERIALS[name].poisson
    assert 0.0 < nu < 0.5


@pytest.mark.parametrize("name", NAMES)
def test_yield_below_ultimate_at_room_temperature(name: str) -> None:
    y = _room_temp_value(MATERIALS[name].yield_strength_MPa)
    u = _room_temp_value(MATERIALS[name].ultimate_strength_MPa)
    assert 0.0 < y < u


@pytest.mark.parametrize("name", NAMES)
def test_youngs_modulus_in_metal_range(name: str) -> None:
    e = _room_temp_value(MATERIALS[name].youngs_modulus_GPa)
    assert 50.0 < e < 450.0


@pytest.mark.parametrize("name", NAMES)
def test_youngs_modulus_softens_with_temperature(name: str) -> None:
    """Elastic modulus decreases monotonically with temperature for metals."""
    curve = sorted(MATERIALS[name].youngs_modulus_GPa, key=lambda tv: tv[0])
    vals = [v for _t, v in curve]
    for hot_lower, cool_higher in zip(vals[1:], vals[:-1]):
        assert hot_lower <= cool_higher + 1e-9


def test_titanium_6al4v_known_properties() -> None:
    m = MATERIALS["Ti-6Al-4V"]
    assert 4400.0 <= m.density_kg_per_m3 <= 4520.0
    assert 100.0 <= _room_temp_value(m.youngs_modulus_GPa) <= 120.0


def test_inconel_718_known_properties() -> None:
    m = MATERIALS["Inconel 718"]
    assert 8100.0 <= m.density_kg_per_m3 <= 8300.0
    assert 195.0 <= _room_temp_value(m.youngs_modulus_GPa) <= 215.0


def test_stainless_316l_known_density() -> None:
    assert 7900.0 <= MATERIALS["316L"].density_kg_per_m3 <= 8100.0
