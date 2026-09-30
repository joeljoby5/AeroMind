"use client";

import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useMission } from "@/context/MissionContext";
import { BASELINE_COLOR, ML_COLOR } from "@/lib/colors";
import { Empty, ErrorBox, Spinner } from "./ui";

const TICK = { fill: "#9aa5b5", fontSize: 12 };

function Chart({ title, unit, data, digits }: { title: string; unit: string; data: { name: string; value: number; color: string }[]; digits: number }) {
  return (
    <div>
      <h4 className="mb-1 text-xs font-semibold text-muted">{title}</h4>
      <div className="h-44" role="img" aria-label={`${title}: ${data.map((d) => `${d.name} ${d.value.toFixed(digits)} ${unit}`).join(", ")}`}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 18, right: 8, left: -12, bottom: 0 }} barCategoryGap="28%">
            <CartesianGrid vertical={false} stroke="#2a323f" />
            <XAxis dataKey="name" tick={TICK} axisLine={false} tickLine={false} />
            <YAxis tick={TICK} axisLine={false} tickLine={false} allowDecimals={digits > 0} />
            <Tooltip
              cursor={{ fill: "rgba(255,255,255,0.05)" }}
              contentStyle={{ background: "#1b212b", border: "1px solid #2a323f", borderRadius: 6, color: "#e8ecf2" }}
              formatter={(v) => [`${Number(v).toFixed(digits)} ${unit}`, title]}
            />
            <Bar dataKey="value" radius={[4, 4, 0, 0]} isAnimationActive={false}>
              {data.map((d) => (
                <Cell key={d.name} fill={d.color} />
              ))}
              <LabelList dataKey="value" position="top" formatter={(v: unknown) => Number(v).toFixed(digits)} fill="#e8ecf2" fontSize={12} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function ComparisonTab() {
  const { compare, compareError, busy, detail, planActive } = useMission();

  if (busy === "plan") return <Spinner label="Comparing ML vs baseline…" />;
  if (compareError && !compare) return <ErrorBox message={compareError} />;
  if (!compare || !detail || !planActive) return <Empty>Press Plan to compare AI energy-aware allocation with the distance-only baseline.</Empty>;

  const { ml, baseline } = compare;
  const energy = [
    { name: "AI energy-aware", value: ml.actual_energy_pct, color: ML_COLOR },
    { name: "Distance baseline", value: baseline.actual_energy_pct, color: BASELINE_COLOR },
  ];
  const violations = [
    { name: "AI energy-aware", value: ml.infeasible_assignments, color: ML_COLOR },
    { name: "Distance baseline", value: baseline.infeasible_assignments, color: BASELINE_COLOR },
  ];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-md border border-line bg-panel p-3">
          <div className="text-[11px] uppercase tracking-wide text-muted">Energy saved by AI</div>
          <div className="text-2xl font-semibold tabular-nums">{compare.energy_saving_pct.toFixed(1)}%</div>
          <div className="text-[11px] text-muted">vs distance-only allocation</div>
        </div>
        <div className="rounded-md border border-line bg-panel p-3">
          <div className="text-[11px] uppercase tracking-wide text-muted">Unsafe assignments avoided</div>
          <div className="text-2xl font-semibold tabular-nums">{compare.infeasible_avoided}</div>
          <div className="text-[11px] text-muted">would break the 15% battery reserve</div>
        </div>
      </div>

      <div className="flex gap-4 text-xs" aria-label="Legend">
        <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded-sm" style={{ background: ML_COLOR }} />AI energy-aware (ML)</span>
        <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded-sm" style={{ background: BASELINE_COLOR }} />Distance baseline</span>
      </div>

      <Chart title="Total mission energy" unit="% battery" data={energy} digits={1} />
      <Chart title="Battery-infeasible assignments" unit="" data={violations} digits={0} />

      <table className="w-full text-sm">
        <caption className="mb-1 text-left text-xs font-semibold text-muted">Table view</caption>
        <thead className="text-[11px] uppercase tracking-wide text-muted">
          <tr><th className="text-left">Metric</th><th className="text-right">AI (ML)</th><th className="text-right">Baseline</th></tr>
        </thead>
        <tbody className="tabular-nums">
          {[
            ["Predicted energy (%)", ml.predicted_energy_pct, baseline.predicted_energy_pct],
            ["Actual energy (%)", ml.actual_energy_pct, baseline.actual_energy_pct],
            ["Infeasible assignments", ml.infeasible_assignments, baseline.infeasible_assignments],
            ["Tasks assigned", ml.assigned, baseline.assigned],
            ["Tasks unassigned", ml.unassigned, baseline.unassigned],
          ].map(([label, a, b]) => (
            <tr key={label as string} className="border-t border-line">
              <td className="py-1">{label}</td>
              <td className="py-1 text-right">{typeof a === "number" && !Number.isInteger(a) ? a.toFixed(1) : a}</td>
              <td className="py-1 text-right">{typeof b === "number" && !Number.isInteger(b) ? b.toFixed(1) : b}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-[11px] text-muted">
        “Actual” energy scores both plans against the noise-free physics model, not the ML model that made them, so the
        comparison is not self-flattering. Model: {compare.model}.
      </p>
    </div>
  );
}
