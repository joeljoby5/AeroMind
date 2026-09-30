import type {
  CompareOut, Drone, MissionDetail, Mission, ModelInfo, Obstacle, PlanOut, Strategy, Waypoint,
} from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
export const WS_URL = API_URL.replace(/^http/, "ws") + "/ws/telemetry";

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(`Cannot reach the API at ${API_URL}. Is the backend running?`, 0);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* keep statusText */
    }
    throw new ApiError(detail, res.status);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  drones: () => request<Drone[]>("/api/drones"),
  missions: () => request<Mission[]>("/api/missions"),
  mission: (id: number) => request<MissionDetail>(`/api/missions/${id}`),
  createMission: (name: string, tasks: Waypoint[]) => post<MissionDetail>("/api/missions", { name, tasks }),
  plan: (id: number, strategy: Strategy) => post<PlanOut>(`/api/missions/${id}/plan?strategy=${strategy}`),
  compare: (id: number) => request<CompareOut>(`/api/missions/${id}/compare`),
  start: (id: number) => post<unknown>(`/api/missions/${id}/start`),
  stop: (id: number) => post<unknown>(`/api/missions/${id}/stop`),
  injectObstacle: (id: number, lat: number, lon: number, radius_m: number) =>
    post<Obstacle>(`/api/missions/${id}/obstacles`, { lat, lon, radius_m }),
  clearObstacles: (id: number) => request<void>(`/api/missions/${id}/obstacles`, { method: "DELETE" }),
  drain: (droneId: number, pct: number) => post<unknown>(`/api/drones/${droneId}/drain?pct=${pct}`),
  modelInfo: () => request<ModelInfo>("/api/ai/model-info"),
};
