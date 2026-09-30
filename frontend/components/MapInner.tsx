"use client";

import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useMemo, useRef } from "react";
import { Circle, MapContainer, Marker, Polyline, TileLayer, Tooltip, useMap, useMapEvents } from "react-leaflet";
import { useMission } from "@/context/MissionContext";
import { useTelemetryContext } from "@/context/TelemetryContext";
import { STATE_LABEL } from "@/lib/colors";
import type { LatLng, Obstacle } from "@/lib/types";

const NEUTRAL = "#7d8898";

const waypointIcon = (n: number, color: string) =>
  L.divIcon({
    className: "",
    html: `<div class="wp-marker" style="background:${color}">${n}</div>`,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
  });

const homeIcon = (color: string) =>
  L.divIcon({
    className: "",
    html: `<div class="home-marker" style="border-color:${color};color:${color}">H</div>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });

const droneIcon = (color: string, label: string, heading: number, alert: boolean) =>
  L.divIcon({
    className: "",
    html: `<div class="drone-marker ${alert ? "drone-alert" : ""}" style="--c:${color}">
             <div class="drone-arrow" style="transform:rotate(${heading}deg)"></div>
             <span>${label}</span>
           </div>`,
    iconSize: [34, 34],
    iconAnchor: [17, 17],
  });

function ClickHandler() {
  const { mode, addWaypoint, injectObstacle, setPendingHome, setMode } = useMission();
  useMapEvents({
    click(e) {
      if (mode === "home") {
        setPendingHome({ lat: e.latlng.lat, lon: e.latlng.lng });
        setMode("idle");
      } else if (mode === "waypoint") addWaypoint(e.latlng.lat, e.latlng.lng);
      else if (mode === "obstacle") void injectObstacle(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

/** Fit the map to the mission whenever a different mission (or the first drones) load. */
function FitBounds({ points, fitKey }: { points: LatLng[]; fitKey: string }) {
  const map = useMap();
  const last = useRef("");
  useEffect(() => {
    if (!points.length || last.current === fitKey) return;
    last.current = fitKey;
    map.invalidateSize();
    map.fitBounds(L.latLngBounds(points), { padding: [50, 50], maxZoom: 17 });
  }, [map, points, fitKey]);
  return null;
}

export default function MapInner() {
  const { drones, detail, draft, dirty, planActive, colorOf, mode, obstacleRadius, pendingHome } = useMission();
  const tel = useTelemetryContext();

  const droneById = useMemo(() => new Map(drones.map((d) => [d.id, d])), [drones]);
  const assignmentByTask = useMemo(() => new Map(detail?.assignments.map((a) => [a.task_id, a]) ?? []), [detail]);
  const obstacles: Obstacle[] = useMemo(() => {
    const byId = new Map<number, Obstacle>();
    detail?.obstacles.forEach((o) => byId.set(o.id, o));
    if (tel.missionId === detail?.mission.id) tel.obstacles.forEach((o) => byId.set(o.id, o));
    return [...byId.values()];
  }, [detail, tel.obstacles, tel.missionId]);

  const fitPoints: LatLng[] = useMemo(
    () => [...drones.map((d) => [d.home_lat, d.home_lon] as LatLng), ...draft.map((w) => [w.lat, w.lon] as LatLng)],
    [drones, draft],
  );
  const fitKey = `${detail?.mission.id ?? "none"}:${drones.length > 0}`;
  const center: LatLng = fitPoints[0] ?? [12.9716, 77.5946];

  const liveDrones = drones.map((d) => tel.drones[d.id]).filter(Boolean);
  const flying = tel.running;
  const cursor = mode === "idle" ? "" : "map-crosshair";

  return (
    <div className={`map-dark relative h-full w-full ${cursor}`}>
      <MapContainer center={center} zoom={16} zoomSnap={0.25} className="h-full w-full" zoomControl>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          maxZoom={19}
        />
        <ClickHandler />
        <FitBounds points={fitPoints} fitKey={fitKey} />

        {/* obstacles */}
        {obstacles.map((o) => (
          <Circle
            key={`ob-${o.id}`}
            center={[o.lat, o.lon]}
            radius={o.radius_m}
            pathOptions={{ color: "#ef5350", fillColor: "#ef5350", fillOpacity: 0.28, weight: 2 }}
          >
            <Tooltip>Obstacle #{o.id} · {o.radius_m} m</Tooltip>
          </Circle>
        ))}

        {/* planned routes (dashed) — replaced by the live remaining route while a drone flies */}
        {planActive &&
          detail?.routes.map((r) => {
            const live = tel.drones[r.drone_id];
            if (flying && live && live.route.length > 1) return null;
            return (
              <Polyline
                key={`route-${r.drone_id}`}
                positions={r.polyline}
                pathOptions={{ color: colorOf(r.drone_id), weight: 3, opacity: 0.6, dashArray: "8 8" }}
              >
                <Tooltip sticky>{r.drone_name} · {r.length_m.toFixed(0)} m</Tooltip>
              </Polyline>
            );
          })}

        {/* flown trail + live remaining route */}
        {flying || liveDrones.some((d) => d.state !== "IDLE")
          ? liveDrones.map((d) => (
              <Polyline key={`trail-${d.id}`} positions={tel.trails[d.id] ?? []} pathOptions={{ color: colorOf(d.id), weight: 2, opacity: 0.35 }} />
            ))
          : null}
        {flying &&
          liveDrones.map((d) =>
            d.route.length > 1 ? (
              <Polyline key={`live-${d.id}`} positions={d.route} pathOptions={{ color: colorOf(d.id), weight: 3, opacity: 0.95 }} />
            ) : null,
          )}

        {/* home bases */}
        {drones.map((d) => (
          <Marker key={`home-${d.id}`} position={[d.home_lat, d.home_lon]} icon={homeIcon(colorOf(d.id))} zIndexOffset={-100}>
            <Tooltip>{d.name} · home base</Tooltip>
          </Marker>
        ))}

        {pendingHome && (
          <Marker position={[pendingHome.lat, pendingHome.lon]} icon={homeIcon("#e8ecf2")}>
            <Tooltip permanent>New drone home</Tooltip>
          </Marker>
        )}

        {/* waypoints */}
        {draft.map((w, i) => {
          const task = !dirty ? detail?.tasks[i] : undefined;
          const a = task ? assignmentByTask.get(task.id) : undefined;
          const owner = a ? droneById.get(a.drone_id) : undefined;
          const color = a && planActive ? colorOf(a.drone_id) : NEUTRAL;
          return (
            <Marker key={`wp-${i}-${w.lat}-${w.lon}`} position={[w.lat, w.lon]} icon={waypointIcon(i + 1, color)}>
              <Tooltip>
                <div>
                  <b>Waypoint {i + 1}</b> · {w.altitude_m} m · {w.payload_kg} kg
                  {a && planActive && owner && (
                    <div>→ {owner.name} (stop {a.order + 1}) · {a.predicted_energy_pct.toFixed(1)}% battery</div>
                  )}
                </div>
              </Tooltip>
            </Marker>
          );
        })}

        {/* live drones */}
        {liveDrones.map((d) => (
          <Marker
            key={`drone-${d.id}`}
            position={[d.lat, d.lon]}
            icon={droneIcon(colorOf(d.id), d.name.slice(-1), d.heading_deg, d.state === "AVOIDING" || d.state === "FAILSAFE" || d.state === "RETURN_TO_LAUNCH")}
            zIndexOffset={1000}
          >
            <Tooltip>
              <div>
                <b>{d.name}</b> · {STATE_LABEL[d.state] ?? d.state}
                <div>battery {d.battery_pct.toFixed(0)}% · alt {d.alt_m.toFixed(0)} m</div>
              </div>
            </Tooltip>
          </Marker>
        ))}
      </MapContainer>

      {mode !== "idle" && (
        <div className="pointer-events-none absolute left-1/2 top-3 z-[1000] -translate-x-1/2 rounded-full border border-line bg-panel/95 px-4 py-1.5 text-sm shadow">
          {mode === "waypoint"
            ? "＋ Click the map to add a waypoint"
            : mode === "home"
              ? "H Click the map to set the new drone's home base"
              : `⚠ Click the map to inject a ${obstacleRadius} m obstacle`}
        </div>
      )}
      {tel.status !== "open" && (
        <div className="absolute bottom-3 left-3 z-[1000] rounded-md border border-warn/60 bg-panel/95 px-3 py-1.5 text-xs text-warn">
          ▲ Live telemetry {tel.status === "connecting" ? "connecting…" : "disconnected — retrying"}
        </div>
      )}
    </div>
  );
}
