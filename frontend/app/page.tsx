"use client";

import { DroneList } from "@/components/DroneList";
import { MapView } from "@/components/MapView";
import { MissionPanel } from "@/components/MissionPanel";
import { RightPanel } from "@/components/RightPanel";
import { MissionProvider } from "@/context/MissionContext";
import { TelemetryProvider, useTelemetryContext } from "@/context/TelemetryContext";

const DOT = { open: "bg-good", connecting: "bg-warn", closed: "bg-bad" } as const;
const LABEL = { open: "Live", connecting: "Connecting…", closed: "Disconnected" } as const;

function Header() {
  const { status, running } = useTelemetryContext();
  return (
    <header className="flex items-center justify-between">
      <div>
        <h1 className="text-lg font-bold tracking-tight">AeroMind</h1>
        <p className="text-[11px] text-muted">Multi-drone mission command · simulation</p>
      </div>
      <span className="flex items-center gap-1.5 rounded-full border border-line px-2.5 py-1 text-xs" title="WebSocket telemetry">
        <span className={`h-2 w-2 rounded-full ${DOT[status]} ${status === "open" ? "" : "animate-pulse"}`} aria-hidden />
        {LABEL[status]}
        {running && <span className="text-accent">· mission running</span>}
      </span>
    </header>
  );
}

function Dashboard() {
  return (
    <div className="grid h-screen grid-cols-1 grid-rows-[auto_minmax(60vh,1fr)_auto] overflow-hidden lg:grid-cols-[350px_minmax(0,1fr)_440px] lg:grid-rows-1">
      <aside className="order-1 space-y-3 overflow-y-auto border-line bg-panel p-3 lg:border-r">
        <Header />
        <DroneList />
        <MissionPanel />
      </aside>
      <main className="order-2 min-h-0">
        <MapView />
      </main>
      <aside className="order-3 min-h-0 border-line bg-panel lg:border-l">
        <RightPanel />
      </aside>
    </div>
  );
}

export default function Page() {
  return (
    <TelemetryProvider>
      <MissionProvider>
        <Dashboard />
      </MissionProvider>
    </TelemetryProvider>
  );
}
