import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { fmtCost, fmtDuration, fmtTokens, type Span } from "@/lib/api";
import {
  Bot,
  Cog,
  CornerDownRight,
  Hash,
  MessageCircle,
  User,
  Wrench,
} from "lucide-react";

interface InspectorProps {
  span: Span | null;
}

export function Inspector({ span }: InspectorProps) {
  if (!span) {
    return (
      <div className="flex h-full flex-col items-center justify-center px-6 text-center text-sm text-muted-foreground">
        <CornerDownRight className="mb-2 size-5 text-muted-foreground/60" />
        Click a span on the left to inspect.
      </div>
    );
  }

  const messages = extractMessages(span.input_inline);
  const choices = extractChoices(span.output_inline);
  const hasConversation = messages.length > 0 || choices.length > 0;

  const meta = {
    id: span.id,
    parent_span_id: span.parent_span_id,
    provider: span.provider,
    model: span.model,
    tokens_in: span.tokens_in,
    tokens_out: span.tokens_out,
    cost_usd: span.cost_usd,
    started_at: span.started_at,
    finished_at: span.finished_at,
  };

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border/30 px-4 py-3">
        <div className="flex items-start gap-2.5">
          <span
            className={`flex size-7 shrink-0 items-center justify-center rounded-md ${bgForKind(
              span.kind,
            )}`}
          >
            {iconForKind(span.kind)}
          </span>
          <div className="min-w-0">
            <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              {span.kind === "llm"
                ? "LLM call"
                : span.kind === "tool"
                  ? "Tool call"
                  : "Step"}
            </div>
            <div className="mt-0.5 truncate font-mono text-sm font-semibold">
              {span.name}
            </div>
          </div>
        </div>
        <div className="mt-2 flex flex-wrap gap-x-3.5 gap-y-1 text-[11px] text-muted-foreground">
          <Pill status={span.status} />
          {span.model && <KV k="model" v={span.model} />}
          {span.finished_at && span.started_at ? (
            <KV k="dur" v={fmtDuration(span.finished_at - span.started_at)} />
          ) : null}
          {(span.tokens_in || span.tokens_out) && (
            <KV k="tok" v={fmtTokens(span.tokens_in, span.tokens_out)} />
          )}
          {span.cost_usd ? <KV k="cost" v={fmtCost(span.cost_usd)} accent /> : null}
        </div>
      </div>

      <Tabs
        defaultValue={hasConversation ? "conversation" : "metadata"}
        className="flex flex-1 flex-col"
      >
        <TabsList className="mx-4 mt-3 self-start">
          {hasConversation && (
            <TabsTrigger value="conversation">
              <MessageCircle className="mr-1 size-3.5" />
              Conversation
            </TabsTrigger>
          )}
          <TabsTrigger value="metadata">
            <Hash className="mr-1 size-3.5" />
            Metadata
          </TabsTrigger>
          <TabsTrigger value="attrs">
            <Cog className="mr-1 size-3.5" />
            Attributes
          </TabsTrigger>
          <TabsTrigger value="raw">Raw</TabsTrigger>
        </TabsList>

        {hasConversation && (
          <TabsContent
            value="conversation"
            className="flex-1 overflow-y-auto px-4 pb-4"
          >
            <Conversation messages={messages} choices={choices} />
          </TabsContent>
        )}

        <TabsContent value="metadata" className="flex-1 overflow-y-auto px-4 pb-4">
          <CodeBlock value={JSON.stringify(meta, null, 2)} />
        </TabsContent>

        <TabsContent value="attrs" className="flex-1 overflow-y-auto px-4 pb-4">
          <CodeBlock value={JSON.stringify(span.attrs ?? {}, null, 2)} />
        </TabsContent>

        <TabsContent value="raw" className="flex-1 overflow-y-auto px-4 pb-4">
          <CodeBlock value={JSON.stringify(span, null, 2)} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function iconForKind(kind: string) {
  if (kind === "llm") return <Bot className="size-4 text-accent" />;
  if (kind === "tool") return <Wrench className="size-4 text-sky-400" />;
  return <Cog className="size-4 text-emerald-400" />;
}

function bgForKind(kind: string) {
  if (kind === "llm") return "bg-accent/15";
  if (kind === "tool") return "bg-sky-500/15";
  return "bg-emerald-500/15";
}

function KV({ k, v, accent }: { k: string; v: string; accent?: boolean }) {
  return (
    <span className="inline-flex items-baseline gap-1">
      <span className="uppercase text-[9px] tracking-wider text-muted-foreground/70">
        {k}
      </span>
      <span className={accent ? "text-accent" : "text-foreground"}>{v}</span>
    </span>
  );
}

function Pill({ status }: { status: string }) {
  const cls =
    status === "success"
      ? "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30"
      : status === "error" || status === "failed"
        ? "bg-destructive/15 text-destructive ring-1 ring-destructive/30"
        : "bg-accent/15 text-accent ring-1 ring-accent/30";
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider ${cls}`}
    >
      {status}
    </span>
  );
}

interface Message {
  role: string;
  content?: string;
  [k: string]: unknown;
}

function extractMessages(input: unknown): Message[] {
  if (!input || typeof input !== "object") return [];
  const v = input as { messages?: unknown };
  if (!Array.isArray(v.messages)) return [];
  return v.messages as Message[];
}

interface Choice {
  finish_reason?: string;
  "message.content"?: string;
  message?: { content?: string };
  [k: string]: unknown;
}

function extractChoices(output: unknown): Choice[] {
  if (!output || typeof output !== "object") return [];
  const v = output as { choices?: unknown };
  if (!Array.isArray(v.choices)) return [];
  return v.choices as Choice[];
}

function Conversation({
  messages,
  choices,
}: {
  messages: Message[];
  choices: Choice[];
}) {
  return (
    <div className="space-y-3 py-3">
      {messages.map((m, i) => (
        <Bubble key={`m-${i}`} role={m.role} content={pickContent(m)} />
      ))}
      {choices.map((c, i) => (
        <Bubble
          key={`c-${i}`}
          role="assistant"
          content={c["message.content"] || c.message?.content || ""}
          finishReason={c.finish_reason}
        />
      ))}
    </div>
  );
}

function pickContent(m: Message): string {
  if (typeof m.content === "string") return m.content;
  if (typeof m.arguments === "string") return m.arguments;
  const parts: string[] = [];
  if (typeof m.name === "string") parts.push(`name: ${m.name}`);
  if (typeof m.arguments === "string") parts.push(`args: ${m.arguments}`);
  if (typeof m.content === "string") parts.push(m.content);
  return parts.length ? parts.join("\n") : JSON.stringify(m);
}

function Bubble({
  role,
  content,
  finishReason,
}: {
  role: string;
  content: string;
  finishReason?: string;
}) {
  const { palette, icon, name } = bubbleStyle(role);
  return (
    <div className={`rounded-lg border px-4 py-3 ${palette}`}>
      <div className="mb-1.5 flex items-center justify-between text-[10px] uppercase tracking-[0.18em] opacity-70">
        <span className="flex items-center gap-1.5">
          {icon}
          {name}
        </span>
        {finishReason && (
          <span className="rounded bg-background/60 px-1.5 py-0.5 font-normal tracking-normal">
            {finishReason}
          </span>
        )}
      </div>
      <div className="whitespace-pre-wrap text-sm leading-relaxed">{content}</div>
    </div>
  );
}

function bubbleStyle(role: string) {
  switch (role) {
    case "user":
      return {
        palette: "border-border/30 bg-secondary/20 text-foreground",
        icon: <User className="size-3.5" />,
        name: "User",
      };
    case "assistant":
    case "choice":
      return {
        palette: "border-accent/30 bg-accent/10 text-foreground",
        icon: <Bot className="size-3.5" />,
        name: "Assistant",
      };
    case "system":
      return {
        palette: "border-emerald-500/30 bg-emerald-500/10 text-foreground",
        icon: <Cog className="size-3.5" />,
        name: "System",
      };
    case "tool":
      return {
        palette: "border-sky-500/30 bg-sky-500/10 text-foreground",
        icon: <Wrench className="size-3.5" />,
        name: "Tool",
      };
    default:
      return {
        palette: "border-border/30 bg-secondary/10 text-foreground",
        icon: <MessageCircle className="size-3.5" />,
        name: role,
      };
  }
}

function CodeBlock({ value }: { value: string }) {
  return (
    <SyntaxHighlighter
      language="json"
      style={vscDarkPlus}
      customStyle={{
        background: "rgba(0,0,0,0.25)",
        border: "1px solid rgba(48,54,61,0.6)",
        borderRadius: 8,
        padding: 12,
        margin: 0,
        fontSize: 12,
        lineHeight: 1.55,
      }}
      wrapLongLines
    >
      {value}
    </SyntaxHighlighter>
  );
}
