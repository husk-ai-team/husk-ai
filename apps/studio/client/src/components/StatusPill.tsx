export function StatusPill({ status }: { status: string }) {
  // Monochrome: error is the loud, inverted ink chip; success is quiet; the rest
  // sit in between. Severity is carried by fill and contrast, not hue.
  const cls =
    status === "success"
      ? "bg-secondary text-muted-foreground ring-1 ring-border"
      : status === "error" || status === "failed"
        ? "bg-foreground text-background"
        : "bg-card text-foreground ring-1 ring-border";
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
    <span className="rounded-md border border-border bg-secondary px-2 py-0.5 font-mono text-[11px] text-muted-foreground">
      {framework}
    </span>
  );
}

export function FrameworkDot({ framework: _framework }: { framework: string }) {
  // Monochrome: a single neutral marker. Frameworks are distinguished by their
  // label, not by colour.
  return <span className="inline-block size-2 rounded-full bg-muted-foreground/70" />;
}
