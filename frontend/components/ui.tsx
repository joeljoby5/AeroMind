"use client";

import type { ReactNode } from "react";
import { STATE_LABEL, stateTone } from "@/lib/colors";

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-muted text-sm" role="status">
      <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-line border-t-accent" />
      {label ?? "Loading…"}
    </div>
  );
}

export function ErrorBox({ message, onRetry, onDismiss }: { message: string; onRetry?: () => void; onDismiss?: () => void }) {
  return (
    <div role="alert" className="flex items-start gap-2 rounded-md border border-bad/60 bg-bad/10 px-3 py-2 text-sm">
      <span aria-hidden>✖</span>
      <span className="flex-1 break-words">{message}</span>
      {onRetry && (
        <button className="underline" onClick={onRetry}>Retry</button>
      )}
      {onDismiss && (
        <button aria-label="Dismiss" className="text-muted hover:text-ink" onClick={onDismiss}>×</button>
      )}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="rounded-md border border-dashed border-line p-4 text-center text-sm text-muted">{children}</div>;
}

const TONE: Record<string, string> = {
  neutral: "border-line text-muted",
  active: "border-accent/70 text-accent",
  warn: "border-warn/70 text-warn",
  bad: "border-bad/80 bg-bad/15 text-bad",
};
const GLYPH: Record<string, string> = { neutral: "○", active: "▶", warn: "▲", bad: "✖" };

export function StateBadge({ state }: { state: string }) {
  const tone = stateTone(state);
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-[11px] font-medium ${TONE[tone]}`}>
      <span aria-hidden>{GLYPH[tone]}</span>
      {STATE_LABEL[state] ?? state}
    </span>
  );
}

export function Card({ title, children, right }: { title?: string; children: ReactNode; right?: ReactNode }) {
  return (
    <section className="rounded-lg border border-line bg-panel2 p-3">
      {(title || right) && (
        <header className="mb-2 flex items-center justify-between">
          {title && <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">{title}</h3>}
          {right}
        </header>
      )}
      {children}
    </section>
  );
}

export function Btn({
  children, onClick, disabled, tone = "default", active, title, className = "", type = "button",
}: {
  children: ReactNode; onClick?: () => void; disabled?: boolean; title?: string; className?: string;
  tone?: "default" | "primary" | "danger"; active?: boolean; type?: "button" | "submit";
}) {
  const base = "inline-flex items-center justify-center gap-1.5 rounded-md border px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-40";
  const tones = {
    default: "border-line bg-panel hover:border-muted",
    primary: "border-accent bg-accent text-white hover:brightness-110",
    danger: "border-bad/70 bg-bad/10 text-bad hover:bg-bad/20",
  } as const;
  return (
    <button
      type={type}
      title={title}
      onClick={onClick}
      disabled={disabled}
      aria-pressed={active}
      className={`${base} ${tones[tone]} ${active ? "ring-2 ring-accent" : ""} ${className}`}
    >
      {children}
    </button>
  );
}
