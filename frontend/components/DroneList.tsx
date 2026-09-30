"use client";

import { useState } from "react";
import { useMission } from "@/context/MissionContext";
import { useTelemetryContext } from "@/context/TelemetryContext";
import { batteryColor } from "@/lib/colors";
import type { DroneType } from "@/lib/types";
import { Btn, Card, Empty, StateBadge } from "./ui";

const TYPE_LABEL = { quad_small: "Quad (small)", quad_medium: "Quad (medium)", hex_heavy: "Hex (heavy)" } as const;
const FLYING = new Set(["TAKEOFF", "EN_ROUTE", "EXECUTING_TASK", "AVOIDING"]);

function RegisterDrone() {
  const { drones, registerDrone, pendingHome, setPendingHome, mode, setMode } = useMission();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [type, setType] = useState<DroneType>("quad_medium");
  const [battery, setBattery] = useState(90);
  const [health, setHealth] = useState(0.95);
  const [saving, setSaving] = useState(false);
  const base = drones[0];
  const home = pendingHome ?? (base ? { lat: base.home_lat, lon: base.home_lon } : { lat: 12.9716, lon: 77.5946 });
  const field = "w-full rounded border border-line bg-bg px-1.5 py-1 text-ink";

  if (!open) {
    return (
      <Btn className="mt-2 w-full" onClick={() => setOpen(true)}>＋ Register drone</Btn>
    );
  }
  return (
    <form
      className="mt-2 space-y-2 rounded-md border border-line bg-panel p-2 text-xs"
      onSubmit={async (e) => {
        e.preventDefault();
        setSaving(true);
        const ok = await registerDrone({
          name: name.trim() || `Drone-${drones.length + 1}`, type,
          battery_pct: battery, health, home_lat: home.lat, home_lon: home.lon,
        });
        setSaving(false);
        if (ok) { setOpen(false); setName(""); }
      }}
    >
      <div className="grid grid-cols-2 gap-2">
        <label className="text-muted">Name
          <input className={field} value={name} placeholder={`Drone-${drones.length + 1}`} maxLength={64} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="text-muted">Type
          <select className={field} value={type} onChange={(e) => setType(e.target.value as DroneType)}>
            <option value="quad_small">Quad (small)</option>
            <option value="quad_medium">Quad (medium)</option>
            <option value="hex_heavy">Hex (heavy)</option>
          </select>
        </label>
        <label className="text-muted">Battery %
          <input className={field} type="number" min={0} max={100} value={battery} onChange={(e) => setBattery(Math.min(100, Math.max(0, Number(e.target.value))))} />
        </label>
        <label className="text-muted">Health (0.70–1.00)
          <input className={field} type="number" min={0.7} max={1} step={0.01} value={health} onChange={(e) => setHealth(Math.min(1, Math.max(0.7, Number(e.target.value))))} />
        </label>
      </div>
      <div className="flex items-center justify-between gap-2 text-muted">
        <span className="tabular-nums">Home: {home.lat.toFixed(5)}, {home.lon.toFixed(5)}</span>
        <Btn active={mode === "home"} onClick={() => setMode(mode === "home" ? "idle" : "home")}>Pick on map</Btn>
      </div>
      <div className="flex gap-2">
        <Btn tone="primary" type="submit" className="flex-1" disabled={saving}>
          {saving ? "Saving…" : "Register"}
        </Btn>
        <Btn onClick={() => { setOpen(false); setPendingHome(null); if (mode === "home") setMode("idle"); }}>Cancel</Btn>
      </div>
    </form>
  );
}

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
      <RegisterDrone />
    </Card>
  );
}
