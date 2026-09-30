"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ModelInfo } from "@/lib/types";
import { ErrorBox, Spinner } from "./ui";

export function ModelTab() {
  const [info, setInfo] = useState<ModelInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setInfo(await api.modelInfo());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  if (loading && !info) return <Spinner label="Loading model metrics…" />;
  if (error) return <ErrorBox message={error} onRetry={load} />;
  if (!info) return null;

  const best = info.best_model ? info.models?.[info.best_model] : undefined;
  const importance = Object.entries(info.feature_importance ?? {});
  const maxImp = Math.max(...importance.map(([, v]) => v), 0.0001);

  return (
    <div className="space-y-4">
      {info.is_fallback && (
        <div className="rounded-md border border-warn/60 bg-warn/10 p-2 text-xs text-warn">
          ▲ The trained model artifact is missing — the linear heuristic fallback is active. Run <code>make train</code>.
        </div>
      )}
      <div className="rounded-md border border-line bg-panel p-3">
        <div className="text-[11px] uppercase tracking-wide text-muted">Best model (serving now)</div>
        <div className="text-lg font-semibold">{info.active_model}</div>
        <div className="text-[11px] text-muted">
          {info.selection_criterion ?? "—"} · {info.n_rows?.toLocaleString() ?? "?"} synthetic flight legs
          ({info.n_train?.toLocaleString()} train / {info.n_test?.toLocaleString()} test)
        </div>
      </div>

      {best && (
        <div className="grid grid-cols-3 gap-2">
          {[
            ["MAE", best.mae.toFixed(2), "% battery"],
            ["RMSE", best.rmse.toFixed(2), "% battery"],
            ["R²", best.r2.toFixed(3), "test set"],
          ].map(([k, v, u]) => (
            <div key={k} className="rounded-md border border-line bg-panel p-2 text-center">
              <div className="text-[11px] uppercase tracking-wide text-muted">{k}</div>
              <div className="text-xl font-semibold tabular-nums">{v}</div>
              <div className="text-[10px] text-muted">{u}</div>
            </div>
          ))}
        </div>
      )}

      {info.models && (
        <table className="w-full text-sm">
          <caption className="mb-1 text-left text-xs font-semibold text-muted">Model comparison (held-out test set)</caption>
          <thead className="text-[11px] uppercase tracking-wide text-muted">
            <tr><th className="text-left">Model</th><th className="text-right">MAE</th><th className="text-right">RMSE</th><th className="text-right">R²</th></tr>
          </thead>
          <tbody className="tabular-nums">
            {Object.entries(info.models).map(([name, m]) => (
              <tr key={name} className="border-t border-line">
                <td className="py-1 pr-2">{name.replace("Regressor", "")}{name === info.best_model && <span className="ml-1 text-accent">★</span>}</td>
                <td className="text-right">{m.mae.toFixed(2)}</td>
                <td className="text-right">{m.rmse.toFixed(2)}</td>
                <td className="text-right">{m.r2.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {importance.length > 0 && (
        <div>
          <h4 className="mb-2 text-xs font-semibold text-muted">Feature importance</h4>
          <ul className="space-y-1.5">
            {importance.map(([name, v]) => (
              <li key={name} className="flex items-center gap-2 text-xs">
                <span className="w-32 shrink-0 truncate text-muted">{name}</span>
                <div className="h-2.5 flex-1 overflow-hidden rounded bg-line">
                  <div className="h-full rounded-r bg-accent" style={{ width: `${(v / maxImp) * 100}%` }} />
                </div>
                <span className="w-12 text-right tabular-nums">{(v * 100).toFixed(1)}%</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="text-[11px] text-muted">
        The model is an advisory cost estimator: a distance-only fallback always exists. Open <code>notebooks/01_energy_model.ipynb</code> for the full analysis.
      </p>
    </div>
  );
}
