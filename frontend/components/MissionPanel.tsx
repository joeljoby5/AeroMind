"use client";

import { useMission } from "@/context/MissionContext";
import { useTelemetryContext } from "@/context/TelemetryContext";
import { Btn, Card, Empty, ErrorBox, Spinner } from "./ui";

export function MissionPanel() {
  const m = useMission();
  const tel = useTelemetryContext();
  const running = tel.running;
  const busy = m.busy !== null;
  const assignmentByTask = new Map(m.detail?.assignments.map((a) => [a.task_id, a]) ?? []);

  return (
    <div className="space-y-3">
      {m.error && <ErrorBox message={m.error} onDismiss={m.dismissError} onRetry={m.detail === null ? m.retryInit : undefined} />}

      <Card title="Strategy">
        <div className="grid grid-cols-2 gap-1 rounded-md border border-line p-1" role="radiogroup" aria-label="Allocation strategy">
          {(["ml", "baseline"] as const).map((s) => (
            <button
              key={s}
              role="radio"
              aria-checked={m.strategy === s}
              disabled={running}
              onClick={() => m.setStrategy(s)}
              className={`rounded px-2 py-1.5 text-sm transition disabled:opacity-50 ${
                m.strategy === s ? "bg-accent font-semibold text-white" : "text-muted hover:text-ink"
              }`}
            >
              {s === "ml" ? "AI · energy-aware" : "Baseline · distance"}
            </button>
          ))}
        </div>
        <p className="mt-2 text-[11px] text-muted">
          {m.strategy === "ml"
            ? "Trained energy model → Hungarian cost matrix, with battery-reserve feasibility."
            : "Straight-line distance only. Deterministic fallback, no model."}
        </p>
      </Card>

      <Card
        title={`Mission waypoints (${m.draft.length})`}
        right={m.dirty ? <span className="text-[11px] text-warn">▲ unsaved — press Plan</span> : undefined}
      >
        <div className="mb-2 flex flex-wrap gap-2">
          <Btn active={m.mode === "waypoint"} disabled={running} onClick={() => m.setMode(m.mode === "waypoint" ? "idle" : "waypoint")}>
            ＋ Add waypoints
          </Btn>
          <Btn disabled={running || busy} onClick={m.loadSample} title="Reload the seeded sample mission (8 waypoints)">
            Load sample
          </Btn>
          <Btn disabled={running || m.draft.length === 0} onClick={m.clearWaypoints}>
            Clear
          </Btn>
        </div>
        {m.mode === "waypoint" && <p className="mb-2 text-[11px] text-accent">Click the map to drop waypoints.</p>}

        {m.busy === "init" && m.draft.length === 0 ? (
          <Spinner label="Loading mission…" />
        ) : m.draft.length === 0 ? (
          <Empty>No waypoints yet. Click “Add waypoints”, then click the map — or load the sample.</Empty>
        ) : (
          <ul className="max-h-64 space-y-1 overflow-y-auto pr-1">
            {m.draft.map((w, i) => {
              const task = !m.dirty ? m.detail?.tasks[i] : undefined;
              const a = task ? assignmentByTask.get(task.id) : undefined;
              return (
                <li key={i} className="flex items-center gap-2 rounded border border-line bg-panel px-2 py-1 text-xs">
                  <span
                    className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-bold text-white"
                    style={{ background: a && m.planActive ? m.colorOf(a.drone_id) : "#6b7686" }}
                  >
                    {i + 1}
                  </span>
                  <span className="min-w-0 flex-1 truncate tabular-nums text-muted" title={`${w.lat}, ${w.lon}`}>
                    {w.lat.toFixed(4)}, {w.lon.toFixed(4)}
                  </span>
                  <label className="flex items-center gap-1 text-muted" title="Flight altitude (m)">
                    ↑
                    <input
                      type="number" min={5} max={120} step={5} value={w.altitude_m} disabled={running}
                      onChange={(e) => m.updateWaypoint(i, { altitude_m: Math.min(120, Math.max(5, Number(e.target.value) || 5)) })}
                      className="w-12 rounded border border-line bg-bg px-1 py-0.5 text-right text-ink"
                    />
                  </label>
                  <label className="flex items-center gap-1 text-muted" title="Payload (kg) — drives energy use">
                    ⚖
                    <input
                      type="number" min={0} max={2.5} step={0.1} value={w.payload_kg} disabled={running}
                      onChange={(e) => m.updateWaypoint(i, { payload_kg: Math.min(2.5, Math.max(0, Number(e.target.value) || 0)) })}
                      className="w-12 rounded border border-line bg-bg px-1 py-0.5 text-right text-ink"
                    />
                  </label>
                  <button aria-label={`Delete waypoint ${i + 1}`} disabled={running} onClick={() => m.removeWaypoint(i)} className="text-muted hover:text-bad disabled:opacity-40">
                    ×
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </Card>

      <Card title="Mission control">
        <div className="grid grid-cols-3 gap-2">
          <Btn tone="primary" disabled={busy || running || m.draft.length === 0} onClick={m.runPlan}>
            {m.busy === "plan" ? "Planning…" : "Plan"}
          </Btn>
          <Btn tone="primary" disabled={busy || running || !m.planActive} onClick={m.startMission} title={m.planActive ? "Start the mission" : "Plan the mission first"}>
            {m.busy === "start" ? "Starting…" : "▶ Start"}
          </Btn>
          <Btn tone="danger" disabled={!running || m.busy === "stop"} onClick={m.stopMission}>
            ■ Stop
          </Btn>
        </div>

        <div className="mt-3 flex items-center gap-2">
          <Btn
            active={m.mode === "obstacle"}
            disabled={!m.detail || m.dirty}
            onClick={() => m.setMode(m.mode === "obstacle" ? "idle" : "obstacle")}
            title="Then click the map to drop an obstacle"
          >
            ⚠ Inject obstacle
          </Btn>
          <label className="flex items-center gap-1 text-[11px] text-muted">
            radius
            <select
              value={m.obstacleRadius}
              onChange={(e) => m.setObstacleRadius(Number(e.target.value))}
              className="rounded border border-line bg-bg px-1 py-1 text-ink"
            >
              {[20, 30, 45, 60].map((r) => (
                <option key={r} value={r}>{r} m</option>
              ))}
            </select>
          </label>
          <Btn disabled={running || !m.detail || m.detail.obstacles.length === 0} onClick={m.clearObstacles}>
            Clear ({m.detail?.obstacles.length ?? 0})
          </Btn>
        </div>
        {m.mode === "obstacle" && (
          <p className="mt-2 text-[11px] text-bad">
            Click the map (ideally on a route). While flying, drones detect it with LiDAR and replan with A*.
          </p>
        )}
        <p className="mt-3 text-[11px] text-muted">
          Status: <span className="text-ink">{tel.running ? "running" : tel.missionStatus}</span>
          {tel.running && <> · sim time {tel.simTime.toFixed(0)} s</>}
        </p>
      </Card>
    </div>
  );
}
