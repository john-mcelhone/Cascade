/**
 * The /learn glossary. ~120 turbomachinery terms used in the tutorial.
 *
 * Each entry: term, 1-3 sentence definition, the chapter where it
 * first appears (for hot-linking), and an optional Cascade feature link.
 *
 * The keying convention: sort key is lowercase first letter; display
 * name preserves case (e.g. "M_rel", "n_s", "Brayton cycle").
 */

export interface GlossaryEntry {
  /** Display term, with the original casing. */
  term: string;
  /** First-letter group for A-Z navigation. Always uppercase. */
  letter: string;
  /** 1-3 sentence definition. */
  definition: string;
  /** Chapter slug where the term is introduced (for hot-linking). */
  chapter?: string;
  /** Optional deep-link into Cascade. */
  pageHref?: string;
  /** Optional short feature label paired with `pageHref`. */
  pageLabel?: string;
}

function letter(t: string): string {
  // Take the first alphabetic character. Greek letters fall back to "Other".
  const m = /[A-Za-z]/.exec(t);
  return m ? m[0].toUpperCase() : "Other";
}

const RAW: Array<Omit<GlossaryEntry, "letter">> = [
  // A
  {
    term: "absolute frame",
    definition:
      "The non-rotating reference frame attached to the casing. Absolute velocity V is the fluid velocity observed in this frame. Compare relative frame.",
    chapter: "3-why-its-hard",
  },
  {
    term: "amplification factor (Q)",
    definition:
      "The ratio of resonant peak amplitude to the static deflection at the same forcing level. API 684 separation-margin formulas use Q as a relaxation parameter; high-Q rotors need wider margin.",
    chapter: "8-rotor-dynamics",
  },
  {
    term: "anti-surge valve",
    definition:
      "A control valve that recycles compressor discharge back to inlet when the operating point approaches the surge boundary. Standard on industrial centrifugal compressors.",
    chapter: "7-performance-maps",
  },
  {
    term: "API 617",
    definition:
      "The American Petroleum Institute standard for centrifugal compressors, including rotor-dynamic acceptance criteria (residual unbalance limits, separation margins, vibration levels).",
    chapter: "8-rotor-dynamics",
  },
  {
    term: "API 684",
    definition:
      "The industry-standard rotor-dynamic tutorial. Defines amplification factor, log decrement, and separation margin in a vocabulary used by every major OEM.",
    chapter: "8-rotor-dynamics",
  },
  {
    term: "axial",
    definition:
      "A turbomachine geometry family where the flow direction is largely parallel to the rotor axis. Used at high specific speed and high mass flow.",
    chapter: "4-radial-vs-axial",
  },
  {
    term: "axisymmetric",
    definition:
      "A simplifying assumption that the geometry and flow field are independent of azimuthal angle. Mean-line and throughflow methods assume axisymmetric flow.",
    chapter: "4-radial-vs-axial",
  },

  // B
  {
    term: "blade",
    definition:
      "An aerofoil mounted on the rotor or stator that turns the flow. The blade does work on the fluid (compressor) or extracts work from it (turbine).",
    chapter: "1-what-is-a-turbine",
  },
  {
    term: "blade angle",
    definition:
      "The angle the blade leading or trailing edge makes with a reference direction. Cascade defaults to angles measured from axial; the legacy tools' convention is angles from tangential.",
    chapter: "3-why-its-hard",
  },
  {
    term: "blade-to-blade plane",
    definition:
      "The 2D plane formed by unwrapping a cylindrical section through a blade row. Used for blade-to-blade Euler / RANS analysis of stage aerodynamics.",
    chapter: "4-radial-vs-axial",
  },
  {
    term: "boundary condition",
    definition:
      "Total pressure, total temperature, mass flow, and composition specified at the inlet or outlet of a component. Cascade stores BCs in the typed Port structure (SPEC_SHEET §3.1).",
    chapter: "2-brayton-cycle",
  },
  {
    term: "Brayton cycle",
    definition:
      "The thermodynamic cycle of gas turbines and jet engines: compress, heat, expand. The simplest open-cycle form has four idealized processes.",
    chapter: "2-brayton-cycle",
  },
  {
    term: "burner",
    definition:
      "Synonym for combustor. The component that adds heat to the working fluid by burning fuel.",
    chapter: "2-brayton-cycle",
  },

  // C
  {
    term: "Campbell diagram",
    definition:
      "Mode frequency plotted vs rotor RPM, with engine-order lines overlaid. Crossings of mode lines with engine-order lines flag potential resonances.",
    chapter: "8-rotor-dynamics",
  },
  {
    term: "candidate",
    definition:
      "A specific point in the design space waiting to be evaluated or selected. The Cascade term that replaces 'design' or 'permutation' (Cascade naming convention).",
    chapter: "6-design-exploration",
    pageHref: "/projects/microturbine-30kw/flowpath",
    pageLabel: "Flow Path PD",
  },
  {
    term: "cantilever",
    definition:
      "A rotor configuration with both bearings on the same side of an impeller, so the impeller is overhung. Distinguishes from a 'between-bearings' arrangement.",
    chapter: "8-rotor-dynamics",
  },
  {
    term: "Capstone",
    definition:
      "Capstone Turbine Corporation (now Capstone Green Energy). Manufacturer of the C30, C65, and C200 microturbines used as Cascade's primary validation reference for the cycle solver.",
    chapter: "9-the-workflow",
  },
  {
    term: "cascade",
    definition:
      "A row of blades viewed in two dimensions for aerodynamic analysis. 'Cascade testing' is the rig-test method for measuring profile loss.",
    chapter: "5-loss-models",
  },
  {
    term: "characterization test",
    definition:
      "A validation case whose result is tracked and reported but does not block CI on failure. Pairs with 'pass-gate test'.",
    chapter: "10-validation",
  },
  {
    term: "choke",
    definition:
      "The right boundary of a compressor map: the throat reaches Mach 1 and mass flow saturates. Further reduction in back pressure produces no extra flow.",
    chapter: "7-performance-maps",
    pageHref: "/projects/microturbine-30kw/map",
    pageLabel: "Map page",
  },
  {
    term: "choked",
    definition:
      "Describes a flow path operating at the choke condition. Cascade's map solver returns CHOKED as one of its eight explicit per-point codes.",
    chapter: "7-performance-maps",
  },
  {
    term: "choke line",
    definition:
      "The right-side locus on a compressor map, connecting the rightmost converged point on each speedline.",
    chapter: "7-performance-maps",
  },
  {
    term: "clearance",
    definition:
      "The gap between rotating and stationary components, typically tip clearance (rotor blade tip to casing). A key source of leakage loss.",
    chapter: "5-loss-models",
  },
  {
    term: "compressor",
    definition:
      "A turbomachine that adds energy to a fluid, raising its total pressure. Operates in the opposite direction to a turbine.",
    chapter: "1-what-is-a-turbine",
  },
  {
    term: "conservation of mass",
    definition:
      "ṁ in = ṁ out at steady state. The first of three governing principles for any compressible-flow machine.",
    chapter: "3-why-its-hard",
  },
  {
    term: "conservation of energy",
    definition:
      "The first law of thermodynamics applied across a control volume: Δh_0 = q − w. For an adiabatic rotor, the work extraction equals the total-enthalpy drop.",
    chapter: "3-why-its-hard",
  },
  {
    term: "conservation of momentum",
    definition:
      "Newton's second law applied to fluid mass. In a rotating turbomachinery rotor, the Euler turbine equation is its angular form.",
    chapter: "3-why-its-hard",
  },
  {
    term: "cooled turbine",
    definition:
      "A turbine stage where coolant air is bled from the compressor and routed through hollow blades to cool the metal. Enables turbine-inlet temperatures above the material limit.",
    chapter: "9-the-workflow",
  },
  {
    term: "Cordier diagram",
    definition:
      "A log-log plot of specific diameter vs specific speed with efficiency contours. Named after Otto Cordier (1955), it tells the designer which geometry family (radial / mixed / axial) is optimal for given n_s.",
    chapter: "4-radial-vs-axial",
  },
  {
    term: "corrected flow",
    definition:
      "Mass flow normalized to reference inlet conditions: ṁ_corr = ṁ·√θ/δ. Makes a compressor map independent of ambient temperature and pressure.",
    chapter: "7-performance-maps",
  },
  {
    term: "corrected speed",
    definition:
      "Rotational speed normalized to reference inlet temperature: N_corr = N/√θ. Pairs with corrected mass flow on a compressor map.",
    chapter: "7-performance-maps",
  },
  {
    term: "critical speed",
    definition:
      "A rotor speed at which the spin frequency matches one of the rotor's damped natural frequencies. Synchronous unbalance excites the corresponding mode strongly at this RPM.",
    chapter: "8-rotor-dynamics",
  },

  // D
  {
    term: "deck",
    definition:
      "A complete project state stored as a TOML file (or set of files). Borrowed from NPSS aerospace tradition. Cascade's project format is one .cascade directory of decks.",
    chapter: "9-the-workflow",
  },
  {
    term: "design exploration",
    definition:
      "Sobol' sampling over the free design parameters followed by per-candidate forward solves. Cascade's term for what other tools call an 'inverse solver' (which is misleading).",
    chapter: "6-design-exploration",
    pageHref: "/projects/microturbine-30kw/flowpath",
    pageLabel: "Flow Path PD",
  },
  {
    term: "design point",
    definition:
      "The single operating condition for which the geometry is optimized. Off-design behavior radiates out from this point on the performance map.",
    chapter: "7-performance-maps",
  },
  {
    term: "design space",
    definition:
      "The high-dimensional set of all possible parameter combinations a designer might choose. For a single-stage radial turbine this is typically a 5-15 dimensional box.",
    chapter: "6-design-exploration",
  },
  {
    term: "deviation",
    definition:
      "The angle between the blade trailing edge and the actual fluid exit direction. Caused by finite blade count and tip leakage; modeled by slip-factor correlations.",
    chapter: "3-why-its-hard",
  },
  {
    term: "diffuser",
    definition:
      "A diverging passage that converts kinetic energy back into pressure rise. Sits immediately after the impeller in a centrifugal compressor.",
    chapter: "5-loss-models",
  },
  {
    term: "disc",
    definition:
      "The rotating element that carries the blades, attaching them to the shaft. Disc stress at the bore typically limits achievable tip speed.",
    chapter: "5-loss-models",
  },
  {
    term: "disc friction",
    definition:
      "Power loss from windage between the impeller back-face and the stationary casing. Often modeled by the Daily-Nece correlation (1960).",
    chapter: "5-loss-models",
  },
  {
    term: "dynamic viscosity",
    definition:
      "μ — the ratio of shear stress to shear rate in a fluid. Appears in the Reynolds number, journal-bearing Reynolds equation, and skin-friction loss models.",
    chapter: "5-loss-models",
  },

  // E
  {
    term: "efficiency",
    definition:
      "The ratio of actual to ideal work transfer. Multiple definitions exist; the choice (total-to-total, total-to-static, polytropic, isentropic) must be stated when reporting.",
    chapter: "1-what-is-a-turbine",
  },
  {
    term: "Euler turbine equation",
    definition:
      "Δh_0 = U·ΔV_θ. The work done per unit mass equals the wheel speed times the change in tangential velocity. Derives from angular-momentum conservation.",
    chapter: "3-why-its-hard",
  },
  {
    term: "exhaust",
    definition:
      "The discharge stream from a turbine. In a Brayton cycle, exhaust gas leaving the recuperator's hot side becomes the cycle's heat rejection.",
    chapter: "2-brayton-cycle",
  },
  {
    term: "exit",
    definition:
      "Synonym for outlet. The downstream boundary of a component or stage.",
    chapter: "3-why-its-hard",
  },

  // F
  {
    term: "fluid",
    definition:
      "The working substance. In Cascade, a discriminated union: a NASA-9 polynomial mixture for combustion gas, or a CoolProp pure species for sCO₂ / He / H₂ / steam.",
    chapter: "2-brayton-cycle",
  },
  {
    term: "free vortex",
    definition:
      "A flow with constant angular momentum per unit mass: r·V_θ = const. The classical 1D assumption for axisymmetric stage design.",
    chapter: "3-why-its-hard",
  },
  {
    term: "fuel mass flow",
    definition:
      "ṁ_fuel — the rate of fuel injection into the combustor. Sets the cycle's heat addition Q = ṁ_fuel · LHV.",
    chapter: "2-brayton-cycle",
  },

  // G
  {
    term: "gas turbine",
    definition:
      "A heat engine that runs the Brayton cycle on a continuous flow of hot gas. Distinguished from a steam turbine (which uses a Rankine cycle with phase change).",
    chapter: "2-brayton-cycle",
  },
  {
    term: "generator",
    definition:
      "An electrical machine driven by the rotor to produce shaft power output as electricity. In a microturbine, often direct-drive at 60-100 krpm with a power-electronics converter.",
    chapter: "9-the-workflow",
  },
  {
    term: "geometry",
    definition:
      "The mathematical description of a wheel or blade row, typically a B-spline mean-line plus hub/shroud curves and a thickness distribution. Exportable as STEP / IGES / STL.",
    chapter: "6-design-exploration",
  },
  {
    term: "glTF",
    definition:
      "A JSON-based 3D geometry format used for browser-side previews. Cascade renders the picked candidate's wheel via glTF on the Flow Path PD page.",
    chapter: "9-the-workflow",
  },
  {
    term: "gyroscopic coupling",
    definition:
      "The cross-coupling between lateral translation and lateral rotation in a spinning disk. Encoded in the G matrix of the rotor equation of motion.",
    chapter: "8-rotor-dynamics",
  },

  // H
  {
    term: "h-s diagram",
    definition:
      "A thermodynamic plot of specific enthalpy vs specific entropy. Reads work output as vertical distance; reads loss as horizontal distance from isentropic.",
    chapter: "2-brayton-cycle",
  },
  {
    term: "hub",
    definition:
      "The inner surface of the flow passage in an axial machine, or the inner streamline of a radial machine. Pairs with shroud.",
    chapter: "4-radial-vs-axial",
  },
  {
    term: "hub-to-tip ratio",
    definition:
      "The ratio of hub radius to tip radius at a blade row. Low ratio = more radial flow; high ratio = closer to axial.",
    chapter: "4-radial-vs-axial",
  },

  // I
  {
    term: "impeller",
    definition:
      "The rotating wheel of a centrifugal compressor or radial-inflow turbine. Has blades plus a hub plus a back-disc.",
    chapter: "4-radial-vs-axial",
  },
  {
    term: "incidence",
    definition:
      "The angle between the inlet flow and the blade leading-edge angle. Off-design incidence causes a loss as the boundary layer separates from the wrong side of the blade.",
    chapter: "5-loss-models",
  },
  {
    term: "inducer",
    definition:
      "The first portion of a centrifugal compressor impeller, where flow turns from axial to radial. Often the location of peak relative Mach.",
    chapter: "4-radial-vs-axial",
  },
  {
    term: "inlet",
    definition:
      "The upstream boundary of a component. The duct, cascade, or guide vane that brings flow into the rotor.",
    chapter: "3-why-its-hard",
  },
  {
    term: "intercooler",
    definition:
      "A heat exchanger between two compressor stages that reduces the inlet temperature of the second stage. Reduces specific work but adds a pressure drop.",
    chapter: "2-brayton-cycle",
  },
  {
    term: "isentropic",
    definition:
      "Constant-entropy. The idealized reversible adiabatic process. Real machines deviate from isentropic by losses; the deviation is the entropy generated.",
    chapter: "2-brayton-cycle",
  },
  {
    term: "isentropic efficiency",
    definition:
      "η_s = actual Δh / isentropic Δh. The fractional approach to the ideal reversible-adiabatic process.",
    chapter: "2-brayton-cycle",
  },

  // J
  {
    term: "jet engine",
    definition:
      "A gas turbine arranged to produce thrust rather than shaft power. Same Brayton cycle, different output device.",
    chapter: "2-brayton-cycle",
  },
  {
    term: "journal bearing",
    definition:
      "A fluid-film bearing in which a journal (the shaft) rotates inside a stationary sleeve, separated by an oil or air film. Cascade models them with the Reynolds equation + Christopherson PSOR cavitation BC.",
    chapter: "8-rotor-dynamics",
  },

  // K
  {
    term: "kinetic energy",
    definition:
      "V²/2 per unit mass. In a turbomachinery rotor, kinetic energy is the immediate carrier of work; static enthalpy converts to/from KE at every stage.",
    chapter: "3-why-its-hard",
  },

  // L
  {
    term: "lateral",
    definition:
      "Perpendicular to the rotor axis. Lateral rotor dynamics concerns bending modes; torsional and axial are the other two coordinate families.",
    chapter: "8-rotor-dynamics",
  },
  {
    term: "leakage",
    definition:
      "Flow that bypasses the intended path of a machine, through clearance gaps and seal cavities. Always reduces efficiency.",
    chapter: "5-loss-models",
  },
  {
    term: "log decrement",
    definition:
      "δ — the natural logarithm of the ratio of successive vibration cycles in a damped free response. API 684 requires δ ≥ 0.1 at Level I for rotor stability.",
    chapter: "8-rotor-dynamics",
  },
  {
    term: "loss model",
    definition:
      "A correlation that predicts entropy generation across one specific loss mechanism (profile, secondary, tip clearance, etc.). Every Cascade loss model carries an open citation.",
    chapter: "5-loss-models",
  },
  {
    term: "lumped disk",
    definition:
      "A rotor-dynamic idealization where an impeller is represented by a point mass plus polar and diametrical moments of inertia at its centroid.",
    chapter: "8-rotor-dynamics",
  },

  // M
  {
    term: "M_rel",
    definition:
      "Relative Mach number — Mach computed using the velocity in the rotor-attached reference frame. Subsonic meanlines require M_rel < ~0.95 at every station.",
    chapter: "3-why-its-hard",
  },
  {
    term: "Mach number",
    definition:
      "M = V/a, the ratio of fluid speed to local sound speed. A dimensionless measure of compressibility; > 1 means supersonic with attendant shock losses.",
    chapter: "3-why-its-hard",
  },
  {
    term: "mass flow",
    definition:
      "ṁ — the rate at which mass crosses a control surface, in kg/s. The horizontal axis of a compressor map after correction.",
    chapter: "2-brayton-cycle",
  },
  {
    term: "mean line",
    definition:
      "A 1D analysis along the mid-streamline of a turbomachine. The simplest engineering model; Cascade's mean-line core is the fast inner loop of design exploration.",
    chapter: "5-loss-models",
  },
  {
    term: "meridional",
    definition:
      "The plane containing the rotor axis and the radial direction. The 'meridional view' of a machine shows the hub and shroud curves in this plane.",
    chapter: "4-radial-vs-axial",
  },
  {
    term: "microturbine",
    definition:
      "A gas turbine of 1-200 kW shaft power. Recuperated Brayton cycle, single-stage radial compressor + radial turbine, direct-drive generator. The customer profile for Cascade.",
    chapter: "9-the-workflow",
  },
  {
    term: "mode shape",
    definition:
      "The lateral deflection pattern of the rotor at one of its natural frequencies. Mode 1 is bending; mode 2 is S-shape; mode 3 is W-shape.",
    chapter: "8-rotor-dynamics",
  },

  // N
  {
    term: "NACA",
    definition:
      "The U.S. National Advisory Committee for Aeronautics (1915-1958), predecessor to NASA. Published many of the canonical blade-profile families still in use.",
    chapter: "5-loss-models",
  },
  {
    term: "NASA",
    definition:
      "The U.S. National Aeronautics and Space Administration. Authoritative source for many Cascade validation cases (TM-102368, TN D-7508, SP-290, CR series).",
    chapter: "10-validation",
  },
  {
    term: "n_s",
    definition:
      "Specific speed — a dimensionless rotor speed normalized by flow rate and head. Determines whether radial, mixed-flow, or axial geometry is optimal (Cordier diagram).",
    chapter: "4-radial-vs-axial",
  },
  {
    term: "NSGA-II",
    definition:
      "Non-dominated Sorting Genetic Algorithm II — the canonical multi-objective optimizer for Pareto-front exploration. Deb et al. 2002.",
    chapter: "6-design-exploration",
  },

  // O
  {
    term: "off-design",
    definition:
      "Operating conditions other than the single design point. The performance map quantifies off-design behavior.",
    chapter: "7-performance-maps",
  },
  {
    term: "OPR",
    definition:
      "Overall pressure ratio — the cumulative pressure rise across all compressor stages of an engine. Aircraft engines run OPR = 30-60; microturbines OPR = 3-6.",
    chapter: "2-brayton-cycle",
  },
  {
    term: "optimization",
    definition:
      "An algorithm that returns a recommended design under explicit objectives and constraints. Distinct from design exploration, which scatters and lets the engineer pick.",
    chapter: "6-design-exploration",
  },
  {
    term: "ω",
    definition:
      "Angular velocity, rad/s. The base SI representation of rotor speed; Cascade displays as RPM for convenience but stores ω canonically.",
    chapter: "3-why-its-hard",
  },

  // P
  {
    term: "Pareto front",
    definition:
      "The set of non-dominated candidates in a multi-objective optimization. No candidate on the front is strictly better than any other across all objectives.",
    chapter: "6-design-exploration",
  },
  {
    term: "pass-gate test",
    definition:
      "A validation case whose failure blocks CI on main. Distinguished from a characterization test, which is informational.",
    chapter: "10-validation",
  },
  {
    term: "Pelton wheel",
    definition:
      "An impulse hydraulic turbine where high-velocity jets strike cups on a wheel. Pure impulse (zero reaction); the textbook simple case for velocity-triangle analysis.",
    chapter: "3-why-its-hard",
  },
  {
    term: "performance map",
    definition:
      "A 2D plot of pressure ratio vs corrected mass flow at multiple corrected speeds. Bounded by the surge line on the left and the choke line on the right.",
    chapter: "7-performance-maps",
  },
  {
    term: "PR (pressure ratio)",
    definition:
      "π = p_out / p_in. A compressor raises pressure (PR > 1); a turbine drops it (PR < 1 across the rotor).",
    chapter: "2-brayton-cycle",
  },
  {
    term: "pressure ratio",
    definition:
      "See PR. Total-to-total π_tt, total-to-static π_ts — the choice matters for definition consistency.",
    chapter: "2-brayton-cycle",
  },
  {
    term: "pressure total",
    definition:
      "p_t — the pressure a fluid would have if brought isentropically to rest. The pressure variable used in turbomachinery boundary conditions.",
    chapter: "2-brayton-cycle",
  },
  {
    term: "prime mover",
    definition:
      "The shaft-power output device of a power-generation system. A microturbine's prime mover is the gas turbine rotor.",
    chapter: "1-what-is-a-turbine",
  },
  {
    term: "profile loss",
    definition:
      "Skin-friction loss on the blade surface. Modeled by correlations (Soderberg, Ainley-Mathieson, Kacker-Okapuu) calibrated to cascade-test data.",
    chapter: "5-loss-models",
  },

  // R
  {
    term: "radial",
    definition:
      "A turbomachine geometry family where the flow direction is mostly radial through the rotor. Used at low specific speed and high pressure-ratio-per-stage.",
    chapter: "4-radial-vs-axial",
  },
  {
    term: "RANS",
    definition:
      "Reynolds-Averaged Navier-Stokes — the time-averaged CFD approach. Cascade is not a RANS solver; it ships adapters to send geometry into OpenFOAM / StarCCM+ for CFD confirmation.",
    chapter: "9-the-workflow",
  },
  {
    term: "reaction",
    definition:
      "R — the fraction of stage total-enthalpy drop that occurs in the rotor (vs the stator). R = 0 is pure impulse; R = 0.5 is symmetric.",
    chapter: "3-why-its-hard",
  },
  {
    term: "real-gas",
    definition:
      "A working-fluid model that accounts for non-ideal compressibility. NASA-9 polynomial mixtures and CoolProp HEOS handle this in Cascade.",
    chapter: "2-brayton-cycle",
  },
  {
    term: "recuperator",
    definition:
      "A counterflow heat exchanger in a Brayton cycle that uses turbine exhaust heat to preheat compressor discharge. Adds 5-15 points to thermal efficiency.",
    chapter: "2-brayton-cycle",
  },
  {
    term: "recuperator effectiveness",
    definition:
      "ε_recup = (T_cold,out − T_cold,in) / (T_hot,in − T_cold,in). A standard microturbine target is 0.85-0.90.",
    chapter: "2-brayton-cycle",
  },
  {
    term: "relative frame",
    definition:
      "The rotating reference frame attached to the impeller. Relative velocity W = V − U. Compare absolute frame.",
    chapter: "3-why-its-hard",
  },
  {
    term: "rotor",
    definition:
      "The rotating element of a turbomachine, comprising shaft + impellers + disks. Distinct from the casing-side stators / nozzles.",
    chapter: "1-what-is-a-turbine",
  },
  {
    term: "rotor dynamics",
    definition:
      "The discipline that predicts and controls vibration of rotating shafts. Covers critical speeds, unbalance response, and stability.",
    chapter: "8-rotor-dynamics",
    pageHref: "/projects/microturbine-30kw/rotor",
    pageLabel: "Rotor page",
  },
  {
    term: "RPM",
    definition:
      "Revolutions per minute. Display unit for rotor speed; Cascade stores ω in rad/s canonically and converts at the I/O layer.",
    chapter: "3-why-its-hard",
  },

  // S
  {
    term: "sCO2",
    definition:
      "Supercritical carbon dioxide. A working fluid for high-temperature low-volume power cycles. Compressor inlet near critical (7.5 MPa, 308 K) gives unusually high efficiency.",
    chapter: "2-brayton-cycle",
  },
  {
    term: "scroll",
    definition:
      "Synonym for volute. A spiral collector that decelerates and de-swirls the impeller discharge before it enters the diffuser.",
    chapter: "5-loss-models",
  },
  {
    term: "secondary loss",
    definition:
      "Loss from corner vortices where the blade meets the hub and shroud. Modeled separately from profile loss in modern correlations.",
    chapter: "5-loss-models",
  },
  {
    term: "separation margin",
    definition:
      "The percentage gap between operating speed and the nearest critical speed. API 684 requires ≥ 16% above MCS and ≥ 26% below the minimum allowed speed.",
    chapter: "8-rotor-dynamics",
  },
  {
    term: "shaft",
    definition:
      "The cylindrical metal beam that connects the impellers and transfers torque. Modeled as Timoshenko beam elements in rotor dynamics.",
    chapter: "8-rotor-dynamics",
  },
  {
    term: "shock loss",
    definition:
      "Entropy generated by a shock wave when the relative Mach exceeds 1. Modeled by Moustapha 2003 (axial turbine) or Kacker-Okapuu with shock term.",
    chapter: "5-loss-models",
  },
  {
    term: "shroud",
    definition:
      "The outer surface of the flow passage. In a 'shrouded impeller', the shroud rotates with the blades; in an 'unshrouded' design, it is stationary with a tip-clearance gap.",
    chapter: "4-radial-vs-axial",
  },
  {
    term: "slip factor",
    definition:
      "σ — the ratio of actual to ideal tangential velocity at the impeller exit. Wiesner, Stanitz, and Stodola correlations are the standard choices. Default: Wiesner.",
    chapter: "5-loss-models",
  },
  {
    term: "Sobol' sequence",
    definition:
      "A deterministic low-discrepancy sequence in [0,1]^d. Used for design exploration sampling because of its extensible, well-distributed property.",
    chapter: "6-design-exploration",
  },
  {
    term: "specific speed",
    definition:
      "See n_s. The single most informative dimensionless number for choosing turbomachinery geometry family.",
    chapter: "4-radial-vs-axial",
  },
  {
    term: "specific work",
    definition:
      "w = W/ṁ — work output per unit mass flow, in J/kg. The cycle's specific work times the design mass flow gives shaft power.",
    chapter: "2-brayton-cycle",
  },
  {
    term: "spool",
    definition:
      "An independent compressor-turbine shaft. Multi-spool engines (turbofans, advanced industrial turbines) match the optimal RPM for low-pressure vs high-pressure stages.",
    chapter: "2-brayton-cycle",
  },
  {
    term: "stagnation",
    definition:
      "The state a fluid would reach if brought isentropically to rest. Stagnation pressure (total pressure) and stagnation temperature (total temperature) are reference values for compressible flow.",
    chapter: "3-why-its-hard",
  },
  {
    term: "stall",
    definition:
      "Flow separation from the blade suction surface caused by excessive incidence. Rotating stall is a precursor to surge.",
    chapter: "7-performance-maps",
  },
  {
    term: "Stanitz slip factor",
    definition:
      "σ = 1 − 0.63π/Z, a 1952 Stanitz correlation for centrifugal impeller slip. Simpler than Wiesner; appropriate for radial-bladed impellers.",
    chapter: "5-loss-models",
  },
  {
    term: "stator",
    definition:
      "A non-rotating blade row whose purpose is to guide flow into the next rotor. Compressor stators turn flow back toward axial; turbine nozzles turn it tangentially.",
    chapter: "3-why-its-hard",
  },
  {
    term: "steam cycle",
    definition:
      "A Rankine power cycle using water/steam as the working fluid, with a phase change in the boiler and condenser. Distinct from the Brayton cycle.",
    chapter: "2-brayton-cycle",
  },
  {
    term: "STEP file",
    definition:
      "An ISO 10303 neutral CAD interchange format (AP242 for Cascade). The standard way to hand 3D geometry off to CFD or FEA contractors.",
    chapter: "9-the-workflow",
  },
  {
    term: "surge",
    definition:
      "Flow reversal in a compressor caused by trying to push too high a pressure ratio at too low a mass flow. Violent, audible, destructive. The left boundary of the operating map.",
    chapter: "7-performance-maps",
  },

  // T
  {
    term: "tip clearance",
    definition:
      "The radial gap between an unshrouded blade tip and the casing. Tip-clearance loss is one of the largest individual losses in unshrouded impellers (~2 pt for typical microturbine designs).",
    chapter: "5-loss-models",
  },
  {
    term: "total enthalpy",
    definition:
      "h_0 = h + V²/2. The thermodynamic potential conserved across an adiabatic, work-free duct (Bernoulli-like).",
    chapter: "3-why-its-hard",
  },
  {
    term: "total pressure",
    definition:
      "See pressure total.",
    chapter: "2-brayton-cycle",
  },
  {
    term: "total temperature",
    definition:
      "T_t = T + V²/(2c_p). The stagnation temperature, conserved across an adiabatic flow with no work transfer.",
    chapter: "2-brayton-cycle",
  },
  {
    term: "trailing-edge loss",
    definition:
      "Loss from wake mixing downstream of a finite-thickness blade trailing edge. Modeled by Kacker-Okapuu (axial) or by the Aungier correlation (radial).",
    chapter: "5-loss-models",
  },
  {
    term: "transient",
    definition:
      "Time-varying solution, as opposed to steady-state. Cascade's cycle solver supports transient simulation via BDF integration; mean-line is steady-only in v1.",
    chapter: "2-brayton-cycle",
  },
  {
    term: "turbine",
    definition:
      "A turbomachine that extracts work from a flowing fluid by turning rotor blades. The complement of a compressor.",
    chapter: "1-what-is-a-turbine",
  },
  {
    term: "turbine inlet temperature (TIT)",
    definition:
      "T_t at the rotor inlet of the first turbine stage. Limited by material capability (uncooled) or coolant supply (cooled). Drives the cycle thermal efficiency.",
    chapter: "2-brayton-cycle",
  },
  {
    term: "turbocharger",
    definition:
      "A small radial compressor driven by a small radial turbine on a common shaft, used to boost the inlet of a piston engine. The most-built application of turbomachinery.",
    chapter: "1-what-is-a-turbine",
  },

  // U
  {
    term: "unbalance response",
    definition:
      "The steady-state lateral displacement of the rotor at the synchronous (1×) excitation frequency. API 617 limits this to a function of operating speed and rotor mass.",
    chapter: "8-rotor-dynamics",
  },
  {
    term: "units",
    definition:
      "Cascade's strict typed unit system. Every quantity carries dimension and unit; mixed-unit operations raise an error at construction. SI canonical; degrees / RPM / psi accepted on opt-in.",
    chapter: "10-validation",
  },

  // V
  {
    term: "validation case",
    definition:
      "A test that compares a Cascade output to a published reference value, with a documented source and a published tolerance. Cascade v1 ships 45 pass-gates + 126 characterization cases.",
    chapter: "10-validation",
  },

  // W
  {
    term: "Walsh & Fletcher",
    definition:
      "Walsh, P. P. and Fletcher, P., *Gas Turbine Performance* (2nd ed., Blackwell 2004). The canonical textbook for corrected quantities, cycle modeling, and operational performance.",
    chapter: "7-performance-maps",
  },
  {
    term: "whirling",
    definition:
      "Lateral orbital motion of a spinning rotor. Forward whirl: same sense as spin. Backward whirl: opposite. Oil whirl / oil whip: a subsynchronous instability.",
    chapter: "8-rotor-dynamics",
  },
  {
    term: "Wiesner slip factor",
    definition:
      "σ = 1 − √(cos β_2b) / Z^{0.7}, a 1967 correlation for centrifugal impeller slip. Default in Cascade; switchable to Stanitz, Stodola, Busemann, or Eck.",
    chapter: "5-loss-models",
  },
  {
    term: "work",
    definition:
      "Energy transferred to or from the rotor. Per unit mass, w = U·ΔV_θ for a turbomachinery stage (Euler turbine equation).",
    chapter: "3-why-its-hard",
  },

  // Y
  {
    term: "Y_shock",
    definition:
      "The shock-loss term in the Kacker-Okapuu axial-turbine loss decomposition. Calibrated by Moustapha 2003 (NASA TM-2003-211807) for transonic relative inflow.",
    chapter: "5-loss-models",
  },

  // Z
  {
    term: "zero-D cycle",
    definition:
      "A thermodynamic cycle modeled by component-level steady-state mass/energy balances, without spatial resolution. Cascade's Cycle Canvas is zero-D.",
    chapter: "2-brayton-cycle",
  },

  // Extras (deepening common terms)
  {
    term: "Aungier 2000",
    definition:
      "Aungier, R. H., *Centrifugal Compressors: A Strategy for Aerodynamic Design and Analysis* (ASME Press 2000). Cascade's default centrifugal-compressor loss model set.",
    chapter: "5-loss-models",
  },
  {
    term: "Whitfield & Baines 1990",
    definition:
      "Whitfield, A. and Baines, N. C., *Design of Radial Turbomachines* (Longman 1990). Cascade's default radial-inflow-turbine loss model set.",
    chapter: "5-loss-models",
  },
  {
    term: "Kacker-Okapuu",
    definition:
      "Kacker, S. C. and Okapuu, U., 1982 ASME J Eng Power. The canonical axial-turbine loss model. Cascade extends it with the Moustapha 2003 shock term.",
    chapter: "5-loss-models",
  },
  {
    term: "Koch-Smith",
    definition:
      "Koch, C. C. and Smith, L. H., 1976. Axial-compressor loss prediction. Pairs with the Casey 1987 deviation correlation in Cascade's axial-compressor mean-line.",
    chapter: "5-loss-models",
  },
  {
    term: "Soderberg 1949",
    definition:
      "Soderberg, C. R., 1949 unpublished MIT note. A simple, broadly-applicable axial-turbine loss correlation; useful for early-stage design when Kacker-Okapuu is overkill.",
    chapter: "5-loss-models",
  },
  {
    term: "isentropic spouting velocity (C_0)",
    definition:
      "C_0 = √(2 c_p T_in (1 − π_ts^{(γ−1)/γ})). The velocity a fluid would reach if expanded isentropically across the full pressure ratio. Pairs with u/C_0.",
    chapter: "3-why-its-hard",
  },
  {
    term: "u/C_0",
    definition:
      "Isentropic velocity ratio — wheel tip speed divided by spouting velocity. Whitfield & Baines 1990 says radial-inflow turbines peak at u/C_0 ≈ 0.68-0.72.",
    chapter: "3-why-its-hard",
  },
  {
    term: "psi (loading coefficient)",
    definition:
      "ψ = Δh_0 / U². Dimensionless stage loading. Higher ψ = more work per unit blade speed = larger blade turning = higher loss.",
    chapter: "3-why-its-hard",
  },
  {
    term: "phi (flow coefficient)",
    definition:
      "φ = V_m / U. Dimensionless flow rate. Smith-chart (Smith 1965) plots η contours on (ψ, φ) for axial turbines.",
    chapter: "3-why-its-hard",
  },
  {
    term: "Smith chart",
    definition:
      "Smith, S. F., 1965 — efficiency contours on (ψ, φ) for axial turbines. Tells the designer the optimal loading-flow region for a given stage.",
    chapter: "3-why-its-hard",
  },
  {
    term: "ε-NTU",
    definition:
      "Effectiveness-NTU method for sizing heat exchangers from total surface area and overall heat-transfer coefficient. Cascade uses ε-NTU for recuperators and intercoolers.",
    chapter: "2-brayton-cycle",
  },
  {
    term: "B-spline",
    definition:
      "A piecewise-polynomial parametric curve used for mean-line and blade-surface geometry. Cascade's geometry generation is B-spline-based throughout.",
    chapter: "6-design-exploration",
  },
  {
    term: "OCCT",
    definition:
      "Open Cascade Technology — the open-source CAD kernel Cascade uses for STEP / IGES / STL exports. Apache-2.0 licensed.",
    chapter: "9-the-workflow",
  },
  {
    term: "Sommerfeld number",
    definition:
      "S = μ N D L / (W ψ²). A dimensionless bearing-load parameter; characterizes the operating regime of a journal bearing.",
    chapter: "8-rotor-dynamics",
  },
  {
    term: "Eckardt Rotor O",
    definition:
      "A 1976 ASME-published back-swept centrifugal compressor with detailed hot-wire data. The most-cited validation case in centrifugal compressor literature (Cascade CC-2).",
    chapter: "10-validation",
  },
];

// Letter group + sort.
export const GLOSSARY: GlossaryEntry[] = RAW.map((e) => ({
  ...e,
  letter: letter(e.term),
})).sort((a, b) =>
  a.term.toLowerCase().localeCompare(b.term.toLowerCase()),
);

/** All letters that actually appear, in alphabetical order. */
export const GLOSSARY_LETTERS = Array.from(
  new Set(GLOSSARY.map((e) => e.letter)),
).sort();

export const GLOSSARY_COUNT = GLOSSARY.length;
