"""Valid, converging INPUT fixtures for the independent verification suite.

These are *inputs only*. The geometries below are real published machines
(Whitney-Stewart NASA TN D-7508 helium RIT; Eckardt Rotor A centrifugal
compressor) used purely because they are known to converge in a mean-line
solver. The independent suite NEVER asserts the Cascade implementation's own
output values against these — every expected value/bound in the test modules is
derived from physics (Euler work, conservation, kinematics, isentropic
relations) or from the published measurement, not from Cascade's code.
"""

from __future__ import annotations

import math

from cascade.units import Composition, Port, Q, Species

# --- Cycle ------------------------------------------------------------------


def air_inlet(p_kpa: float = 100.0, t_k: float = 300.0, mdot: float = 1.0) -> Port:
    return Port(
        pressure_total=Q(p_kpa, "kPa"),
        temperature_total=Q(t_k, "K"),
        mass_flow=Q(mdot, "kg/s"),
        composition=Composition.air(),
    )


# --- Radial inflow turbine (Whitney-Stewart NASA TN D-7508, helium) ---------
# Used only as a known-converging RIT input.

from cascade.meanline import (  # noqa: E402
    CentrifugalCompressorGeometry,
    RadialTurbineGeometry,
)

RIT_GEOMETRY = RadialTurbineGeometry(
    rotor_inlet_radius=0.076,
    rotor_outlet_radius_hub=0.019,
    rotor_outlet_radius_tip=0.0406,
    blade_height_inlet=0.012,
    blade_height_outlet=0.0216,
    blade_count=12,
    inlet_metal_angle_rad=0.0,
    exducer_angle_rad=math.radians(60),
    tip_clearance=0.00025,
)
RIT_INLET = Port(
    pressure_total=Q(220000, "Pa"),
    temperature_total=Q(1090.0, "K"),
    mass_flow=Q(0.13, "kg/s"),
    composition=Composition.pure(Species.HE),
)
RIT_RPM = Q(79000, "rpm")
RIT_INLET_RADIUS_M = 0.076

# --- Centrifugal compressor (Eckardt Rotor A, air) --------------------------

CC_GEOMETRY = CentrifugalCompressorGeometry(
    inducer_hub_radius=0.045,
    inducer_tip_radius=0.140,
    impeller_outlet_radius=0.200,
    blade_height_outlet=0.026,
    blade_count=20,
    beta_2_metal_rad=math.pi / 6,  # 30 deg backsweep from radial
    tip_clearance=0.0003,
    blockage_outlet=0.08,
)
CC_INLET = Port(
    pressure_total=Q(101325, "Pa"),
    temperature_total=Q(288.15, "K"),
    mass_flow=Q(5.31, "kg/s"),
    composition=Composition.air(),
)
CC_RPM = Q(14000, "rpm")
CC_OUTLET_RADIUS_M = 0.200
CC_BLADE_COUNT = 20
CC_BETA2_FROM_TANGENTIAL_RAD = math.pi / 3  # 60 deg from tangential
