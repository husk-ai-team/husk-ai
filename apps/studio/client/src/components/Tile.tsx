// Lovable-style card primitive. Two sizes:
//   <Tile> — default data tile, ~p-6
//   <Tile size="hero"> — big hero with extra padding, larger numbers
//
// Optional `href` makes the whole tile a clickable link (uses <a> for cross-app
// navigation; pages should wrap with wouter's <Link> when navigating in-app).

import { ArrowUpRight } from "lucide-react";
import type { ReactNode } from "react";

interface TileProps {
  icon?: ReactNode;
  label?: string;
  href?: string;
  onClick?: () => void;
  size?: "default" | "hero" | "wide";
  className?: string;
  children?: ReactNode;
  rightLabel?: ReactNode;
}

export function Tile({
  icon,
  label,
  href,
  onClick,
  size = "default",
  className = "",
  children,
  rightLabel,
}: TileProps) {
  const padding =
    size === "hero" ? "p-8 md:p-10" : size === "wide" ? "p-6 md:p-7" : "p-6";
  const cls = `relative group rounded-xl border border-border/30 bg-secondary/10 ${padding} hover:border-accent/40 hover:bg-secondary/15 transition-colors duration-200 ${className}`;
  const inner = (
    <>
      {(label || rightLabel) && (
        <div className="mb-3 flex items-center justify-between gap-2">
          {label && (
            <div className="inline-flex items-center gap-1.5 text-xs uppercase tracking-[0.16em] text-muted-foreground">
              {icon}
              {label}
            </div>
          )}
          {rightLabel}
        </div>
      )}
      {children}
      {(href || onClick) && (
        <ArrowUpRight className="absolute top-4 right-4 size-4 text-muted-foreground/40 group-hover:text-accent transition-colors" />
      )}
    </>
  );
  if (href) {
    return (
      <a href={href} className={cls}>
        {inner}
      </a>
    );
  }
  if (onClick) {
    return (
      <button type="button" onClick={onClick} className={`${cls} text-left w-full`}>
        {inner}
      </button>
    );
  }
  return <div className={cls}>{inner}</div>;
}

interface StatProps {
  value: ReactNode;
  sub?: ReactNode;
  accent?: boolean;
  size?: "hero" | "default";
}

export function StatNumber({ value, sub, accent, size = "default" }: StatProps) {
  const sz =
    size === "hero"
      ? "text-5xl md:text-6xl"
      : "text-3xl md:text-4xl";
  return (
    <>
      <div
        className={`${sz} font-bold tabular-nums tracking-[-0.02em] ${
          accent ? "text-accent" : "text-foreground"
        }`}
      >
        {value}
      </div>
      {sub && <div className="mt-2 text-xs text-muted-foreground">{sub}</div>}
    </>
  );
}
