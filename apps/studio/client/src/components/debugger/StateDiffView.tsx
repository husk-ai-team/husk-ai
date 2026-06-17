import type { StateDiff } from "@/lib/api";

function fmt(v: unknown): string {
  if (typeof v === "string") return v;
  return JSON.stringify(v, null, 2);
}

export function StateDiffView({ diff }: { diff: StateDiff | null }) {
  if (!diff) {
    return <p className="text-xs text-muted-foreground">No state diff recorded for this node.</p>;
  }
  const added = Object.entries(diff.added ?? {});
  const removed = Object.entries(diff.removed ?? {});
  const changed = Object.entries(diff.changed ?? {});
  if (!added.length && !removed.length && !changed.length) {
    return <p className="text-xs text-muted-foreground">This node changed no state keys.</p>;
  }
  return (
    <div className="space-y-3 text-xs">
      {changed.map(([k, v]) => (
        <div key={`c-${k}`} className="rounded-md border border-amber-500/30 bg-amber-500/5 p-2.5">
          <div className="mb-1 font-mono text-[11px] text-amber-300">~ {k}</div>
          <pre className="overflow-x-auto whitespace-pre-wrap text-[11px] text-destructive/90">- {fmt(v.from)}</pre>
          <pre className="overflow-x-auto whitespace-pre-wrap text-[11px] text-emerald-300/90">+ {fmt(v.to)}</pre>
        </div>
      ))}
      {added.map(([k, v]) => (
        <div key={`a-${k}`} className="rounded-md border border-emerald-500/30 bg-emerald-500/5 p-2.5">
          <div className="mb-1 font-mono text-[11px] text-emerald-300">+ {k}</div>
          <pre className="overflow-x-auto whitespace-pre-wrap text-[11px] text-foreground/80">{fmt(v)}</pre>
        </div>
      ))}
      {removed.map(([k, v]) => (
        <div key={`r-${k}`} className="rounded-md border border-destructive/30 bg-destructive/5 p-2.5">
          <div className="mb-1 font-mono text-[11px] text-destructive">- {k}</div>
          <pre className="overflow-x-auto whitespace-pre-wrap text-[11px] text-foreground/60">{fmt(v)}</pre>
        </div>
      ))}
    </div>
  );
}
