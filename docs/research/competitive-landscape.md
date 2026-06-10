# Turbomachinery Design Software — Competitive Landscape

Compiled June 2026 for the Cascade project. Audience: anyone deciding what a
small-turbine design tool must do to be taken seriously, and where the
existing market leaves room for an open-source, web-native entrant.

Scope: software used to design and analyze small gas turbines — microturbines,
small industrial turbines, turbogenerators, APUs, and the adjacent ORC/sCO2
machines that share the same radial turbomachinery architecture.

Method and sourcing rules: every load-bearing claim carries a public source.
Pricing is quoted only where publicly reported, always dated and hedged —
vendor pricing in this market is quote-driven and volatile. Severity of each
weakness is judged against one persona: a small engineering team developing a
natural-gas microturbine, without a CAE budget or a dedicated IT department.

---

## 1. Commercial suites

### 1.1 SoftInWay AxSTREAM

**What it is.** The closest commercial analog to Cascade's scope: an
integrated platform spanning 0D/1D cycle and thermal-fluid simulation
(AxSTREAM System Simulation, which merged the legacy AxCYCLE and AxSTREAM NET
in 2023), mean-line and streamline flow-path design, blade profiling,
performance maps (AxMAP), CFD (AxCFD), FEA (AxSTRESS), rotor dynamics and
bearings, reverse engineering (AxSLICE), and a workflow-automation graph
(AxSTREAM ION). The company self-reports more than 70 modules
([Power Tokens press release](https://www.softinway.com/softinway-launches-groundbreaking-power-tokens-licensing-program-for-axstream-software/)).
Founded 1999; AxSTREAM launched 2005; ~750 client companies self-reported
([SoftInWay](https://www.softinway.com/)).

**What makes it good.**
- Breadth: one vendor covers cycle → flow path → maps → rotor dynamics → CFD/FEA.
- Deep radial and axial machine coverage across turbines, compressors, pumps, fans.
- Active development: AxSTREAM Twin (2025, restricted project sharing) and
  AxSTREAM AI (announced January 2026, workflow-aware assistant) per
  [SoftInWay's announcements](https://www.softinway.com/softinway-introduces-axstream-ai-to-accelerate-engineering-decisions-with-workflow-aware-intelligence/).
- Engineering-services arm that can take on whole machine programs.

**What users run into.**
- Desktop-only, Windows-centric; no browser access, no real-time collaboration.
  AxSTREAM Twin shares restricted *copies*, not a live model
  ([Twin press release](https://www.softinway.com/softinway-launches-axstream-twin-to-enable-secure-collaborative-engineering-and-simulation-sharing/)).
- Quote-only pricing; no published list prices anywhere.
- Module-by-module licensing across 70+ modules makes the entry path hard to
  evaluate for a small team.
- Binary project files; reproducibility and diff-based review are not part of
  the workflow model.

**Licensing signal.** In November 2024 SoftInWay introduced "Power Tokens" —
a consumption-token pool allocated across modules, marketed as "up to 60%
savings" versus traditional licensing
([press release](https://www.softinway.com/softinway-launches-groundbreaking-power-tokens-licensing-program-for-axstream-software/)).
No dollar amounts are published. The move itself is the signal: the
traditional per-seat model is under pressure from smaller buyers.

### 1.2 Concepts NREC — Agile Engineering Design System

**What it is.** The most vertically integrated suite in the market: 1D
mean-line design wizards per machine type (COMPAL centrifugal compressors,
RITAL radial turbines, AXIAL, FANPAL, PUMPAL), CYCAL cycle analysis, AxCent
3D blade design and streamline-curvature analysis, pbCFD, TurboOPT II
optimization, ARMD rotor dynamics — and, uniquely, MAX-PAC 5-axis CNC
tool-path generation ([Concepts NREC](https://www.conceptsnrec.com/design-software-solutions)).
A 2025 "Fidelity" release unified several modules under one interface
([Turbomachinery Magazine](https://www.turbomachinerymag.com/view/concepts-nrec-releases-new-cae-and-cam-software)).

**What makes it good.**
- True design-through-manufacturing chain: mean-line geometry flows to 3D
  blade design, CFD, and directly to 5-axis machining.
- Citable loss-model lineage (Aungier and related literature appear by name
  in their materials).
- Deep application notes for ORC, sCO2, turbochargers, turbopumps, APUs —
  exactly the small-machine space.

**What users run into.**
- Quote-only pricing; annual or perpetual licenses with a separate support
  subscription. No published prices.
- No public user reviews on any aggregator — the buyer pool is small and
  enterprise-shaped.
- Windows desktop; no web access or collaboration model.

### 1.3 Ansys turbomachinery toolchain

**What it is.** The incumbent ecosystem rather than a single product: Vista
CCD/RTD (preliminary centrifugal/radial design), Vista TF (throughflow),
BladeModeler (3D blade geometry), TurboGrid (blade-passage meshing), CFX
(the historically dominant turbomachinery CFD solver), all integrated through
Workbench ([Ansys TurboGrid](https://www.ansys.com/products/fluids/ansys-turbogrid),
[BladeModeler](https://www.ansys.com/products/fluids/ansys-blademodeler)).

**What makes it good.**
- CFX remains the reference solver in turbomachinery CFD validation
  literature; TurboGrid's automated blade-passage topologies are a real
  labor saver.
- The de-facto standard handoff target: every competing design tool
  advertises TurboGrid/geomTurbo compatibility.

**What users run into.**
- Cost. A reseller-published price guide reported CFD Premium at roughly
  $58,000 per 4-core seat plus ~$12,000 annual maintenance, and CFD
  Enterprise around $65,000 plus $13,000, as of its 2024 snapshot
  ([Ozen Engineering pricing blog](https://blog.ozeninc.com/industry-applications/ansys-pricing)).
  Treat the numbers as indicative, not current quotes — but the order of
  magnitude is the point: a small team cannot casually own this stack.
- The preliminary-design pieces (Vista) only pay off if you also own the
  meshing and CFD layers.
- Desktop licensing, license servers, enterprise sales motion.

### 1.4 CFturbo

**What it is.** A parametric geometry-first design tool for pumps, fans,
compressors, and turbines — the "CAD front-end" of the market. Its strength
is generating clean, watertight turbomachinery geometry for downstream CFD,
with named interfaces to TurboGrid, AutoGrid, STAR-CCM+, OpenFOAM, SimScale,
and every major CAD package
([CFturbo interfaces](https://cfturbo.com/software/interfaces-workflows)).

**Strengths:** broadest integration story in the market; step-by-step design
wizard praised for accessibility; free trial.
**Limits for this persona:** it is not a performance-prediction or cycle
tool — you still need everything else; pricing is contact-vendor.

### 1.5 ADT TURBOdesign Suite

**What it is.** A niche built on one differentiated idea: inverse design —
specify the blade-loading distribution, compute the geometry that achieves it
([ADT](https://www.adtechnology.com/)). Active releases through 2025 added a
response-surface surrogate and a Python API
([release notes](https://blog.adtechnology.com/turbodesign-suite-release-2025.2)).
Reference customers include Grundfos, Daikin, and Cummins (per ADT's site).

**Limits for this persona:** no cycle analysis or rotor dynamics; conceptual
learning curve; quote-only pricing.

### 1.6 Cycle and system tools

| Tool | What it is | Signal for small NG turbines |
|---|---|---|
| **GasTurb** | The practical standard for gas-turbine cycle analysis; 27+ engine configurations, off-design with component maps ([gasturb.com](https://www.gasturb.com/)) | Excellent at cycles, but node-locked desktop licensing and no aerodynamic design capability. Single-author heritage is institutional risk. |
| **GSP (NLR)** | Free drag-and-drop gas-turbine performance simulation ([gspteam.com](https://www.gspteam.com)) | Free and capable for cycle studies; not a design tool, thinner documentation. |
| **NPSS (NASA/SwRI)** | US aerospace's dominant propulsion cycle environment; commercial licenses via SwRI ([SwRI](https://www.swri.org/markets/electronics-automation/software/aerospace-software/numerical-propulsion-system-simulation-npss)) | Steep learning curve, consortium pricing; rare outside large aerospace. |
| **Thermoflow GT PRO** | Combined-cycle / cogeneration plant design with an 860+ engine database ([thermoflow.com](https://www.thermoflow.com/products_gasturbine.html)) | Plant-level, not machine-level; hardware-dongle licensing ([licensing page](https://www.thermoflow.com/licensing.html)). |
| **EcosimPro / PROOSIS** | 1D gas-turbine transient simulation, SAE-standard model exchange ([ecosimpro.com](https://ecosimpro.com/products/turbo/)) | Aerospace-first; industrial small turbines are a secondary market. |

### 1.7 Web-native CAE (the adjacent precedent)

**SimScale** is the proof that browser-based CAE works commercially: free
community tier, consumption-based compute, turbomachinery CFD as a featured
application, and a published CFturbo integration
([SimScale blog](https://www.simscale.com/blog/turbomachinery-modeling-with-simscale-and-cfturbo/),
[pricing](https://www.simscale.com/product/pricing/)). It does CFD only — no
mean-line design, no cycle analysis, no rotor dynamics. No vendor offers a
web-native turbomachinery *design* environment today.

---

## 2. Open-source and academic landscape

| Capability | Best available option | Gap |
|---|---|---|
| Axial turbine mean-line | **TurboFlow** (MIT license, Python, [JOSS 2025](https://joss.theoj.org/papers/10.21105/joss.07588); validates mass flow ±2.5%, angles ±5° on three published rigs) | Axial turbines only — no radial machines, no compressor, no cycle, no rotor dynamics |
| Full design system | **MULTALL/MEANGEN/STAGEN** (Denton, open-sourced; [ASME 2017](https://asmedigitalcollection.asme.org/turbomachinery/article-abstract/139/12/121001/378803)) | Fortran, axial-focused, no GUI, no maps, no rotor dynamics |
| Cycle analysis | **pyCycle** (NASA, [GitHub](https://github.com/OpenMDAO/pyCycle)) | Jet-engine cycles; documentation self-described as minimal |
| 3D CFD | **SU2** (turbomachinery extensions validated, [ASME 2024](https://asmedigitalcollection.asme.org/turbomachinery/article-abstract/146/6/061003/1193573/)) | High-fidelity analysis, not design; needs external geometry/meshing |
| 2D cascade analysis | **MISES** (MIT; $10,000 commercial license, free academic — [MIT TLO](https://tlo.mit.edu/technologies/mises-software-design-and-analysis-turbomachinery-blading)) | 2D blade sections only; not free for commercial use |
| Parametric geometry | **CAESES** ($2,000/yr published flat rate — [Capterra](https://www.capterra.com/p/177131/CAESES/)) | Geometry engine, not a design tool; commercial |
| Rotor dynamics | none suitable | No maintained open-source lateral/torsional rotor-dynamics tool with bearing solvers exists |

The takeaway: open source covers fragments — an axial mean-line here, a CFD
solver there — but no project combines cycle analysis, radial mean-line
design, performance maps, and rotor dynamics, and none of them has a usable
web interface. Radial inflow turbine and centrifugal compressor mean-line
design — the exact architecture of microturbines — has no credible
open-source option at all.

---

## 3. Table stakes — what any entrant must clear to be credible

1. **Validation against published test cases, with the cases named.**
   TurboFlow's ±2.5%/±5° standard against three published rigs shows what the
   community expects. Capability claims without reproducible validation are
   read as marketing.
2. **Citable loss models.** Engineers must be able to trace which
   Whitfield-Baines, Aungier, or Wiesner formulation produced a number, and
   defend it to a customer or a certification authority.
3. **API 617 / API 684 alignment for rotor dynamics.** For any machine sold
   into industrial service, lateral/torsional analysis terminology and
   acceptance criteria must map to the API standards
   ([API 684 overview](https://standards.globalspec.com/std/14225369/api-tr-684-1)).
4. **Standard geometry handoff.** STEP/IGES export plus
   TurboGrid/geomTurbo-compatible output — the "USB port" of turbomachinery
   CFD workflows.
5. **Real-gas equation of state.** Ideal-gas assumptions fail near the sCO2
   critical point and for ORC working fluids; CoolProp is the community
   standard backend, REFPROP the commercial reference.
6. **Performance-map conventions.** Corrected mass flow / corrected speed
   presentation consistent with SAE practice
   ([ARP5571](https://saemobilus.sae.org/standards/arp5571)), with explicit
   surge/choke labeling.
7. **Serious units handling.** SI and US customary, with conversion at the
   boundary and dimension checking inside.
8. **Honest failure modes.** Solvers must refuse outside validated regimes
   rather than extrapolate silently — practitioners distrust tools that
   always return a number.

Where Cascade stands today, honestly: items 1, 2, 5, 6, 7, and 8 are shipped
and publicly documented (`VALIDATION_REPORT.md`, the citations gate, the
refusal doctrine in `SPEC_SHEET.md` §13). Item 3 is partially shipped
(API 684 separation-margin and amplification-factor outputs in rotor
dynamics; full report alignment is roadmap work). Item 4 is partially shipped
(TurboGrid and point-cloud export shipped; STEP/IGES gated behind an optional
CAD dependency). Axial machines and the 1D thermal-fluid network are not
shipped (`KNOWN_GAPS.md` KG-AXT-01, KG-TFN-01) — see `ROADMAP.md`.

---

## 4. Cross-cutting pain points (the openings)

- **Cost and opacity.** Among all commercial vendors above, exactly one
  (CAESES, a geometry tool) publishes a price. Everything else is
  quote-only, and the public data points that exist put serious
  turbomachinery CAE in five figures per seat-year. For a microturbine
  startup, tooling cost is a structural barrier to entry.
- **Desktop, dongles, and license servers.** Thermoflow ships hardware
  dongles; GasTurb node-locks; the suites need license servers. Remote and
  distributed teams fight their tools.
- **No collaboration model.** No commercial turbomachinery design tool offers
  browser access or live multi-user work. File-based project formats make
  design review a screen-sharing exercise rather than a pull request.
- **Opaque methods.** Loss-model provenance and validation evidence are
  unevenly published. Tools that always produce a number, with no visible
  validity envelope, push the verification burden onto the user.
- **Fragmented small-machine workflows.** A small team today stitches
  GSP or GasTurb (cycle) + spreadsheet mean-line or a suite module (design)
  + separate rotor-dynamics consulting + CFD — with file-format friction at
  every seam.

These pain points map one-to-one onto Cascade's design choices: AGPL and
free to self-host, browser-native, text-based diffable projects, cited loss
models, published validation, and refusal over extrapolation.

---

## 5. Sources

All claims above are linked inline. Key references:

- SoftInWay product and licensing pages (AxSTREAM platform, Power Tokens,
  Twin, AxSTREAM AI announcements) — softinway.com
- Concepts NREC product pages and 2025 release coverage — conceptsnrec.com,
  turbomachinerymag.com
- Ansys product pages; Ozen Engineering pricing guide (2024 snapshot) —
  ansys.com, blog.ozeninc.com
- CFturbo interfaces documentation — cfturbo.com
- ADT TURBOdesign releases — adtechnology.com
- GasTurb, GSP, NPSS/SwRI, Thermoflow, EcosimPro licensing and product
  pages — gasturb.com, gspteam.com, swri.org, thermoflow.com, ecosimpro.com
- TurboFlow (JOSS 2025), MULTALL (ASME 2017), SU2 turbomachinery validation
  (ASME 2024), MISES (MIT TLO), pyCycle (GitHub), CAESES (Capterra)
- SimScale pricing and CFturbo integration — simscale.com
- SAE ARP5571; API TR 684 — saemobilus.sae.org, standards.globalspec.com
