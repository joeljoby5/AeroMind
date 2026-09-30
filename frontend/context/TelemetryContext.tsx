"use client";

import { createContext, useContext, type ReactNode } from "react";
import { WS_URL } from "@/lib/api";
import { useTelemetry, type TelemetryState } from "@/hooks/useTelemetry";

const TelemetryContext = createContext<TelemetryState | null>(null);

export function TelemetryProvider({ children }: { children: ReactNode }) {
  const state = useTelemetry(WS_URL);
  return <TelemetryContext.Provider value={state}>{children}</TelemetryContext.Provider>;
}

export function useTelemetryContext(): TelemetryState {
  const ctx = useContext(TelemetryContext);
  if (!ctx) throw new Error("useTelemetryContext must be used inside <TelemetryProvider>");
  return ctx;
}
