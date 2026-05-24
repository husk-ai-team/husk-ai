import { AlertTriangle, Check, Hourglass, ShieldOff } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import {
  decideCursorEvent,
  listCursorEvents,
  summarizeCursorEvent,
  type CursorEvent,
  type CursorPermission,
} from "@/lib/api";

const POLL_MS = 1500;

export function CursorBanner() {
  const [pending, setPending] = useState<CursorEvent[]>([]);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const tick = () =>
      listCursorEvents("pending")
        .then((p) => alive && setPending(p))
        .catch(() => {});
    tick();
    const t = setInterval(tick, POLL_MS);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  if (pending.length === 0) return null;
  const first = pending[0];

  const decide = async (id: string, perm: CursorPermission) => {
    setBusy(id);
    const label = perm === "allow" ? "Allowed" : perm === "deny" ? "Denied" : "Asked";
    try {
      await decideCursorEvent(id, perm);
      const remaining = await listCursorEvents("pending");
      setPending(remaining);
      toast.success(`${label}: ${first.hook}`);
    } catch (e) {
      toast.error(`Failed: ${e}`);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="border-b border-destructive/40 bg-gradient-to-r from-destructive/15 via-destructive/10 to-destructive/15">
      <div className="px-6 md:px-12 max-w-6xl mx-auto flex flex-wrap items-center gap-x-5 gap-y-3 py-3.5">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-destructive/20 text-destructive">
          <AlertTriangle className="size-5" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 text-sm font-semibold">
            Cursor needs you
            {pending.length > 1 && (
              <span className="rounded-full bg-destructive/20 px-2 py-0.5 text-[10px] font-bold text-destructive">
                +{pending.length - 1} more
              </span>
            )}
          </div>
          <div className="mt-0.5 flex flex-wrap items-baseline gap-x-2 gap-y-1 text-xs">
            <span className="rounded-md border border-border/40 bg-background/40 px-2 py-0.5 font-mono text-[11px] text-muted-foreground">
              {first.hook}
            </span>
            <code className="truncate font-mono text-[11px]">
              {summarizeCursorEvent(first)}
            </code>
          </div>
        </div>
        <div className="flex shrink-0 gap-2">
          <Btn
            onClick={() => decide(first.id, "allow")}
            variant="allow"
            disabled={busy === first.id}
            icon={<Check className="size-3.5" />}
          >
            Allow
          </Btn>
          <Btn
            onClick={() => decide(first.id, "deny")}
            variant="deny"
            disabled={busy === first.id}
            icon={<ShieldOff className="size-3.5" />}
          >
            Deny
          </Btn>
          <Btn
            onClick={() => decide(first.id, "ask")}
            variant="ask"
            disabled={busy === first.id}
            icon={<Hourglass className="size-3.5" />}
          >
            Ask
          </Btn>
        </div>
      </div>
    </div>
  );
}

function Btn({
  onClick,
  variant,
  disabled,
  icon,
  children,
}: {
  onClick: () => void;
  variant: "allow" | "deny" | "ask";
  disabled?: boolean;
  icon?: React.ReactNode;
  children: React.ReactNode;
}) {
  const cls =
    variant === "allow"
      ? "bg-emerald-500/20 text-emerald-200 hover:bg-emerald-500/30 ring-1 ring-emerald-500/40"
      : variant === "deny"
        ? "bg-destructive text-white hover:bg-destructive/90"
        : "border border-border/50 bg-background/40 text-foreground hover:bg-secondary/30";
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${cls}`}
    >
      {icon}
      {children}
    </button>
  );
}
