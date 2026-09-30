// Categorical series colours (dark-mode steps), assigned to drones in fixed id order.
export const DRONE_COLORS = [
  "#3987e5", // blue
  "#d95926", // orange
  "#199e70", // aqua
  "#c98500", // yellow
  "#d55181", // magenta
  "#22a522", // green
  "#9085e9", // violet
  "#e66767", // red
];

export const ML_COLOR = "#3987e5";
export const BASELINE_COLOR = "#d95926";

export function droneColor(index: number): string {
  return DRONE_COLORS[index % DRONE_COLORS.length];
}

export function batteryColor(pct: number): string {
  if (pct > 50) return "var(--good)";
  if (pct > 25) return "var(--warn)";
  return "var(--bad)";
}

export const STATE_LABEL: Record<string, string> = {
  IDLE: "Idle",
  ARMED: "Armed",
  TAKEOFF: "Take-off",
  EN_ROUTE: "En route",
  EXECUTING_TASK: "Executing task",
  AVOIDING: "Avoiding",
  RETURN_TO_LAUNCH: "Return to launch",
  LANDED: "Landed",
  FAILSAFE: "FAILSAFE",
};

export function stateTone(state: string): "neutral" | "active" | "warn" | "bad" {
  if (state === "FAILSAFE") return "bad";
  if (state === "AVOIDING" || state === "RETURN_TO_LAUNCH") return "warn";
  if (state === "IDLE" || state === "LANDED") return "neutral";
  return "active";
}
