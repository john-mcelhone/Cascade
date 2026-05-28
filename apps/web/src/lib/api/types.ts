/**
 * Public types for the Cascade web API. The mock client and the eventual real
 * client both conform to ApiClient. Domain naming is consistent across the API:
 *  - "candidate" (not "design" / "trial")
 *  - "regime" (not "validity envelope")
 *  - "converged" / "diverged"
 *  - "the run" (a discrete solver invocation)
 */

export type ProjectStatus = "design" | "converged" | "diverged" | "in-progress";

export type WorkingFluid = "air" | "co2" | "n2" | "h2" | "methane";

export interface Project {
  id: string;
  name: string;
  description: string;
  template: "microturbine" | "sco2-loop" | "radial-turbine" | "aero-axial" | "blank";
  status: ProjectStatus;
  createdAt: string;
  updatedAt: string;
  workingFluid: WorkingFluid;
  /** Headline metric for the project card sparkline. */
  headline: {
    label: string;
    value: number;
    unit: string;
  };
  /** Last-7-runs sparkline data. */
  sparkline: number[];
}

export type CycleNodeKind =
  | "inlet"
  | "outlet"
  | "compressor"
  | "turbine"
  | "burner"
  | "recuperator"
  | "intercooler"
  | "mixer"
  | "splitter"
  | "duct"
  | "shaft";

export interface CycleNode {
  id: string;
  kind: CycleNodeKind;
  label: string;
  x: number;
  y: number;
  /** Display-only parameter chips (e.g. PR for compressor). */
  chips: Array<{ symbol: string; value: string }>;
  /** Optional parameter bag for backend round-trip. */
  params?: Record<string, number | string | boolean>;
}

export interface CycleEdge {
  id: string;
  source: string;
  target: string;
  /** Optional port labels on each end. */
  sourcePort?: string;
  targetPort?: string;
}

export interface CycleStatePoint {
  /** Stage label, e.g. "1", "2", "3". */
  label: string;
  /** Temperature [K]. */
  temperature: number;
  /** Entropy [kJ/(kg·K)]. */
  entropy: number;
  /** Pressure [kPa]. */
  pressure?: number;
  /** Mass flow [kg/s]. */
  massFlow?: number;
}

export interface CycleComponentResult {
  componentId: string;
  /** Shaft work [kW] (signed: compressor < 0, turbine > 0). */
  shaftWork: number;
  /** Outlet stagnation T [K]. */
  outletTemperature: number;
  /** Outlet stagnation P [kPa]. */
  outletPressure: number;
  /** Outlet mass flow [kg/s]. */
  outletMassFlow: number;
}

/**
 * Structured failure payload from the cycle worker. When `failure` is
 * present on a CycleResult, the solver couldn't produce a valid answer.
 *
 *   - `kind: "design"` — the issue is with the user's design (a
 *     physically impossible PR, a degenerate efficiency, a missing
 *     component, etc). The UI surfaces this as a plain-English
 *     explanation + concrete suggestions to try.
 *   - `kind: "bug"` — an unexpected internal exception that doesn't
 *     correspond to a known physical impossibility. The UI surfaces
 *     this as a "this looks like a software bug, copy the log" panel.
 */
export interface CycleFailure {
  kind: "design" | "bug";
  /** Short headline shown in the result-panel header. */
  title: string;
  /** First-principles explanation in plain English. */
  plain_english: string;
  /** Concrete things the user can try, ranked most-likely-fix first. */
  suggestions: string[];
  /** Optional raw solver detail (small, safe to display). */
  details?: string;
  /** Full Python traceback. Only populated when `kind == "bug"`. */
  bug_log?: string;
}

export interface CycleResult {
  thermalEfficiency: number;
  electricalEfficiency: number;
  /** Specific work [kJ/kg]. */
  specificWork: number;
  /** Fuel mass flow [kg/s]. */
  fuelFlow: number;
  /** Net shaft work [kW]. */
  netShaftWork: number;
  /** Electrical output [kW]. */
  electricalOutput: number;
  /** Per-component breakdown. */
  components: CycleComponentResult[];
  /** Plotted cycle states for the T-s diagram (numbered). */
  states: CycleStatePoint[];
  /** Populated when the solver didn't converge or threw. */
  failure?: CycleFailure;
}

export interface CycleGraph {
  nodes: CycleNode[];
  edges: CycleEdge[];
  /** Most recent result of running the cycle, if any. */
  result?: CycleResult;
}

export interface Candidate {
  id: string;
  /** Free indexed handle into the exploration. */
  index: number;
  /** Pass / fail / regime violation. */
  status: "ok" | "regime-violation" | "invalid-geometry" | "diverged";
  /** Headline objectives. */
  eta_tt: number;
  eta_ts: number;
  max_m_rel: number;
  mass: number;
  // The full parameter vector, free-form for the mock.
  params: Record<string, number>;
}

export interface MapPoint {
  rpm: number;
  massFlow: number;
  pi_tt: number;
  eta_tt: number;
  status: "ok" | "surge" | "choke" | "diverged";
}

export interface MapResult {
  rpmList: number[];
  points: MapPoint[];
}

export interface RotorSection {
  axialStart: number;
  axialEnd: number;
  radius: number;
  kind: "shaft" | "disk" | "bearing";
  label?: string;
}

export interface RotorShape {
  totalLength: number;
  sections: RotorSection[];
}

export interface RunRecord {
  id: string;
  kind: "cycle" | "explore" | "analysis" | "map" | "rotor";
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  startedAt: string;
  finishedAt?: string;
  durationMs?: number;
  summary?: string;
}

export interface JobProgressEvent {
  jobId: string;
  iteration: number;
  residual: number;
  progress: number; // 0..1
  detail?: string;
  done?: boolean;
  status?: "succeeded" | "failed";
  /** Final cycle result, only emitted on the terminal event. */
  result?: CycleResult;
}

export interface CycleComponentPatch {
  label?: string;
  position?: { x: number; y: number };
  params?: Record<string, number | string | boolean>;
}

export interface CycleComponentCreate {
  kind: CycleNodeKind;
  label: string;
  x: number;
  y: number;
  params?: Record<string, number | string | boolean>;
}

/* ---------------------------------------------------------------------------
 * Real-backend-specific shapes (mirror apps/api/models.py).
 *
 * The real ApiClient maps these to the legacy shapes above so existing pages
 * keep compiling. New (Map / Rotor / Analysis) pages prefer the *Backend
 * shapes directly.
 * ------------------------------------------------------------------------- */

export interface HealthResponse {
  status: string;
  version: string;
  cascade_version: string;
  service: string;
}

export interface JobAcceptedResponse {
  job_id: string;
}

export type JobStatus =
  | "queued"
  | "running"
  | "done"
  | "failed"
  | "cancelled";

export interface JobModel {
  id: string;
  project_id: string;
  kind: "cycle" | "explore" | "map" | "analysis" | "rotor";
  status: JobStatus;
  progress: number;
  message: string;
  created_at: string;
  updated_at: string;
  finished_at?: string | null;
  error?: string | null;
  result?: Record<string, unknown> | null;
}

export interface SseProgressEvent {
  job_id: string;
  status?: JobStatus;
  progress?: number;
  message?: string;
  result?: Record<string, unknown> | null;
  error?: string | null;
  final?: boolean;
  data?: Record<string, unknown> | null;
  ping?: boolean;
}

export interface MapRequestPayload {
  speedline_rpms: number[];
  mass_flows: number[];
  parallelism?: number;
}

export interface MapPointBackend {
  coords: { rpm: number; m_dot: number };
  outputs: { pi: number; eta: number; power_kW: number };
  status: string;
}

export interface MapResultBackend {
  axes: { rpm: number[]; m_dot: number[] };
  points: MapPointBackend[];
  surge_line: MapPointBackend[];
  choke_line: MapPointBackend[];
}

export type RotorAnalysisKind =
  | "lateral"
  | "torsional"
  | "critical_speed_map"
  | "campbell"
  | "unbalance";

export interface RotorRequestPayload {
  analysis: RotorAnalysisKind;
  speed_range_rpm?: number[];
  n_modes?: number;
  sections?: Array<Record<string, unknown>>;
  disks?: Array<Record<string, unknown>>;
  bearings?: Array<RotorBearingPayload | Record<string, unknown>>;
}

/** ADAPT-024 anisotropic + optionally tabulated bearing payload. */
export interface RotorBearingPayload {
  id: string;
  axial_position_mm: number;
  /** Linear-bearing direct + cross-coupled stiffness and damping. */
  K_yy_n_per_m?: number;
  K_zz_n_per_m?: number;
  K_yz_n_per_m?: number;
  K_zy_n_per_m?: number;
  C_yy_n_s_per_m?: number;
  C_zz_n_s_per_m?: number;
  C_yz_n_s_per_m?: number;
  C_zy_n_s_per_m?: number;
  /** Tabulated K-C vs RPM (mutually exclusive with linear fields). */
  table?: Array<{
    rpm: number;
    K_yy: number;
    K_zz: number;
    K_yz?: number;
    K_zy?: number;
    C_yy: number;
    C_zz: number;
    C_yz?: number;
    C_zy?: number;
  }>;
  /** Legacy isotropic shape (kept for backwards compatibility). */
  stiffness_N_per_m?: number;
  damping_N_s_per_m?: number;
}

export interface RotorShapeBackend {
  sections: Array<{
    diameter_outer_m: number;
    diameter_inner_m: number;
    length_m: number;
    axial_position_m: number;
    material: string;
  }>;
  disks: Array<{
    mass_kg: number;
    inertia_polar_kg_m2: number;
    inertia_diametrical_kg_m2: number;
    axial_position_m: number;
  }>;
  total_mass_kg: number;
  total_length_m: number;
}

/** A single axial station of a complex eigenvector projected onto the rotor. */
export interface RotorModeShapeNode {
  /** Axial position [m]. */
  axial_position_m: number;
  /** Normalised y-displacement (radial direction 1). */
  y: number;
  /** Normalised z-displacement (radial direction 2). */
  z: number;
}

export interface RotorMode {
  mode_index: number;
  frequency_hz: number;
  /** Frequency in rpm. */
  frequency_rpm?: number;
  /** Undamped natural frequency [rad/s]. */
  omega_n_rad_s?: number;
  /** Damped natural frequency [rad/s]. */
  omega_d_rad_s?: number;
  damping_ratio: number;
  /** API 684 log decrement; null if undamped or numerically suspect. */
  log_decrement?: number | null;
  /** Whirl direction at the evaluation speed. */
  whirl?: "forward" | "backward" | "planar" | "unknown";
  shape_name: string;
  /** Eigenvector projected onto the axial stations (ADAPT-005). */
  mode_shape?: RotorModeShapeNode[];
}

/** Campbell-diagram payload (ADAPT-013). */
export interface RotorCampbellMode {
  mode_id: number;
  frequencies_hz_at_speed: Array<number | null>;
  whirl_per_speed: string[];
  whirl_classification: "forward" | "backward" | "planar";
}

export interface RotorCampbellPayload {
  speeds_rpm: number[];
  modes: RotorCampbellMode[];
  engine_orders: number[];
  critical_intersections: Array<{
    rpm: number;
    mode_id: number;
    engine_order: number;
  }>;
}

/** Critical-speed-map payload (ADAPT-013). */
export interface RotorCriticalSpeedMapPayload {
  stiffness_n_per_m: number[];
  modes: Array<{
    mode_id: number;
    frequencies_hz_at_stiffness: Array<number | null>;
  }>;
  operating_K_n_per_m: number | null;
}

/** One critical-speed entry in the API 684 compliance report (ADAPT-025). */
export interface RotorComplianceCritical {
  rpm: number;
  mode_id: number;
  whirl: "forward" | "backward" | "planar";
  amplification_factor: number;
  separation_margin_pct: number;
  required_margin_pct: number;
  passes: boolean;
  in_operating_envelope: boolean;
  api_clause: string;
  api_citation: string;
}

export interface RotorComplianceReport {
  operating_speed_rpm: number;
  speed_range_rpm: number[];
  criticals: RotorComplianceCritical[];
}

export interface RotorResultBackend {
  analysis: string;
  shape: RotorShapeBackend;
  modes: RotorMode[];
  speed_range_rpm: number[];
  campbell?: RotorCampbellPayload;
  critical_speed_map?: RotorCriticalSpeedMapPayload;
  compliance?: RotorComplianceReport;
  bearings_used?: Array<{
    name: string;
    axial_position_m: number;
    kind: string;
  }>;
}

export interface AnalysisRequestPayload {
  candidate_id?: string;
  machine_class?: "radial_turbine" | "centrifugal_compressor";
  loss_model?: string;
  geometry?: Record<string, unknown>;
  operating_point?: Record<string, unknown>;
}

export interface LossComponent {
  name: string;
  delta_h_J_per_kg: number;
}

export interface HsState {
  label: string;
  h_J_per_kg: number;
  s_J_per_kgK: number;
}

export interface ConvergenceStep {
  iter: number;
  residual: number;
  /** Max per-residual change for the iteration (parity with backend). */
  max_change?: number;
}

export interface VelocityTriangleBackend {
  /** Blade speed [m/s]. */
  U: number;
  /** Meridional component of absolute velocity [m/s]. */
  V_meridional: number;
  /** Tangential component of absolute velocity [m/s]. */
  V_theta: number;
  /** Meridional component of relative velocity [m/s]. */
  W_meridional: number;
  /** Tangential component of relative velocity [m/s]. */
  W_theta: number;
  /** Magnitude of absolute velocity [m/s]. */
  V: number;
  /** Magnitude of relative velocity [m/s]. */
  W: number;
  /** Absolute flow angle from meridional [deg]. */
  alpha_flow_deg: number;
  /** Relative flow angle from meridional [deg]. */
  beta_flow_deg: number;
}

export interface PortStateBackend {
  T_static_K: number;
  T_total_K: number;
  p_static_Pa: number;
  p_total_Pa: number;
  h_static_J_per_kg: number;
  h_total_J_per_kg: number;
  s_J_per_kgK: number;
  M: number;
  rho_kg_per_m3: number;
}

export interface AnalysisEfficienciesBackend {
  eta_tt: number;
  eta_ts: number;
  eta_polytropic: number;
}

export interface AnalysisResultBackend {
  machine_class: string;
  loss_model: string;
  candidate_id?: string | null;
  /** Legacy: kept for old chart code; equal to `efficiencies.eta_tt`. */
  eta_total: number;
  /** Detailed efficiencies. η_ts uses the proper formula (ADAPT-022). */
  efficiencies?: AnalysisEfficienciesBackend;
  pressure_ratio_tt?: number;
  pressure_ratio_ts?: number;
  work_coefficient?: number;
  flow_coefficient?: number;
  power_W?: number;
  max_M_rel?: number;
  slip_factor?: number;
  mass_flow_kg_per_s?: number;
  rotor_speed_rpm?: number;
  fluid?: string;
  /** Two-station port states (h-s diagram, density / Mach). */
  port_states?: {
    inlet: PortStateBackend;
    exit: PortStateBackend;
  };
  /** Two-station velocity triangles for the SVG widget. */
  velocity_triangles?: {
    inlet: VelocityTriangleBackend;
    exit: VelocityTriangleBackend;
  };
  /** Isentropic static enthalpy at exit pressure — denominator of η_ts. */
  h_s2_at_p2_J_per_kg?: number;
  loss_breakdown: LossComponent[];
  convergence_history: ConvergenceStep[];
  h_s_states: HsState[];
  error?: string;
  elapsed_s?: number;
}

export interface LossModelInfo {
  name: string;
  machine_class: string;
  citation: string;
  description?: string;
  scale_factors?: Record<string, number>;
  validity_envelope?: Record<string, unknown>;
}

export interface ValidationCase {
  id: string;
  source: string;
  tolerance: string;
  result: string;
  status: string;
  category: string;
}

/**
 * Materials registry record (mirrors cascade.materials.Material.as_dict).
 * Temperature-dependent properties are arrays of [T_K, value] pairs;
 * the backend interpolates linearly between stations.
 */
export interface MaterialRecord {
  name: string;
  designation: string;
  family: string;
  density_kg_per_m3: number;
  poisson: number;
  /** [T_K, E_GPa] tuples. Use the API or solver for interpolation. */
  youngs_modulus_GPa: Array<[number, number]>;
  /** [T_K, sigma_y_MPa] tuples. */
  yield_strength_MPa: Array<[number, number]>;
  /** [T_K, sigma_u_MPa] tuples. */
  ultimate_strength_MPa: Array<[number, number]>;
  /** [T_K, alpha_per_K] tuples. */
  thermal_expansion_1_per_K: Array<[number, number]>;
  /** [T_K, k_W_per_mK] tuples. */
  thermal_conductivity_W_per_mK: Array<[number, number]>;
  /** [T_K, cp_J_per_kgK] tuples. */
  specific_heat_J_per_kgK: Array<[number, number]>;
  fatigue_S_N_curve?: Array<[number, number]> | null;
  source: string;
  notes?: string;
  max_service_temperature_K?: number | null;
}

/** Manufacturability check report (ADAPT-032). */
export interface ManufacturabilityViolation {
  rule_name: string;
  description: string;
  measured: number;
  threshold_min: number | null;
  threshold_max: number | null;
  units: string;
  severity: "warning" | "error";
  citation: string;
  direction: "below_min" | "above_max";
}

export interface ManufacturabilityPass {
  rule_name: string;
  description: string;
  measured: number;
  threshold_min: number | null;
  threshold_max: number | null;
  units: string;
  citation: string;
}

export interface ManufacturabilityReport {
  machine_class: "centrifugal_compressor" | "radial_turbine";
  geometry_name: string;
  checked_at: string;
  violations: ManufacturabilityViolation[];
  passes: ManufacturabilityPass[];
  overrides_used: Record<string, number>;
  has_violations: boolean;
  critical_count: number;
  warning_count: number;
  rule_count: number;
  geometry: Record<string, number>;
  candidate_id: string | null;
}

/** Public metadata for a registered LossModel plugin. */
export interface PluginLossModelInfo {
  name: string;
  origin: "builtin" | "user";
  applicable_machine_classes: string[];
  description: string;
  citation: string;
  author: string;
  version: string;
}

export interface PluginUploadResponse {
  plugin: PluginLossModelInfo;
  stored_path: string;
  message: string;
}

export interface ActiveLossModelResponse {
  project_id: string;
  active_loss_model: string;
}

/** Public mock-or-real API contract. */
export interface ApiClient {
  /** Health / readiness probe. Throws on non-2xx. */
  health(): Promise<HealthResponse>;

  listProjects(): Promise<Project[]>;
  getProject(id: string): Promise<Project | undefined>;
  getCycle(projectId: string): Promise<CycleGraph>;
  listCandidates(projectId: string): Promise<Candidate[]>;
  getMap(projectId: string): Promise<MapResult>;
  getRotorShape(projectId: string): Promise<RotorShape>;
  listRuns(projectId: string): Promise<RunRecord[]>;

  /** Cycle component CRUD. */
  addCycleComponent(
    projectId: string,
    payload: CycleComponentCreate,
  ): Promise<CycleNode>;
  updateCycleComponent(
    projectId: string,
    componentId: string,
    patch: CycleComponentPatch,
  ): Promise<CycleNode>;
  deleteCycleComponent(projectId: string, componentId: string): Promise<void>;
  addCycleEdge(projectId: string, edge: Omit<CycleEdge, "id">): Promise<CycleEdge>;
  deleteCycleEdge(projectId: string, edgeId: string): Promise<void>;

  /** Run the cycle solver. Returns the job_id; consume events with streamJob. */
  solveCycle(projectId: string): Promise<{ jobId: string }>;
  /** Save a snapshot of the project. */
  saveCycleVersion(projectId: string, note?: string): Promise<{ versionId: string }>;

  /** Map / Rotor / Analysis runs. */
  runMap(projectId: string, payload: MapRequestPayload): Promise<JobAcceptedResponse>;
  runRotor(projectId: string, payload: RotorRequestPayload): Promise<JobAcceptedResponse>;
  runAnalysis(
    projectId: string,
    payload: AnalysisRequestPayload,
  ): Promise<JobAcceptedResponse>;

  /** Polls a job's terminal state. */
  getJob(jobId: string): Promise<JobModel>;
  /** Wait until the job is done/failed/cancelled. Returns the final job. */
  waitForJob(jobId: string, timeoutMs?: number): Promise<JobModel>;

  /** Loss models + validation. */
  listLossModels(): Promise<LossModelInfo[]>;
  listValidationCases(): Promise<ValidationCase[]>;

  /** Per-project plugin management (ADAPT-035). */
  listProjectLossModels(
    projectId: string,
    machineClass?: string,
  ): Promise<PluginLossModelInfo[]>;
  uploadLossModelPlugin(
    projectId: string,
    file: File,
  ): Promise<PluginUploadResponse>;
  selectLossModel(
    projectId: string,
    name: string,
  ): Promise<ActiveLossModelResponse>;
  deleteLossModelPlugin(projectId: string, name: string): Promise<void>;

  /** Materials registry (ADAPT-031). */
  listMaterials(family?: string): Promise<MaterialRecord[]>;
  getMaterial(name: string): Promise<MaterialRecord>;

  /** Manufacturability check (ADAPT-032). */
  getManufacturability(projectId: string): Promise<ManufacturabilityReport>;
  setManufacturabilityOverrides(
    projectId: string,
    overrides: Record<string, number>,
  ): Promise<ManufacturabilityReport>;

  /** Returns an async generator emitting progress events. */
  streamJob(jobId: string): AsyncGenerator<JobProgressEvent, void, void>;
}
