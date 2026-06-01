"""Independent verification — slip-factor correlations.

Oracles are the published closed-form correlations evaluated at the
radial-bladed limit (blade angle = 90 deg from tangential), where they reduce
to unambiguous expressions independent of the from-radial/from-tangential
convention:

  Wiesner (1967):  sigma = 1 - sqrt(cos beta_2')/Z^0.7  -> 1 - 1/Z^0.7  (radial)
  Stanitz (1952):  sigma = 1 - 0.63*pi/Z
  Stodola  (1927): sigma = 1 - pi/Z                                      (radial)

plus the universal physical requirements: sigma in (0,1), monotone increasing
toward 1 as Z grows, and higher slip factor for backswept blades.
"""

from __future__ import annotations

import math

import pytest

from cascade.meanline import StanitzSlip, StodolaSlip, WiesnerSlip

RADIAL = math.pi / 2.0  # blade angle measured from the tangential direction


@pytest.mark.parametrize("z", [8, 12, 16, 20, 30])
def test_wiesner_radial_limit_closed_form(z: int) -> None:
    expected = 1.0 - 1.0 / z ** 0.7
    assert WiesnerSlip().slip_factor(z, RADIAL) == pytest.approx(expected, abs=1e-3)


@pytest.mark.parametrize("z", [8, 12, 16, 20, 30])
def test_stanitz_radial_limit_closed_form(z: int) -> None:
    expected = 1.0 - 0.63 * math.pi / z
    assert StanitzSlip().slip_factor(z, RADIAL) == pytest.approx(expected, abs=3e-3)


@pytest.mark.parametrize("z", [8, 12, 16, 20, 30])
def test_stodola_radial_limit_closed_form(z: int) -> None:
    expected = 1.0 - math.pi / z
    assert StodolaSlip().slip_factor(z, RADIAL) == pytest.approx(expected, abs=3e-3)


@pytest.mark.parametrize("model", [WiesnerSlip(), StanitzSlip(), StodolaSlip()])
def test_slip_factor_is_a_physical_fraction(model) -> None:  # noqa: ANN001
    # Realistic design envelope (centrifugal impellers carry >= 5 blades).
    # Z < 3 is documented as an extrapolation zone (SPEC §13), tested separately.
    for z in (5, 8, 12, 20, 40):
        s = model.slip_factor(z, RADIAL)
        assert 0.0 < s < 1.0


def test_stodola_below_validity_clips_with_warning() -> None:
    """SPEC §15: a slip factor below its validity (Z<=2, where the raw Stodola
    expression 1-pi/Z goes negative) must be clipped to a physical value AND
    flagged with a warning — never silently extrapolated."""
    with pytest.warns(Warning):
        s = StodolaSlip().slip_factor(2, RADIAL)
    assert 0.0 <= s <= 1.0


@pytest.mark.parametrize("model", [WiesnerSlip(), StanitzSlip(), StodolaSlip()])
def test_slip_factor_increases_with_blade_count(model) -> None:  # noqa: ANN001
    vals = [model.slip_factor(z, RADIAL) for z in (4, 8, 16, 32, 64)]
    for lo, hi in zip(vals, vals[1:]):
        assert hi > lo


@pytest.mark.parametrize("model", [WiesnerSlip(), StanitzSlip(), StodolaSlip()])
def test_slip_factor_approaches_unity_for_many_blades(model) -> None:  # noqa: ANN001
    assert model.slip_factor(1000, RADIAL) > 0.97


def test_wiesner_backswept_blades_have_higher_slip_factor_than_radial() -> None:
    """Wiesner: sqrt(cos beta_2') shrinks with backsweep, so sigma rises."""
    radial = WiesnerSlip().slip_factor(20, RADIAL)
    backswept = WiesnerSlip().slip_factor(20, math.radians(60))  # 30 deg from radial
    assert backswept > radial
