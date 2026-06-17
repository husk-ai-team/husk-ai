import { useState } from "react";
import { toast } from "sonner";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { analyzeRun, applyDebugFix, type DebugReportRow } from "@/lib/api";
import { Bug, Check, Loader2, Sparkles, Wand2 } from "lucide-react";
import { Link } from "wouter";

interface DebugReportCardProps {
  runId: string;
  report: DebugReportRow | null;
  hasKey: boolean;
  onChanged: () => void;
}

export function DebugReportCard({ runId, report, hasKey, onChanged }: DebugReportCardProps) {
  const [busy, setBusy] = useState(false);

  const analyze = async () => {
    setBusy(true);
    try {
      await analyzeRun(runId);
      toast.success("Debug analysis complete");
      onChanged();
    } catch (e) {
      toast.error(`Analysis failed: ${String(e)}`);
    } finally {
      setBusy(false);
    }
  };

  if (!report) {
    return (
      <div className="rounded-lg border border-border/40 bg-secondary/10 p-3">
        <div className="mb-2 flex items-center gap-1.5 text-[10px] uppercase tracking-[0.16em] text-muted-foreground/80">
          <Bug className="size-3.5 text-accent" />
          Automatic debugger
        </div>
        {hasKey ? (
          <>
            <p className="mb-2.5 text-[11px] leading-relaxed text-muted-foreground">
              Send this run's failure-focused trace to your configured model and get a
              localized root cause and a proposed fix.
            </p>
            <button
              type="button"
              onClick={analyze}
              disabled={busy}
              className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-accent px-3 py-2 text-sm font-semibold text-white hover:bg-accent/90 disabled:opacity-60"
            >
              {busy ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
              Analyze this run
            </button>
          </>
        ) : (
          <p className="text-[11px] leading-relaxed text-muted-foreground">
            Add an API key in{" "}
            <Link href="/settings" className="text-accent hover:underline">
              Settings
            </Link>{" "}
            to enable the automatic debugger (your key stays local).
          </p>
        )}
      </div>
    );
  }

  const r = report.report;
  return (
    <div className="rounded-lg border border-accent/30 bg-accent/5 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.16em] text-accent">
          <Bug className="size-3.5" />
          Debugger · {report.confidence}
        </span>
        <button
          type="button"
          onClick={analyze}
          disabled={busy}
          className="text-[10px] text-muted-foreground hover:text-accent disabled:opacity-60"
        >
          {busy ? "…" : "re-run"}
        </button>
      </div>

      <Field label="failure">
        <span className="font-mono text-foreground">
          {r.failure_localization.node_id ?? "—"}
        </span>{" "}
        <span className="text-muted-foreground">· {r.failure_class}</span>
      </Field>
      <Field label="root cause">{r.root_cause}</Field>

      {r.evidence.length > 0 && (
        <Field label="evidence">
          <ul className="list-disc pl-4">
            {r.evidence.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </Field>
      )}

      <Field label="proposed fix">{r.proposed_fix.summary}</Field>
      {r.proposed_fix.diff && (
        <pre className="mt-1 max-h-48 overflow-auto rounded-md border border-border/40 bg-background/60 p-2 text-[10px] leading-snug">
          {r.proposed_fix.diff}
        </pre>
      )}
      <p className="mt-1 text-[10px] italic text-muted-foreground">{r.proposed_fix.rationale}</p>

      {r.missing_information.length > 0 && (
        <Field label="missing info">
          <ul className="list-disc pl-4">
            {r.missing_information.map((m, i) => (
              <li key={i}>{m}</li>
            ))}
          </ul>
        </Field>
      )}

      {r.proposed_fix.diff && !report.applied && (
        <ApplyFixButton runId={runId} reportId={report.id} onChanged={onChanged} />
      )}
      {report.applied && (
        <div className="mt-3 inline-flex items-center gap-1.5 text-[11px] text-emerald-300">
          <Check className="size-3.5" /> Fix applied (backup saved alongside the file)
        </div>
      )}
    </div>
  );
}

function ApplyFixButton({
  runId,
  reportId,
  onChanged,
}: {
  runId: string;
  reportId: string;
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const apply = async () => {
    setBusy(true);
    try {
      const res = await applyDebugFix(runId, reportId);
      toast.success(`Applied to ${res.path}`);
      onChanged();
    } catch (e) {
      toast.error(`Apply failed: ${String(e)}`);
    } finally {
      setBusy(false);
    }
  };
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <button
          type="button"
          className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-md border border-accent/50 px-3 py-2 text-sm font-semibold text-accent hover:bg-accent/10"
        >
          <Wand2 className="size-4" />
          Apply fix to source
        </button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Apply this fix to your source?</AlertDialogTitle>
          <AlertDialogDescription>
            Husk will write the proposed unified diff to the agent's source file and
            save a <code>.husk-bak</code> backup next to it. The diff must apply
            cleanly or nothing is written. This is the one step where the debugger
            edits your code — review the diff above first.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={apply} disabled={busy}>
            {busy ? "Applying…" : "Apply fix"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mt-2 text-[11px] leading-relaxed">
      <div className="text-[9px] uppercase tracking-wider text-muted-foreground/70">{label}</div>
      <div className="text-foreground/90">{children}</div>
    </div>
  );
}
