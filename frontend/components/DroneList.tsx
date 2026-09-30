"use client";

import { useMission } from "@/context/MissionContext";
import { useTelemetryContext } from "@/context/TelemetryContext";
import { batteryColor } from "@/lib/colors";
import { Card, Empty, StateBadge } from "./ui";

const TYPE_LABEL = { quad_small: "Quad (small)", quad_medium: "Quad (medium)", hex_heavy: "Hex (heavy)" } as const;
const FLYING = new Set(["TAKEOFF", "EN_ROUTE", "EXECUTING_TASK", "AVOIDING"]);

export function DroneList() {
  const { drones, colorOf, drainBattery, busy } = useMission();
  const tel = useTelemetryContext();

  return (
    <Card title={`Fleet (${drones.length})`}>
      {busy === "init" && drones.length === 0 ? (
        <div className="h-16 animate-pulse rounded bg-panel" />
      ) : drones.length === 0 ? (
        <Empty>No drones registered. Run <code>make seed</code>.</Empty>
      ) : (
        <ul className="space-y-2">
          {drones.map((d) => {
            const live = tel.drones[d.id];
            const battery = live?.battery_pct ?? d.battery_pct;
            const state = live?.state ?? "IDLE";
            return (
              <li key={d.id} className="rounded-md border border-line bg-panel p-2">
                <div className="flex items-center gap-2">
                  <span className="h-3 w-3 shrink-0 rounded-full" style={{ background: colorOf(d.id) }} aria-hidden />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-semibold">{d.name}</div>
                    <div className="text-[11px] text-muted">{TYPE_LABEL[d.type]} · health {(d.health * 100).toFixed(0)}%</div>
                  </div>
                  <StateBadge state={state} />
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <div className="h-2 flex-1 overflow-hidden rounded bg-line" role="progressbar" aria-valuenow={Math.round(battery)} aria-valuemin={0} aria-valuemax={100} aria-label={`${d.name} battery`}>
                    <div className="h-full rounded transition-all" style={{ width: `${Math.max(0, Math.min(100, battery))}%`, background: batteryColor(battery) }} />
                  </div>
                  <span className="w-12 text-right text-xs tabular-nums">{battery.toFixed(0)}%</span>
                  {live && FLYING.has(live.state) && (
                    <button
                      className="rounded border border-line px-1.5 text-[11px] text-muted hover:border-warn hover:text-warn"
                      title="Demo: inject a battery fault (-20%) to trigger return-to-launch"
                      onClick={() => drainBattery(d.id, 20)}
                    >
                      ⚡ −20%
                    </button>
                  )}
                </div>
                {live && live.tasks_total > 0 && (
                  <div className="mt-1 text-[11px] text-muted">
                    Tasks {live.tasks_done}/{live.tasks_total} · alt {live.alt_m.toFixed(0)} m
                    {live.lidar_min_m !== null && live.lidar_min_m < 60 && <> · LiDAR {live.lidar_min_m.toFixed(0)} m</>}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
