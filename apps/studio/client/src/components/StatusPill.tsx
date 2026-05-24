export function StatusPill({ status }: { status: string }) {
  const cls =
    status === "success"
      ? "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30"
      : status === "error" || status === "failed"
        ? "bg-destructive/15 text-destructive ring-1 ring-destructive/30"
        : "bg-accent/15 text-accent ring-1 ring-accent/30";
  return (
    <span
      className={`inline-block rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${cls}`}
    >
      {status}
    </span>
  );
}

export function FrameworkBadge({ framework }: { framework: string }) {
  return (
    <span className="rounded-md border border-border/40 bg-secondary/30 px-2 py-0.5 font-mono text-[11px] text-muted-foreground">
      {framework}
    </span>
  );
}

export function FrameworkDot({ framework }: { framework: string }) {
  const color = framework.includes("langgraph")
    ? "bg-emerald-400"
    : framework.includes("cursor")
      ? "bg-destructive"
      : "bg-accent";
  return <span className={`inline-block size-2 rounded-full ${color}`} />;
}
