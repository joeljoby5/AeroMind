"use client";

import { useTelemetryContext } from "@/context/TelemetryContext";
import { useMission } from "@/context/MissionContext";
import { Empty } from "./ui";

const GLYPH = { info: "●", warn: "▲", alert: "✖" } as const;
const TONE = { info: "text-muted", warn: "text-warn", alert: "text-bad" } as const;

export function EventsTab() {
  const { events } = useTelemetryContext();
  const { colorOf } = useMission();
  if (events.length === 0) return <Empty>No events yet. Start a mission to see FSM transitions, replanning and alerts.</Empty>;

  return (
    <ol className="space-y-1" aria-live="polite">
      {[...events].reverse().map((e) => (
        <li key={e.id} className="flex gap-2 rounded border border-line bg-panel px-2 py-1.5 text-xs">
          <span className={`mt-0.5 ${TONE[e.level]}`} aria-label={e.level}>{GLYPH[e.level]}</span>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5 text-[11px] text-muted">
              {e.drone_id !== null && <span className="h-2 w-2 rounded-full" style={{ background: colorOf(e.drone_id) }} aria-hidden />}
              <b className="text-ink">{e.drone_name}</b>
              <span className="tabular-nums">t+{e.sim_time_s.toFixed(0)}s</span>
            </div>
            <div className="break-words">{e.message}</div>
          </div>
        </li>
      ))}
    </ol>
  );
}
