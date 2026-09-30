"use client";

import { useState } from "react";
import { useTelemetryContext } from "@/context/TelemetryContext";
import { AllocationTab } from "./AllocationTab";
import { ComparisonTab } from "./ComparisonTab";
import { EventsTab } from "./EventsTab";
import { ModelTab } from "./ModelTab";

const TABS = [
  { id: "allocation", label: "Allocation" },
  { id: "comparison", label: "AI Comparison" },
  { id: "model", label: "Model" },
  { id: "events", label: "Events" },
] as const;
type TabId = (typeof TABS)[number]["id"];

export function RightPanel() {
  const [tab, setTab] = useState<TabId>("allocation");
  const { events } = useTelemetryContext();

  return (
    <div className="flex h-full flex-col">
      <div role="tablist" className="flex shrink-0 border-b border-line">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            id={`tab-${t.id}`}
            aria-selected={tab === t.id}
            aria-controls={`panel-${t.id}`}
            onClick={() => setTab(t.id)}
            className={`relative flex-1 px-2 py-2.5 text-sm transition ${
              tab === t.id ? "border-b-2 border-accent font-semibold text-ink" : "text-muted hover:text-ink"
            }`}
          >
            {t.label}
            {t.id === "events" && events.length > 0 && (
              <span className="ml-1 rounded-full bg-line px-1.5 text-[10px] tabular-nums">{events.length}</span>
            )}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} className="min-h-0 flex-1 overflow-y-auto p-3">
        {tab === "allocation" && <AllocationTab />}
        {tab === "comparison" && <ComparisonTab />}
        {tab === "model" && <ModelTab />}
        {tab === "events" && <EventsTab />}
      </div>
    </div>
  );
}
