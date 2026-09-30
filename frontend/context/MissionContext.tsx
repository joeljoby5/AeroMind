"use client";

import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode,
} from "react";
import { api, ApiError } from "@/lib/api";
import { droneColor } from "@/lib/colors";
import type {
  CompareOut, Drone, DroneCreate, MissionDetail, PlanOut, Strategy, Waypoint,
} from "@/lib/types";
import { useTelemetryContext } from "./TelemetryContext";

export type MapMode = "idle" | "waypoint" | "obstacle" | "home";
type Busy = "init" | "plan" | "start" | "stop" | "obstacle" | null;

interface MissionContextValue {
  drones: Drone[];
  detail: MissionDetail | null;
  draft: Waypoint[];
  dirty: boolean;
  planActive: boolean; // a plan exists for exactly the waypoints currently shown
  plan: PlanOut | null;
  compare: CompareOut | null;
  compareError: string | null;
  strategy: Strategy;
  mode: MapMode;
  obstacleRadius: number;
  busy: Busy;
  error: string | null;
  pendingHome: { lat: number; lon: number } | null;
  setPendingHome: (p: { lat: number; lon: number } | null) => void;
  registerDrone: (body: DroneCreate) => Promise<boolean>;
  colorOf: (droneId: number) => string;
  setStrategy: (s: Strategy) => void;
  setMode: (m: MapMode) => void;
  setObstacleRadius: (r: number) => void;
  addWaypoint: (lat: number, lon: number) => void;
  removeWaypoint: (index: number) => void;
  updateWaypoint: (index: number, patch: Partial<Waypoint>) => void;
  clearWaypoints: () => void;
  loadSample: () => Promise<void>;
  runPlan: () => Promise<void>;
  startMission: () => Promise<void>;
  stopMission: () => Promise<void>;
  injectObstacle: (lat: number, lon: number) => Promise<void>;
  clearObstacles: () => Promise<void>;
  drainBattery: (droneId: number, pct: number) => Promise<void>;
  dismissError: () => void;
  retryInit: () => void;
}

const MissionContext = createContext<MissionContextValue | null>(null);

const msg = (e: unknown) => (e instanceof ApiError || e instanceof Error ? e.message : String(e));
const toDraft = (d: MissionDetail): Waypoint[] =>
  d.tasks.map((t) => ({ lat: t.lat, lon: t.lon, altitude_m: t.altitude_m, payload_kg: t.payload_kg }));

export function MissionProvider({ children }: { children: ReactNode }) {
  const tel = useTelemetryContext();
  const [drones, setDrones] = useState<Drone[]>([]);
  const [detail, setDetail] = useState<MissionDetail | null>(null);
  const [draft, setDraft] = useState<Waypoint[]>([]);
  const [dirty, setDirty] = useState(false);
  const [plan, setPlan] = useState<PlanOut | null>(null);
  const [compare, setCompare] = useState<CompareOut | null>(null);
  const [compareError, setCompareError] = useState<string | null>(null);
  const [strategy, setStrategy] = useState<Strategy>("ml");
  const [mode, setMode] = useState<MapMode>("idle");
  const [obstacleRadius, setObstacleRadius] = useState(30);
  const [busy, setBusy] = useState<Busy>("init");
  const [error, setError] = useState<string | null>(null);
  const [initNonce, setInitNonce] = useState(0);
  const [pendingHome, setPendingHome] = useState<{ lat: number; lon: number } | null>(null);

  const applyDetail = useCallback((d: MissionDetail) => {
    setDetail(d);
    setDraft(toDraft(d));
    setDirty(false);
  }, []);

  const loadCompare = useCallback(async (id: number) => {
    try {
      setCompare(await api.compare(id));
      setCompareError(null);
    } catch (e) {
      setCompare(null);
      setCompareError(msg(e));
    }
  }, []);

  // ---- initial load: drones + most recent mission ----
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setBusy("init");
      try {
        const [ds, missions] = await Promise.all([api.drones(), api.missions()]);
        if (cancelled) return;
        setDrones(ds);
        if (missions.length) {
          const d = await api.mission(missions[0].id);
          if (cancelled) return;
          applyDetail(d);
          if (d.assignments.length) await loadCompare(d.mission.id);
        }
        setError(null);
      } catch (e) {
        if (!cancelled) setError(msg(e));
      } finally {
        if (!cancelled) setBusy(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [initNonce, applyDetail, loadCompare]);

  // ---- when a run ends, refresh the persisted mission (status) ----
  const wasRunning = useRef(false);
  useEffect(() => {
    if (wasRunning.current && !tel.running && detail) {
      api.mission(detail.mission.id).then(setDetail).catch(() => undefined);
    }
    wasRunning.current = tel.running;
  }, [tel.running, detail]);

  const guard = useCallback(async (kind: Exclude<Busy, null>, fn: () => Promise<void>) => {
    setBusy(kind);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(msg(e));
    } finally {
      setBusy(null);
    }
  }, []);

  const value = useMemo<MissionContextValue>(() => {
    const planActive = !dirty && !!detail && detail.assignments.length > 0;
    const idIndex = new Map(drones.map((d, i) => [d.id, i]));
    return {
      drones, detail, draft, dirty, planActive, plan, compare, compareError, strategy, mode,
      obstacleRadius, busy, error, pendingHome, setPendingHome,
      registerDrone: async (body) => {
        try {
          const created = await api.createDrone(body);
          setDrones((ds) => [...ds, created]);
          setPendingHome(null);
          setError(null);
          return true;
        } catch (e) {
          setError(msg(e));
          return false;
        }
      },
      colorOf: (id) => droneColor(idIndex.get(id) ?? id),
      setStrategy, setMode, setObstacleRadius,
      addWaypoint: (lat, lon) => {
        setDraft((d) => [...d, { lat, lon, altitude_m: 35, payload_kg: 0 }]);
        setDirty(true);
      },
      removeWaypoint: (i) => {
        setDraft((d) => d.filter((_, k) => k !== i));
        setDirty(true);
      },
      updateWaypoint: (i, patch) => {
        setDraft((d) => d.map((w, k) => (k === i ? { ...w, ...patch } : w)));
        setDirty(true);
      },
      clearWaypoints: () => {
        setDraft([]);
        setDirty(true);
      },
      loadSample: () =>
        guard("init", async () => {
          const missions = await api.missions();
          if (!missions.length) throw new Error("No sample mission found. Run `make seed` on the backend.");
          const sample = missions[missions.length - 1]; // oldest = the seeded sample
          applyDetail(await api.mission(sample.id));
          setPlan(null);
          setCompare(null);
          setCompareError(null);
        }),
      runPlan: () =>
        guard("plan", async () => {
          if (!draft.length) throw new Error("Add at least one waypoint (click the map) before planning.");
          let d = detail;
          if (dirty || !d) {
            d = await api.createMission(`Mission ${new Date().toLocaleTimeString()}`, draft);
          }
          const id = d.mission.id;
          const p = await api.plan(id, strategy);
          setPlan(p);
          const fresh = await api.mission(id);
          applyDetail(fresh);
          await loadCompare(id);
        }),
      startMission: () =>
        guard("start", async () => {
          if (!detail) throw new Error("Plan the mission first.");
          await api.start(detail.mission.id);
          setMode("idle");
        }),
      stopMission: () =>
        guard("stop", async () => {
          if (detail) await api.stop(detail.mission.id);
        }),
      injectObstacle: (lat, lon) =>
        guard("obstacle", async () => {
          if (!detail || dirty) throw new Error("Plan the mission first, then inject obstacles.");
          const ob = await api.injectObstacle(detail.mission.id, lat, lon, obstacleRadius);
          setDetail((cur) => (cur ? { ...cur, obstacles: [...cur.obstacles, ob] } : cur));
        }),
      clearObstacles: () =>
        guard("obstacle", async () => {
          if (!detail) return;
          await api.clearObstacles(detail.mission.id);
          setDetail((cur) => (cur ? { ...cur, obstacles: [] } : cur));
        }),
      drainBattery: async (id, pct) => {
        try {
          await api.drain(id, pct);
        } catch (e) {
          setError(msg(e));
        }
      },
      dismissError: () => setError(null),
      retryInit: () => setInitNonce((n) => n + 1),
    };
  }, [drones, detail, draft, dirty, plan, compare, compareError, strategy, mode, obstacleRadius, busy,
      error, pendingHome, guard, applyDetail, loadCompare]);

  return <MissionContext.Provider value={value}>{children}</MissionContext.Provider>;
}

export function useMission(): MissionContextValue {
  const ctx = useContext(MissionContext);
  if (!ctx) throw new Error("useMission must be used inside <MissionProvider>");
  return ctx;
}
