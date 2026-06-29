import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";

import { StateDiffView } from "@/components/debugger/StateDiffView";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { fmtCost, fmtDuration, fmtTokens, type GraphNode } from "@/lib/api";
import { AlertTriangle, Bot, CornerDownRight, Wrench } from "lucide-react";

export function NodeContextPanel({ node }: { node: GraphNode | null }) {
  if (!node) {
    return (
      <div className="flex h-full flex-col items-center justify-center px-6 text-center text-sm text-muted-foreground">
        <CornerDownRight className="mb-2 size-5 text-muted-foreground/60" />
        Click a node in the graph to inspect its full context.
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border/30 px-4 py-3">
        <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
          Graph node
        </div>
        <div className="mt-0.5 flex items-center gap-2 font-mono text-sm font-semibold">
          {node.name}
          {node.is_failure_point && <AlertTriangle className="size-4 text-destructive" />}
        </div>
        <div className="mt-2 flex flex-wrap gap-x-3.5 gap-y-1 text-[11px] text-muted-foreground">
          <StatusPill status={node.status} />
          {node.duration_ms != null && <KV k="dur" v={fmtDuration(node.duration_ms)} />}
          {(node.tokens_in || node.tokens_out) && (
            <KV k="tok" v={fmtTokens(node.tokens_in, node.tokens_out)} />
          )}
          {node.cost_usd ? <KV k="cost" v={fmtCost(node.cost_usd)} accent /> : null}
        </div>
      </div>

      <Tabs defaultValue="state" className="flex flex-1 flex-col">
        <TabsList className="mx-4 mt-3 self-start">
          <TabsTrigger value="state">State diff</TabsTrigger>
          {node.model_calls.length > 0 && <TabsTrigger value="model">Model</TabsTrigger>}
          {node.tool_calls.length > 0 && <TabsTrigger value="tools">Tools</TabsTrigger>}
          <TabsTrigger value="io">In / Out</TabsTrigger>
          {(node.error || node.traceback) && <TabsTrigger value="error">Error</TabsTrigger>}
        </TabsList>

        <TabsContent value="state" className="flex-1 overflow-y-auto px-4 pb-4 pt-3">
          <StateDiffView diff={node.state_diff} />
        </TabsContent>

        {node.model_calls.length > 0 && (
          <TabsContent value="model" className="flex-1 overflow-y-auto px-4 pb-4 pt-3">
            {node.model_calls.map((m) => (
              <div key={m.span_id} className="mb-4">
                <div className="mb-1.5 flex items-center gap-1.5 text-[11px] text-muted-foreground">
                  <Bot className="size-3.5 text-accent" />
                  {m.model || "model"} · {fmtTokens(m.tokens_in, m.tokens_out)} tok
                </div>
                <Labeled label="prompt">
                  <Code value={toText(m.prompt)} />
                </Labeled>
                <Labeled label="response">
                  <Code value={toText(m.response)} />
                </Labeled>
              </div>
            ))}
          </TabsContent>
        )}

        {node.tool_calls.length > 0 && (
          <TabsContent value="tools" className="flex-1 overflow-y-auto px-4 pb-4 pt-3">
            {node.tool_calls.map((t) => (
              <div key={t.span_id} className="mb-4">
                <div className="mb-1.5 flex items-center gap-1.5 text-[11px] text-muted-foreground">
                  <Wrench className="size-3.5 text-foreground" />
                  {t.name}
                </div>
                <Labeled label="args">
                  <Code value={toText(t.args)} />
                </Labeled>
                <Labeled label="result">
                  <Code value={toText(t.error ?? t.result)} />
                </Labeled>
              </div>
            ))}
          </TabsContent>
        )}

        <TabsContent value="io" className="flex-1 overflow-y-auto px-4 pb-4 pt-3">
          <Labeled label="state before">
            <Code value={toText(node.state_before)} />
          </Labeled>
          <Labeled label="state after">
            <Code value={toText(node.state_after)} />
          </Labeled>
        </TabsContent>

        {(node.error || node.traceback) && (
          <TabsContent value="error" className="flex-1 overflow-y-auto px-4 pb-4 pt-3">
            {node.error && <Code value={toText(node.error)} />}
            {node.traceback && (
              <Labeled label="traceback">
                <Code value={node.traceback} />
              </Labeled>
            )}
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}

function toText(v: unknown): string {
  if (v == null) return "—";
  if (typeof v === "string") return v;
  return JSON.stringify(v, null, 2);
}

function Labeled({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mb-3">
      <div className="mb-1 text-[9px] uppercase tracking-wider text-muted-foreground/70">
        {label}
      </div>
      {children}
    </div>
  );
}

function Code({ value }: { value: string }) {
  return (
    <SyntaxHighlighter
      language="json"
      style={vscDarkPlus}
      customStyle={{
        background: "rgba(0,0,0,0.25)",
        border: "1px solid rgba(48,54,61,0.6)",
        borderRadius: 8,
        padding: 10,
        margin: 0,
        fontSize: 11,
        lineHeight: 1.5,
      }}
      wrapLongLines
    >
      {value}
    </SyntaxHighlighter>
  );
}

function KV({ k, v, accent }: { k: string; v: string; accent?: boolean }) {
  return (
    <span className="inline-flex items-baseline gap-1">
      <span className="uppercase text-[9px] tracking-wider text-muted-foreground/70">{k}</span>
      <span className={accent ? "text-accent" : "text-foreground"}>{v}</span>
    </span>
  );
}

function StatusPill({ status }: { status: string }) {
  const cls =
    status === "success"
      ? "bg-secondary text-muted-foreground ring-1 ring-border"
      : status === "error"
        ? "bg-destructive/15 text-destructive ring-1 ring-destructive/30"
        : status === "skipped"
          ? "bg-secondary/40 text-muted-foreground ring-1 ring-border/40"
          : "bg-accent/15 text-accent ring-1 ring-accent/30";
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider ${cls}`}>
      {status}
    </span>
  );
}
