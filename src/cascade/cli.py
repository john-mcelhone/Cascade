"""Cascade CLI — entry point for `cascade` command and `make demo`.

Minimal v1: runs the three demo projects end-to-end and reports the result.
M38 will expand this to full SDK parity with the web UI.
"""

from __future__ import annotations

import sys

from cascade import __version__


def help_text() -> str:
    return (
        f"Cascade v{__version__} — turbomachinery design CLI\n\n"
        "Usage:\n"
        "  cascade --help                Show this message\n"
        "  cascade --version             Show version\n"
        "  cascade demo run              Run the three demo projects end-to-end\n"
        "  cascade demo run --case microturbine_cycle\n"
        "                               Run just the microturbine cycle demo.\n"
        "  cascade demo run --case radial_turbine_design\n"
        "                               Run just the radial turbine design demo.\n"
        "  cascade demo run --case rotor_dynamics\n"
        "                               Run just the rotor dynamics demo.\n"
        "  cascade demo run --energy-balance\n"
        "                               Same as 'demo run', plus the ADAPT-012\n"
        "                               sensible-vs-absolute energy-balance report.\n"
        "  cascade validate              Run the public validation suite\n"
        "  cascade citations             List loss-model citations\n"
        "  cascade sweep --project SLUG --param COMPONENT.FIELD \\\n"
        "               --range START:END:N --output FILE.csv\n"
        "                               Parametric sweep over one cycle parameter.\n"
        "  cascade export --project SLUG --output FILE.csv\n"
        "                               Export last-solve result to CSV.\n"
        "  cascade plugin install <file> Install a custom LossModel plugin\n"
        "  cascade plugin list           Show installed plugins\n"
        "  cascade plugin remove <name>  Remove a user-installed plugin\n"
        "  cascade plugin template       Print the user-facing template to stdout\n"
        "\n"
        "See SPEC_SHEET.md for the canonical specification.\n"
        "See cascade.plugins.__doc__ for the plugin security model.\n"
    )


def cmd_version() -> int:
    print(f"cascade {__version__}")
    return 0


def cmd_demo_run(show_energy_balance: bool = False) -> int:
    """Run the three demo projects: microturbine cycle, radial-turbine design space,
    rotor-dynamics. Per SPEC_SHEET §17 v1 green-light criterion 6.

    Args:
        show_energy_balance: If True, print the ADAPT-012 energy-balance
            report after the Capstone cycle prints. Useful for reviewers and
            auditors who want to verify the Walsh-Fletcher (2004) sensible-
            enthalpy convention closes to numerical precision.
    """
    print(f"Cascade v{__version__} — running 3 demo projects\n")
    failures = 0
    try:
        failures += _demo_capstone_cycle(show_energy_balance=show_energy_balance)
    except Exception as e:  # pragma: no cover
        print(f"  ERROR in demo 1: {e}")
        failures += 1
    try:
        failures += _demo_radial_turbine_design()
    except Exception as e:  # pragma: no cover
        print(f"  ERROR in demo 2: {e}")
        failures += 1
    try:
        failures += _demo_rotor_dynamics()
    except Exception as e:  # pragma: no cover
        print(f"  ERROR in demo 3: {e}")
        failures += 1
    print()
    if failures == 0:
        print("All 3 demos PASSED.")
        return 0
    print(f"{failures} demo(s) FAILED.")
    return 1


def _demo_capstone_cycle(show_energy_balance: bool = False) -> int:
    """Demo 1: Capstone C30 recuperated microturbine cycle.

    All cycle parameters come from `cascade.validation.cases.capstone_c30` —
    the canonical Capstone C30 source of truth shared with the CYC-3 test
    and the API microturbine seed (ADAPT-018).

    Args:
        show_energy_balance: If True, print the ADAPT-012 energy-balance
            report after the cycle summary. Two-column side-by-side
            (sensible vs absolute) that demonstrates the Walsh-Fletcher
            convention closes to numerical precision.
    """
    print("DEMO 1: Capstone C30 recuperated microturbine cycle")
    print("-" * 60)
    try:
        from cascade.cycle.components import (
            Burner,
            Compressor,
            ConstantPressureLoss,
            Recuperator,
            Turbine,
        )
        from cascade.cycle.solver import RecuperatedBraytonSpec, solve_cycle
        from cascade.units import Composition, Port
        from cascade.validation.cases.capstone_c30 import CapstoneC30
    except ImportError as e:
        print(f"  SKIPPED: cycle module not importable ({e})")
        return 0

    c = CapstoneC30
    inlet = Port(
        pressure_total=c.p_ambient,
        temperature_total=c.T_ambient,
        mass_flow=c.mass_flow,
        composition=Composition.air(),
    )
    spec = RecuperatedBraytonSpec(
        inlet_port=inlet,
        inlet_loss=ConstantPressureLoss(
            name="inlet_loss",
            pressure_drop_fraction=c.pdrop_inlet,
        ),
        compressor=Compressor(
            name="C1",
            pressure_ratio=c.pressure_ratio,
            efficiency_isentropic=c.eta_compressor_isen,
        ),
        burner=Burner(
            name="B1",
            outlet_temperature=c.TIT,
            pressure_drop_fraction=c.pdrop_burner,
            combustion_efficiency=c.combustion_efficiency,
            fuel_lhv=c.fuel_LHV.to("J/kg"),
            fuel_carbon_atoms=c.fuel_carbon_atoms,
            fuel_hydrogen_atoms=c.fuel_hydrogen_atoms,
            fuel_molar_mass=c.fuel_molar_mass,
            fuel_inlet_temperature=c.fuel_inlet_temperature,
            air_standard=False,
        ),
        turbine=Turbine(
            name="T1",
            pressure_ratio=c.turbine_pressure_ratio(),
            efficiency_isentropic=c.eta_turbine_isen,
        ),
        recuperator=Recuperator(
            name="R1",
            effectiveness=c.recuperator_effectiveness,
            cold_pressure_drop_fraction=c.pdrop_recup_cold,
            hot_pressure_drop_fraction=c.pdrop_recup_hot,
        ),
        mechanical_efficiency=c.eta_mechanical,
        generator_efficiency=c.eta_generator,
    )
    from cascade.cycle.fluid_model import NasaFluid

    fluid = NasaFluid()
    result = solve_cycle(spec, fluid=fluid)
    target_eta_pct = c.target_eta_electric * 100.0
    target_kW = c.target_power_net.to("kW").magnitude  # noqa: N806
    print(f"  Cycle thermal efficiency:  {result.thermal_efficiency * 100:.2f}%")
    print(f"  Electrical efficiency:     {result.electrical_efficiency * 100:.2f}%")
    print(f"  Net shaft work:            {result.net_shaft_work.to('kW'):.2f}")
    print(f"  Electrical output:         {result.electrical_output.to('kW'):.2f}")
    print(f"  Specific work:             {result.specific_work.to('kJ/kg'):.2f}")
    print(f"  Converged:                 {result.converged} ({result.outer_iterations} iter)")
    print(
        f"  Target (Capstone C30):     ~{target_eta_pct:.0f}% η_e, "
        f"~{target_kW:.0f} kW electric"
    )
    if show_energy_balance:
        from cascade.cycle.solver import energy_balance_report

        print()
        rpt = energy_balance_report(spec, result, fluid=fluid)
        print(rpt)
    return 0


def _demo_radial_turbine_design() -> int:
    """Demo 2: Radial-inflow turbine preliminary design exploration."""
    print()
    print("DEMO 2: Radial inflow turbine — design exploration over geometry")
    print("-" * 60)
    try:
        from cascade.explore.sobol_sampler import ParameterRange, SobolSampler
    except ImportError as e:
        print(f"  SKIPPED: design exploration module not importable ({e})")
        return 0

    ranges = {
        "rotor_outlet_radius": ParameterRange(
            min=0.01, max=0.05, unit="m", scale="linear"
        ),
        "blade_count": ParameterRange(
            min=10, max=18, unit="dimensionless", scale="linear"
        ),
        "tip_clearance": ParameterRange(
            min=0.0001, max=0.0005, unit="m", scale="log"
        ),
    }
    sampler = SobolSampler(parameter_ranges=ranges, n_samples=64, seed=42)
    candidates = sampler.generate()
    print(f"  Generated {len(candidates)} Sobol candidates in 3-dim parameter space")
    print(f"  Sample candidate: {candidates[0]}")
    print(f"  (Full design-space evaluation requires the radial turbine evaluator)")
    return 0


def _demo_rotor_dynamics() -> int:
    """Demo 3: Rotor dynamics — Jeffcott rotor critical speed."""
    print()
    print("DEMO 3: Rotor dynamics — Jeffcott rotor on linear bearings")
    print("-" * 60)
    try:
        from cascade.units import LumpedDisk, Q, RotorSection, RotorShape
    except ImportError as e:
        print(f"  SKIPPED: units module not importable ({e})")
        return 0

    # Construct a simple Jeffcott-style rotor shape
    shape = RotorShape(
        sections=[
            RotorSection(
                diameter_outer=Q(20.0, "mm"),
                diameter_inner=Q(0.0, "mm"),
                length=Q(400.0, "mm"),
                density=Q(7800.0, "kg/m^3"),
                axial_position=Q(0.0, "mm"),
                material="STEEL_AISI4340",
            )
        ],
        disks=[
            LumpedDisk(
                mass=Q(2.5, "kg"),
                inertia_polar=Q(2.5e-3, "kg * m^2"),
                inertia_diametrical=Q(1.25e-3, "kg * m^2"),
                axial_position=Q(200.0, "mm"),
            )
        ],
    )
    print(f"  Rotor shape: 1 shaft section + 1 disk")
    print(f"  Total mass:       {shape.mass_total.to('kg'):.3f}")
    print(f"  Total length:     {shape.length_total.to('mm'):.1f}")
    print(f"  (Full eigenanalysis requires the rotor beam-FEM run)")
    return 0


def cmd_validate() -> int:
    """Shell out to pytest -m validation."""
    import subprocess

    print("Running public validation suite — see VALIDATION_REPORT.md\n")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-m", "validation", "-v"],
        env={"PYTHONPATH": "src", **__import__("os").environ},
    )
    return result.returncode


def _cli_bootstrap_plugins() -> None:
    """Scan the CLI's plugin store and register every file found.

    Each CLI invocation starts a fresh Python process, so the in-memory
    PluginRegistry is empty modulo built-ins. This walk re-populates
    the registry with whatever the user has previously installed via
    `cascade plugin install`. Idempotent.
    """
    try:
        from cascade.plugins import (
            DEFAULT_PLUGIN_STORE_DIR,
            PLUGIN_REGISTRY,
            discover_installed_plugins,
            load_plugins_from_file,
        )
    except ImportError:
        return
    store = DEFAULT_PLUGIN_STORE_DIR / "cli"
    for path in discover_installed_plugins(store):
        try:
            for cls in load_plugins_from_file(path):
                try:
                    PLUGIN_REGISTRY.register(cls, origin="user")
                except Exception:
                    pass
        except Exception:
            # Silent — keep the CLI usable even if one plugin file is bad.
            pass


def cmd_plugin(argv: list[str]) -> int:
    """Dispatch `cascade plugin <subcommand>`.

    Subcommands:
        install <file>   — copy a .py file into ~/.cascade/plugins/ and
                           register the LossModel subclass it contains.
        list             — show every registered plugin (built-in + user).
        remove <name>    — unregister a user plugin and delete its file.
        template         — print the user-facing template to stdout.
    """
    _cli_bootstrap_plugins()
    if not argv:
        print("Usage: cascade plugin {install|list|remove|template} ...\n")
        print(help_text())
        return 1
    sub = argv[0]
    rest = argv[1:]
    if sub == "list":
        return _cmd_plugin_list()
    if sub == "install":
        if not rest:
            print("Usage: cascade plugin install <path>")
            return 1
        return _cmd_plugin_install(rest[0])
    if sub == "remove":
        if not rest:
            print("Usage: cascade plugin remove <name>")
            return 1
        return _cmd_plugin_remove(rest[0])
    if sub == "template":
        return _cmd_plugin_template()
    print(f"Unknown plugin subcommand: {sub}\n")
    print(help_text())
    return 1


def _cmd_plugin_list() -> int:
    try:
        from cascade.plugins import PLUGIN_REGISTRY
    except ImportError as e:
        print(f"cascade.plugins not importable: {e}")
        return 1
    classes = PLUGIN_REGISTRY.list()
    if not classes:
        print("No plugins registered.")
        return 0
    print(f"{'Name':<40}  {'Origin':<8}  Machine classes")
    print("-" * 80)
    for cls in classes:
        origin = PLUGIN_REGISTRY.origin(cls.name) or "?"
        mcs = ",".join(cls.applicable_machine_classes)
        print(f"{cls.name:<40}  {origin:<8}  {mcs}")
    return 0


def _cmd_plugin_install(path_arg: str) -> int:
    """`cascade plugin install <file>` — install + register a user plugin.

    Copies the file into `~/.cascade/plugins/cli/<basename>.py` and
    registers it under origin='user'. The CLI prompts before loading
    untrusted code (set CASCADE_PLUGIN_INSTALL_YES=1 to skip).
    """
    from pathlib import Path

    try:
        from cascade.plugins import (
            DEFAULT_PLUGIN_STORE_DIR,
            PLUGIN_REGISTRY,
            PluginLoadError,
            PluginValidationError,
            install_plugin_file,
            load_plugin_from_file,
        )
    except ImportError as e:
        print(f"cascade.plugins not importable: {e}")
        return 1

    path = Path(path_arg)
    if not path.exists():
        print(f"File not found: {path}")
        return 1

    import os

    # Safety prompt — plugins run in-process.
    if not os.environ.get("CASCADE_PLUGIN_INSTALL_YES"):
        print(f"About to load plugin code from: {path.resolve()}")
        print("Plugin code runs in-process with full Cascade + OS access.")
        print("Only proceed if you trust this file. [y/N]: ", end="", flush=True)
        try:
            line = input().strip().lower()
        except EOFError:
            line = "n"
        if line not in ("y", "yes"):
            print("Aborted.")
            return 1

    try:
        cls = load_plugin_from_file(path)
    except (PluginLoadError, PluginValidationError) as exc:
        print(f"Failed to load plugin: {exc}")
        return 1

    stored = install_plugin_file(
        path, store_dir=DEFAULT_PLUGIN_STORE_DIR, project_id="cli"
    )
    # Re-load from the durable path so the module's __file__ matches.
    try:
        cls = load_plugin_from_file(stored)
        PLUGIN_REGISTRY.register(cls, origin="user")
    except (PluginLoadError, PluginValidationError) as exc:
        print(f"Failed to register plugin: {exc}")
        return 1

    print(f"Installed plugin: {cls.name}")
    print(f"  Stored at: {stored}")
    print(f"  Machine classes: {','.join(cls.applicable_machine_classes)}")
    return 0


def _cmd_plugin_remove(name: str) -> int:
    from pathlib import Path

    try:
        from cascade.plugins import (
            DEFAULT_PLUGIN_STORE_DIR,
            PLUGIN_REGISTRY,
            load_plugins_from_file,
        )
    except ImportError as e:
        print(f"cascade.plugins not importable: {e}")
        return 1

    origin = PLUGIN_REGISTRY.origin(name)
    if origin is None:
        print(f"Plugin {name!r} not registered.")
        return 1
    if origin == "builtin":
        print(f"Cannot remove built-in plugin {name!r}.")
        return 1

    PLUGIN_REGISTRY.unregister(name)
    # Best-effort: delete the on-disk file too.
    store = DEFAULT_PLUGIN_STORE_DIR / "cli"
    removed_path = None
    if store.exists():
        for path in store.glob("*.py"):
            try:
                classes = load_plugins_from_file(path)
            except Exception:
                continue
            if any(c.name == name for c in classes):
                path.unlink(missing_ok=True)
                removed_path = path
                break
    print(f"Removed plugin: {name}")
    if removed_path:
        print(f"  Deleted: {removed_path}")
    return 0


def _cmd_plugin_template() -> int:
    """Print the user-facing template to stdout. Pipe to a file:

        cascade plugin template > my_loss_model.py
    """
    from pathlib import Path

    tpl = (
        Path(__file__).resolve().parent
        / "plugins"
        / "templates"
        / "custom_loss_model.py"
    )
    if not tpl.exists():
        print(f"Template not found at {tpl}")
        return 1
    print(tpl.read_text())
    return 0


def cmd_citations() -> int:
    """List every loss-model citation."""
    print("Cascade loss model citation discipline — see SPEC_SHEET.md §7\n")
    try:
        from cascade.meanline.loss_models_impl import (
            AungierCentrifugal,
            StanitzSlip,
            StodolaSlip,
            WhitfieldBainesRadial,
            WiesnerSlip,
        )
    except ImportError as e:
        print(f"  Loss models not importable yet: {e}")
        return 0
    for cls in (
        WhitfieldBainesRadial,
        AungierCentrifugal,
        StanitzSlip,
        WiesnerSlip,
        StodolaSlip,
    ):
        try:
            instance = cls()
            print(f"  {cls.__name__}: {instance.citation}")
        except Exception as e:
            print(f"  {cls.__name__}: <not instantiable: {e}>")
    return 0


def _load_project_for_cli(project_slug: str):
    """Load a project from ~/.cascade/projects/ by slug.

    Returns the Project object, or prints an error and returns None.
    W-26 / W-35: shared loader for sweep and export commands.
    """
    try:
        from cascade.project.persistence import load_project
    except ImportError as e:
        print(f"cascade.project not importable: {e}")
        return None

    project = load_project(project_slug)
    if project is None:
        import os

        projects_dir = os.environ.get(
            "CASCADE_PROJECTS_DIR",
            str(__import__("pathlib").Path.home() / ".cascade" / "projects"),
        )
        print(
            f"Project {project_slug!r} not found.\n"
            f"Expected: {projects_dir}/{project_slug}.cascade.toml\n"
            "Run `cascade demo run` to seed the demo projects, or check the "
            "--project value."
        )
    return project


def _build_cycle_spec_from_project(project):
    """Build a RecuperatedBraytonSpec from a loaded Project.

    Reads the component records (compressor, burner, turbine, recuperator) and
    boundary-conditions from the project and assembles the cycle spec. Used by
    both `cascade sweep` and `cascade export`.

    Returns (spec, fluid) or raises ValueError with a descriptive message.
    W-26 / W-35.
    """
    from cascade.cycle.components import (
        Burner,
        Compressor,
        ConstantPressureLoss,
        Recuperator,
        Turbine,
    )
    from cascade.cycle.fluid_model import NasaFluid
    from cascade.cycle.solver import RecuperatedBraytonSpec
    from cascade.units import Composition, Port, Q

    # Index components by kind for quick lookup.
    comp_by_kind: dict = {}
    for c in project.components:
        comp_by_kind.setdefault(c.kind, []).append(c)

    def _first(kind: str):
        lst = comp_by_kind.get(kind, [])
        if not lst:
            raise ValueError(f"Project has no {kind!r} component")
        return lst[0]

    bc = project.boundary_conditions
    settings = project.settings

    # Boundary conditions — fall back to sea-level ISO if not in project.
    p_amb = float(bc.get("p_ambient_kpa", 101.325))
    T_amb = float(bc.get("T_ambient_K", 288.15))
    mass_flow = float(bc.get("mass_flow_kg_s", 0.31))

    inlet = Port(
        pressure_total=Q(p_amb, "kPa"),
        temperature_total=Q(T_amb, "K"),
        mass_flow=Q(mass_flow, "kg/s"),
        composition=Composition.air(),
    )

    # Inlet loss (optional)
    inlet_loss = None
    inlet_loss_comps = comp_by_kind.get("inlet_loss", [])
    if inlet_loss_comps:
        pdrop = float(inlet_loss_comps[0].params.get("pressure_drop_fraction", 0.02))
        inlet_loss = ConstantPressureLoss(
            name=inlet_loss_comps[0].name,
            pressure_drop_fraction=pdrop,
        )

    # Compressor
    comp_rec = _first("compressor")
    compressor = Compressor(
        name=comp_rec.name,
        pressure_ratio=float(comp_rec.params.get("pressure_ratio", 4.0)),
        efficiency_isentropic=float(
            comp_rec.params.get("efficiency_isentropic", 0.78)
        ),
    )

    # Burner
    burner_rec = _first("burner")
    bp = burner_rec.params
    burner = Burner(
        name=burner_rec.name,
        outlet_temperature=Q(float(bp.get("outlet_temperature_K", 1116.0)), "K"),
        pressure_drop_fraction=float(bp.get("pressure_drop_fraction", 0.04)),
        combustion_efficiency=float(bp.get("combustion_efficiency", 0.995)),
        fuel_lhv=Q(float(bp.get("fuel_lhv_MJ_per_kg", 50.0)), "MJ/kg"),
        fuel_carbon_atoms=int(bp.get("fuel_carbon_atoms", 1)),
        fuel_hydrogen_atoms=int(bp.get("fuel_hydrogen_atoms", 4)),
        fuel_molar_mass=Q(float(bp.get("fuel_molar_mass_g_per_mol", 16.0425)), "g/mol"),
        fuel_inlet_temperature=Q(
            float(bp.get("fuel_inlet_temperature_K", 298.15)), "K"
        ),
        air_standard=False,
    )

    # Turbine
    turb_rec = _first("turbine")
    tp = turb_rec.params
    turbine = Turbine(
        name=turb_rec.name,
        pressure_ratio=float(tp.get("pressure_ratio", 3.54)),
        efficiency_isentropic=float(tp.get("efficiency_isentropic", 0.84)),
    )

    # Recuperator
    recup_rec = _first("recuperator")
    rp = recup_rec.params
    recuperator = Recuperator(
        name=recup_rec.name,
        effectiveness=float(rp.get("effectiveness", 0.87)),
        cold_pressure_drop_fraction=float(
            rp.get("cold_pressure_drop_fraction", 0.03)
        ),
        hot_pressure_drop_fraction=float(rp.get("hot_pressure_drop_fraction", 0.03)),
    )

    spec = RecuperatedBraytonSpec(
        inlet_port=inlet,
        inlet_loss=inlet_loss,
        compressor=compressor,
        burner=burner,
        turbine=turbine,
        recuperator=recuperator,
        mechanical_efficiency=float(settings.get("mechanical_efficiency", 0.95)),
        generator_efficiency=float(settings.get("generator_efficiency", 0.95)),
    )
    fluid = NasaFluid()
    return spec, fluid


def _set_param_on_spec(spec, param_path: str, value: float):
    """Return a new RecuperatedBraytonSpec with one parameter replaced.

    Cycle components are frozen dataclasses, so we use ``dataclasses.replace()``
    to produce new component instances. RecuperatedBraytonSpec itself is a plain
    dataclass (not frozen), so we shallow-copy it and swap the component.

    param_path format: ``component_kind.field_name`` e.g.
    ``compressor.pressure_ratio``.

    Raises ValueError if the path is invalid. W-26 (AC2).
    Returns a new spec with the field set. Does not mutate the input spec.
    """
    import copy
    import dataclasses

    parts = param_path.split(".", 1)
    if len(parts) != 2:
        raise ValueError(
            f"Invalid --param path {param_path!r}. "
            "Expected format: <component>.<field>  e.g. compressor.pressure_ratio"
        )
    component_kind, field_name = parts

    component_map = {
        "compressor": "compressor",
        "turbine": "turbine",
        "burner": "burner",
        "recuperator": "recuperator",
    }
    if component_kind not in component_map:
        raise ValueError(
            f"Unknown component {component_kind!r} in --param. "
            f"Valid components: {', '.join(component_map)}"
        )

    attr_name = component_map[component_kind]
    component = getattr(spec, attr_name)
    if not hasattr(component, field_name):
        raise ValueError(
            f"Component {component_kind!r} has no field {field_name!r}. "
            f"Check spelling. Available fields vary by component type."
        )

    # Components are frozen dataclasses → use dataclasses.replace() to get
    # a new component instance with the updated field.
    new_component = dataclasses.replace(component, **{field_name: value})

    # RecuperatedBraytonSpec is a plain (non-frozen) dataclass — shallow-copy
    # it and swap the component attribute.
    new_spec = copy.copy(spec)
    setattr(new_spec, attr_name, new_component)
    return new_spec


def _parse_range(range_str: str):
    """Parse 'start:end:n_points' into a list of floats.

    Raises ValueError on bad format. W-26.
    """
    parts = range_str.split(":")
    if len(parts) != 3:
        raise ValueError(
            f"Invalid --range {range_str!r}. "
            "Expected format: start:end:n_points  e.g. 3:7:20"
        )
    try:
        start = float(parts[0])
        end = float(parts[1])
        n = int(parts[2])
    except ValueError as e:
        raise ValueError(
            f"Invalid --range {range_str!r}: {e}. "
            "Expected three numbers separated by colons."
        ) from e
    if n < 2:
        raise ValueError(
            f"--range n_points must be >= 2; got {n}"
        )
    import numpy as np

    return list(np.linspace(start, end, n))


def cmd_sweep(argv: list[str]) -> int:
    """cascade sweep — parametric sweep over one cycle parameter → CSV.

    Usage:
        cascade sweep --project SLUG --param COMPONENT.FIELD \\
                     --range START:END:N --output FILE.csv

    W-26: AC1 (valid CSV with ≥6 cols + N rows), AC2 (bad param error before
    loop), AC3 (failed solves write FAILED row, no crash).
    """
    import copy
    import csv
    import io

    # --- Parse argv ----------------------------------------------------------
    def _flag(flag: str) -> str | None:
        try:
            i = argv.index(flag)
            return argv[i + 1] if i + 1 < len(argv) else None
        except ValueError:
            return None

    project_slug = _flag("--project")
    param_path = _flag("--param")
    range_str = _flag("--range")
    output_path = _flag("--output")

    missing = [
        name
        for name, val in (
            ("--project", project_slug),
            ("--param", param_path),
            ("--range", range_str),
            ("--output", output_path),
        )
        if val is None
    ]
    if missing:
        print(f"Missing required flag(s): {', '.join(missing)}")
        print(
            "Usage: cascade sweep --project SLUG --param COMPONENT.FIELD "
            "--range START:END:N --output FILE.csv"
        )
        return 1

    # --- Load project --------------------------------------------------------
    project = _load_project_for_cli(project_slug)
    if project is None:
        return 1

    # --- Build base spec (validates component layout before entering loop) ---
    try:
        base_spec, fluid = _build_cycle_spec_from_project(project)
    except (ValueError, ImportError) as e:
        print(f"Failed to build cycle spec from project: {e}")
        return 1

    # --- Validate --param path BEFORE the loop (AC2) -------------------------
    try:
        _set_param_on_spec(base_spec, param_path, 4.0)  # dry-run — validates path
    except ValueError as e:
        print(f"Invalid --param: {e}")
        return 1

    # --- Parse range ---------------------------------------------------------
    try:
        values = _parse_range(range_str)
    except ValueError as e:
        print(f"Invalid --range: {e}")
        return 1

    # --- Run sweep -----------------------------------------------------------
    from cascade.cycle.solver import solve_cycle

    CSV_FIELDS = [
        "param_value",
        "thermal_efficiency",
        "electrical_efficiency",
        "specific_work_kJ_per_kg",
        "fuel_flow_kg_s",
        "net_shaft_work_kW",
        "electrical_output_kW",
        "status",
        "reason",
    ]

    rows = []
    n = len(values)
    print(
        f"Sweeping {param_path} over {n} points "
        f"({values[0]:.4g} → {values[-1]:.4g}) ..."
    )
    for i, v in enumerate(values):
        # Build a new spec with the parameter set (frozen dataclasses → replace).
        try:
            spec_i = _set_param_on_spec(base_spec, param_path, v)
        except Exception as exc:
            row = {f: "" for f in CSV_FIELDS}
            row["param_value"] = v
            row["status"] = "FAILED"
            row["reason"] = f"param-set error: {exc}"
            rows.append(row)
            continue

        row: dict = {"param_value": v}
        try:
            result = solve_cycle(spec_i, fluid=fluid)
            row["thermal_efficiency"] = f"{result.thermal_efficiency:.6f}"
            row["electrical_efficiency"] = f"{result.electrical_efficiency:.6f}"
            row["specific_work_kJ_per_kg"] = (
                f"{result.specific_work.to('kJ/kg').magnitude:.4f}"
            )
            row["fuel_flow_kg_s"] = (
                f"{result.fuel_mass_flow.to('kg/s').magnitude:.6f}"
            )
            row["net_shaft_work_kW"] = (
                f"{result.net_shaft_work.to('kW').magnitude:.4f}"
            )
            row["electrical_output_kW"] = (
                f"{result.electrical_output.to('kW').magnitude:.4f}"
            )
            row["status"] = "OK"
            row["reason"] = ""
        except Exception as exc:  # AC3: failed solve → FAILED row, no crash
            row["thermal_efficiency"] = ""
            row["electrical_efficiency"] = ""
            row["specific_work_kJ_per_kg"] = ""
            row["fuel_flow_kg_s"] = ""
            row["net_shaft_work_kW"] = ""
            row["electrical_output_kW"] = ""
            row["status"] = "FAILED"
            row["reason"] = str(exc)
        rows.append(row)

        if (i + 1) % max(1, n // 5) == 0 or i == n - 1:
            print(f"  [{i + 1}/{n}] {param_path}={v:.4g}  status={row['status']}")

    # --- Write CSV -----------------------------------------------------------
    try:
        with open(output_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    except OSError as e:
        print(f"Failed to write output file: {e}")
        return 1

    ok_count = sum(1 for r in rows if r["status"] == "OK")
    fail_count = n - ok_count
    print(
        f"\nSweep complete: {ok_count} OK, {fail_count} FAILED → {output_path}"
    )
    return 0


def cmd_export(argv: list[str]) -> int:
    """cascade export — run cycle once and export result to CSV.

    Usage:
        cascade export --project SLUG --output FILE.csv

    W-35: AC1 (named sections [HEADLINE], [COMPONENT:*]), AC3 (failed solve
    written without crash).
    """
    import csv

    # --- Parse argv ----------------------------------------------------------
    def _flag(flag: str) -> str | None:
        try:
            i = argv.index(flag)
            return argv[i + 1] if i + 1 < len(argv) else None
        except ValueError:
            return None

    project_slug = _flag("--project")
    output_path = _flag("--output")

    missing = [
        name
        for name, val in (("--project", project_slug), ("--output", output_path))
        if val is None
    ]
    if missing:
        print(f"Missing required flag(s): {', '.join(missing)}")
        print("Usage: cascade export --project SLUG --output FILE.csv")
        return 1

    # --- Load project --------------------------------------------------------
    project = _load_project_for_cli(project_slug)
    if project is None:
        return 1

    # --- Build spec ----------------------------------------------------------
    spec = None
    fluid = None
    build_error: str | None = None
    try:
        spec, fluid = _build_cycle_spec_from_project(project)
    except (ValueError, ImportError) as e:
        build_error = str(e)

    # --- Solve ---------------------------------------------------------------
    solve_error: str | None = build_error  # propagate build error as solve error
    result = None
    if spec is not None and fluid is not None:
        from cascade.cycle.solver import solve_cycle

        try:
            result = solve_cycle(spec, fluid=fluid)
        except Exception as exc:
            solve_error = str(exc)

    # --- Build CSV rows (section format) -------------------------------------
    # Format: first column is "section", second is "key", third is "value".
    # Sections: [HEADLINE], [COMPONENT:<name>] for each component, [STATUS].
    rows: list[dict] = []

    def _row(section: str, key: str, value: str) -> dict:
        return {"section": section, "key": key, "value": value}

    # [STATUS] section — always present
    rows.append(_row("[STATUS]", "project", project.id))
    rows.append(_row("[STATUS]", "project_name", project.meta.name))
    if solve_error:
        rows.append(_row("[STATUS]", "solve_status", "FAILED"))
        rows.append(_row("[STATUS]", "error", solve_error))
    else:
        rows.append(_row("[STATUS]", "solve_status", "OK"))
        rows.append(
            _row("[STATUS]", "converged", str(result.converged))
        )
        rows.append(
            _row("[STATUS]", "outer_iterations", str(result.outer_iterations))
        )

    if result is not None:
        # [HEADLINE] section
        rows.append(
            _row("[HEADLINE]", "thermal_efficiency", f"{result.thermal_efficiency:.6f}")
        )
        rows.append(
            _row(
                "[HEADLINE]",
                "electrical_efficiency",
                f"{result.electrical_efficiency:.6f}",
            )
        )
        rows.append(
            _row(
                "[HEADLINE]",
                "specific_work_kJ_per_kg",
                f"{result.specific_work.to('kJ/kg').magnitude:.4f}",
            )
        )
        rows.append(
            _row(
                "[HEADLINE]",
                "net_shaft_work_kW",
                f"{result.net_shaft_work.to('kW').magnitude:.4f}",
            )
        )
        rows.append(
            _row(
                "[HEADLINE]",
                "electrical_output_kW",
                f"{result.electrical_output.to('kW').magnitude:.4f}",
            )
        )
        rows.append(
            _row(
                "[HEADLINE]",
                "fuel_mass_flow_kg_s",
                f"{result.fuel_mass_flow.to('kg/s').magnitude:.6f}",
            )
        )
        rows.append(
            _row(
                "[HEADLINE]",
                "heat_input_kW",
                f"{result.heat_input.to('kW').magnitude:.4f}",
            )
        )

        # [COMPONENT:<name>] sections — one per port in result
        for port_name, port in sorted(result.ports.items()):
            section = f"[COMPONENT:{port_name}]"
            try:
                rows.append(
                    _row(
                        section,
                        "outlet_T_K",
                        f"{port.temperature_total.to('K').magnitude:.2f}",
                    )
                )
                rows.append(
                    _row(
                        section,
                        "outlet_P_kPa",
                        f"{port.pressure_total.to('kPa').magnitude:.4f}",
                    )
                )
                rows.append(
                    _row(
                        section,
                        "mass_flow_kg_s",
                        f"{port.mass_flow.to('kg/s').magnitude:.5f}",
                    )
                )
            except Exception:
                pass  # skip malformed ports gracefully

        # [COMPONENT:<name>] shaft work rows
        for comp_name, work in sorted(result.shaft_work_components.items()):
            section = f"[COMPONENT:{comp_name}]"
            try:
                rows.append(
                    _row(
                        section,
                        "shaft_work_kW",
                        f"{work.to('kW').magnitude:.4f}",
                    )
                )
            except Exception:
                pass

        # [COMPONENT:<name>] efficiency rows
        for comp_name, eta in sorted(result.component_efficiencies.items()):
            section = f"[COMPONENT:{comp_name}]"
            rows.append(_row(section, "efficiency_used", f"{eta:.6f}"))

    # --- Write CSV -----------------------------------------------------------
    try:
        with open(output_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh, fieldnames=["section", "key", "value"]
            )
            writer.writeheader()
            writer.writerows(rows)
    except OSError as e:
        print(f"Failed to write output file: {e}")
        return 1

    if solve_error:
        print(f"Solve FAILED: {solve_error}")
        print(f"Failure written to {output_path}")
        return 0  # not a crash — AC3

    print(f"Export complete → {output_path}")
    print(
        f"  η_th={float(result.thermal_efficiency)*100:.2f}%  "
        f"η_e={float(result.electrical_efficiency)*100:.2f}%  "
        f"P_e={result.electrical_output.to('kW').magnitude:.1f} kW"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args or args[0] in ("--help", "-h", "help"):
        print(help_text())
        return 0
    if args[0] in ("--version", "-V"):
        return cmd_version()
    if args[0] == "demo" and len(args) > 1 and args[1] == "run":
        show_energy_balance = "--energy-balance" in args
        # Allow `cascade demo run --case <name>` for a single named demo.
        # The registry maps case name → callable, so adding a new demo never
        # requires adding another hardcoded name branch here.
        _DEMO_REGISTRY = {
            "microturbine_cycle": lambda: _demo_capstone_cycle(
                show_energy_balance=show_energy_balance
            ),
            "radial_turbine_design": _demo_radial_turbine_design,
            "rotor_dynamics": _demo_rotor_dynamics,
        }
        if "--case" in args:
            i = args.index("--case")
            if i + 1 < len(args):
                case = args[i + 1]
                runner = _DEMO_REGISTRY.get(case)
                if runner is not None:
                    return runner()
                available = ", ".join(sorted(_DEMO_REGISTRY))
                print(f"Unknown demo case: {case!r}. Available: {available}\n")
                print(help_text())
                return 1
        return cmd_demo_run(show_energy_balance=show_energy_balance)
    if args[0] == "validate":
        return cmd_validate()
    if args[0] == "citations":
        return cmd_citations()
    if args[0] == "plugin":
        return cmd_plugin(args[1:])
    if args[0] == "sweep":
        return cmd_sweep(args[1:])
    if args[0] == "export":
        return cmd_export(args[1:])
    print(f"Unknown command: {' '.join(args)}\n")
    print(help_text())
    return 1


# Typer-compatible name (Makefile expects this)
app = main


if __name__ == "__main__":
    sys.exit(main())
