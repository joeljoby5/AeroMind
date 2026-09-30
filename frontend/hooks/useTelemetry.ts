"use client";

import { useEffect, useRef, useState } from "react";
import type { EventItem, LatLng, LiveDrone, Obstacle, TelemetryMessage } from "@/lib/types";

export type ConnectionStatus = "connecting" | "open" | "closed";

export interface TelemetryState {
  status: ConnectionStatus;
  drones: Record<number, LiveDrone>;
  trails: Record<number, LatLng[]>;
  events: EventItem[];
  obstacles: Obstacle[];
  missionId: number | null;
  missionStatus: string;
  running: boolean;
  simTime: number;
}

const EMPTY: TelemetryState = {
  status: "connecting", drones: {}, trails: {}, events: [], obstacles: [],
  missionId: null, missionStatus: "idle", running: false, simTime: 0,
};
const MAX_EVENTS = 300;
const MAX_TRAIL = 800;

/** Native WebSocket with automatic reconnect (exponential back-off, capped at 8 s). */
export function useTelemetry(url: string): TelemetryState {
  const [state, setState] = useState<TelemetryState>(EMPTY);
  const lastSim = useRef(0);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let attempt = 0;
    let closed = false;

    const apply = (msg: TelemetryMessage) =>
      setState((prev) => {
        const restarted = msg.sim_time_s < lastSim.current || msg.type === "snapshot";
        lastSim.current = msg.sim_time_s;
        const drones: Record<number, LiveDrone> = {};
        const trails: Record<number, LatLng[]> = restarted && msg.type === "tick" ? {} : { ...prev.trails };
        for (const d of msg.drones) {
          drones[d.id] = d;
          if (d.state !== "IDLE") {
            const t = trails[d.id] ? [...trails[d.id]] : [];
            const last = t[t.length - 1];
            if (!last || Math.abs(last[0] - d.lat) + Math.abs(last[1] - d.lon) > 1e-6) t.push([d.lat, d.lon]);
            trails[d.id] = t.slice(-MAX_TRAIL);
          }
        }
        const seen = new Set(msg.type === "snapshot" ? [] : prev.events.map((e) => e.id));
        const fresh = msg.events.filter((e) => !seen.has(e.id));
        const events = (msg.type === "snapshot" ? fresh : [...prev.events, ...fresh]).slice(-MAX_EVENTS);
        return {
          status: "open", drones, trails, events, obstacles: msg.obstacles,
          missionId: msg.mission_id, missionStatus: msg.mission_status,
          running: msg.running, simTime: msg.sim_time_s,
        };
      });

    const connect = () => {
      setState((s) => ({ ...s, status: "connecting" }));
      ws = new WebSocket(url);
      ws.onopen = () => {
        attempt = 0;
        setState((s) => ({ ...s, status: "open" }));
      };
      ws.onmessage = (e) => {
        try {
          apply(JSON.parse(e.data) as TelemetryMessage);
        } catch {
          /* ignore malformed frame */
        }
      };
      ws.onerror = () => ws?.close();
      ws.onclose = () => {
        if (closed) return;
        setState((s) => ({ ...s, status: "closed" }));
        timer = setTimeout(connect, Math.min(1000 * 2 ** attempt++, 8000));
      };
    };

    connect();
    return () => {
      closed = true;
      if (timer) clearTimeout(timer);
      ws?.close();
    };
  }, [url]);

  return state;
}
