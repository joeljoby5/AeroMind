export type DroneType = "quad_small" | "quad_medium" | "hex_heavy";
export type Strategy = "ml" | "baseline";
export type LatLng = [number, number];

export interface Drone {
  id: number;
  name: string;
  type: DroneType;
  battery_pct: number;
  health: number;
  home_lat: number;
  home_lon: number;
  status: string;
}

export interface Task {
  id: number;
  lat: number;
  lon: number;
  altitude_m: number;
  payload_kg: number;
}

export interface Assignment {
  drone_id: number;
  task_id: number;
  order: number;
  predicted_energy_pct: number;
}

export interface Obstacle {
  id: number;
  lat: number;
  lon: number;
  radius_m: number;
}

export interface Route {
  drone_id: number;
  drone_name: string;
  task_ids: number[];
  polyline: LatLng[];
  length_m: number;
}

export interface Mission {
  id: number;
  name: string;
  status: string;
  strategy: Strategy | null;
  created_at: string;
}

export interface MissionDetail {
  mission: Mission;
  tasks: Task[];
  assignments: Assignment[];
  obstacles: Obstacle[];
  routes: Route[];
}

export interface Unassigned {
  task_id: number;
  reason: string;
}

export interface PlanOut {
  mission_id: number;
  strategy: Strategy;
  model: string;
  assignments: Assignment[];
  routes: Route[];
  total_energy_pct: number;
  unassigned: Unassigned[];
}

export interface StrategyResult {
  strategy: Strategy;
  assignments: Assignment[];
  predicted_energy_pct: number;
  actual_energy_pct: number;
  infeasible_assignments: number;
  assigned: number;
  unassigned: number;
}

export interface CompareOut {
  mission_id: number;
  model: string;
  ml: StrategyResult;
  baseline: StrategyResult;
  energy_saving_pct: number;
  infeasible_avoided: number;
}

export interface ModelMetrics {
  mae: number;
  rmse: number;
  r2: number;
  cv_rmse_mean: number;
  cv_rmse_std: number;
  cv_mae_mean: number;
  cv_r2_mean: number;
}

export interface ModelInfo {
  best_model?: string;
  selection_criterion?: string;
  n_rows?: number;
  n_train?: number;
  n_test?: number;
  models?: Record<string, ModelMetrics>;
  feature_importance?: Record<string, number>;
  active_model: string;
  is_fallback: boolean;
}

// ---- drafts (client-side waypoints before the mission is saved) ----
export interface Waypoint {
  lat: number;
  lon: number;
  altitude_m: number;
  payload_kg: number;
}

// ---- live telemetry ----
export type FsmState =
  | "IDLE"
  | "ARMED"
  | "TAKEOFF"
  | "EN_ROUTE"
  | "EXECUTING_TASK"
  | "AVOIDING"
  | "RETURN_TO_LAUNCH"
  | "LANDED"
  | "FAILSAFE";

export interface LiveDrone {
  id: number;
  name: string;
  type: DroneType;
  lat: number;
  lon: number;
  alt_m: number;
  battery_pct: number;
  state: FsmState;
  heading_deg: number;
  current_task_id: number | null;
  lidar_min_m: number | null;
  route: LatLng[];
  tasks_done: number;
  tasks_total: number;
}

export interface EventItem {
  id: number;
  ts: string;
  sim_time_s: number;
  drone_id: number | null;
  drone_name: string;
  level: "info" | "warn" | "alert";
  message: string;
}

export interface TelemetryMessage {
  type: "snapshot" | "tick";
  ts: string;
  mission_id: number | null;
  mission_status: string;
  running: boolean;
  sim_time_s: number;
  speedup: number;
  drones: LiveDrone[];
  obstacles: Obstacle[];
  events: EventItem[];
}
