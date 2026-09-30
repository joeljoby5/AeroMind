"use client";

import dynamic from "next/dynamic";
import { Spinner } from "./ui";

// Leaflet touches `window`, so the map only renders in the browser.
export const MapView = dynamic(() => import("./MapInner"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center bg-bg">
      <Spinner label="Loading map…" />
    </div>
  ),
});
