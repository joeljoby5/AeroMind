"use client";

import { useMission } from "@/context/MissionContext";
import { Empty, Spinner } from "./ui";

export function AllocationTab() {
  const { detail, drones, colorOf, plan, planActive, busy, dirty } = useMission();

  if (busy === "plan") return <Spinner label="Running allocation and A* planning…" />;
  if (!detail || !planActive) {
    return (
      <Empty>
        {dirty
          ? "Waypoints changed — press Plan to allocate them."
          : "No plan yet. Load the sample or add waypoints, then press Plan."}
      </Empty>
    );
  }

  const taskNumber = new Map(detail.tasks.map((t, i) => [t.id, i + 1]));
  const byDrone = new Map<number, typeof detail.assignments>();
  detail.assignments.forEach((a) => byDrone.set(a.drone_id, [...(byDrone.get(a.drone_id) ?? []), a]));
  const routeOf = new Map(detail.routes.map((r) => [r.drone_id, r]));
  const strategy = detail.mission.strategy;
  const totalLeg = detail.assignments.reduce((s, a) => s + a.predicted_energy_pct, 0);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
        <span className="rounded border border-line px-2 py-0.5">
          Strategy: <b className="text-ink">{strategy === "ml" ? "AI energy-aware" : "Distance baseline"}</b>
        </span>
        {plan && <span className="rounded border border-line px-2 py-0.5">Model: <b className="text-ink">{plan.model}</b></span>}
        <span className="rounded border border-line px-2 py-0.5">Σ leg energy: <b className="text-ink">{totalLeg.toFixed(1)}%</b></span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-[11px] uppercase tracking-wide text-muted">
            <tr>
              <th className="py-1 pr-2">Drone</th>
              <th className="py-1 pr-2">Tasks (in order)</th>
              <th className="py-1 pr-2 text-right">Energy</th>
              <th className="py-1 text-right">Route</th>
            </tr>
          </thead>
          <tbody>
            {drones.map((d) => {
              const rows = byDrone.get(d.id) ?? [];
              const energy = rows.reduce((s, a) => s + a.predicted_energy_pct, 0);
              return (
                <tr key={d.id} className="border-t border-line align-top">
                  <td className="py-2 pr-2">
                    <div className="flex items-center gap-2">
                      <span className="h-3 w-3 rounded-full" style={{ background: colorOf(d.id) }} aria-hidden />
                      <div>
                        <div className="font-medium">{d.name}</div>
                        <div className="text-[11px] text-muted">battery {d.battery_pct.toFixed(0)}%</div>
                      </div>
                    </div>
                  </td>
                  <td className="py-2 pr-2">
                    {rows.length === 0 ? (
                      <span className="text-muted">— no tasks</span>
                    ) : (
                      <ol className="flex flex-wrap gap-1">
                        {rows.map((a) => (
                          <li key={a.task_id} className="rounded border border-line bg-panel px-1.5 py-0.5 text-xs tabular-nums" title={`Leg energy ${a.predicted_energy_pct.toFixed(2)}%`}>
                            #{taskNumber.get(a.task_id)} <span className="text-muted">({a.predicted_energy_pct.toFixed(1)}%)</span>
                          </li>
                        ))}
                      </ol>
                    )}
                  </td>
                  <td className="py-2 pr-2 text-right tabular-nums">{rows.length ? `${energy.toFixed(1)}%` : "—"}</td>
                  <td className="py-2 text-right tabular-nums text-muted">
                    {routeOf.get(d.id) ? `${routeOf.get(d.id)!.length_m.toFixed(0)} m` : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {plan && plan.unassigned.length > 0 && (
        <div className="rounded-md border border-warn/60 bg-warn/10 p-2 text-xs">
          <div className="mb-1 font-semibold text-warn">▲ {plan.unassigned.length} task(s) unassigned</div>
          <ul className="space-y-0.5">
            {plan.unassigned.map((u) => (
              <li key={u.task_id}>#{taskNumber.get(u.task_id) ?? u.task_id}: {u.reason}</li>
            ))}
          </ul>
        </div>
      )}
      <p className="text-[11px] text-muted">
        Energy = predicted % of battery per leg; “Route” is the obstacle-free A* path home → tasks → home.
      </p>
    </div>
  );
}
