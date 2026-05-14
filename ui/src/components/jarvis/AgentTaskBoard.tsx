import { CheckCircle2, ChevronRight, Play, Wrench, Circle, Lightbulb } from "lucide-react";
import { Panel } from "./Panel";

export type AgentEvent = {
  id: string;
  type: "AGENT_THOUGHT" | "AGENT_TOOL_CALL" | "AGENT_TOOL_RESULT" | "AGENT_PLAN_UPDATE" | "agent_tool";
  text?: string;
  action?: string;
  args?: Record<string, unknown>;
  observation?: string;
  status?: string;
  step?: number;
  at: string;
};

export function AgentTaskBoard({ events = [] }: { events: AgentEvent[] }) {
  return (
    <Panel title="Autonomous Task Board" status={`${events.length} events`}>
      <div className="space-y-3 max-h-[360px] overflow-y-auto pr-2">
        {events.length === 0 ? (
          <div className="text-[11px] text-muted-foreground/60 italic py-2">Agent is standing by.</div>
        ) : (
          events.slice(-20).reverse().map((ev, index) => (
            <div key={`${ev.id}-${index}`} className="relative pl-4 border-l border-line/50 pb-2 last:pb-0">
              <div className="absolute -left-[5px] top-1 bg-background">
                {ev.type === "AGENT_THOUGHT" && <Lightbulb className="h-2.5 w-2.5 text-hud" />}
                {ev.type === "AGENT_TOOL_CALL" && <Play className="h-2.5 w-2.5 text-warn" />}
                {ev.type === "AGENT_TOOL_RESULT" && <CheckCircle2 className="h-2.5 w-2.5 text-success" />}
                {ev.type === "AGENT_PLAN_UPDATE" && <CheckCircle2 className="h-2.5 w-2.5 text-success" />}
                {ev.type === "agent_tool" && <Wrench className="h-2.5 w-2.5 text-hud" />}
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-[10px] uppercase tracking-[0.16em] font-semibold text-foreground">
                  {ev.type.replace("AGENT_", "").replace("_", " ")}
                </span>
                <span className="text-[9px] text-muted-foreground">{ev.at}</span>
              </div>
              {ev.type === "AGENT_THOUGHT" && (
                <p className="mt-1 text-[11px] text-muted-foreground italic leading-relaxed">
                  "{ev.text}"
                </p>
              )}
              {ev.type === "AGENT_TOOL_CALL" && (
                <div className="mt-1 bg-hud/5 p-1.5 rounded-sm border border-hud/10">
                  <div className="text-[10px] text-hud font-semibold">{ev.action}</div>
                  <div className="text-[9px] text-muted-foreground mt-0.5 whitespace-pre-wrap break-words">
                    {JSON.stringify(ev.args, null, 2)}
                  </div>
                </div>
              )}
              {ev.type === "AGENT_TOOL_RESULT" && (
                <p className="mt-1 text-[11px] text-muted-foreground line-clamp-3">
                  {ev.observation}
                </p>
              )}
              {ev.type === "AGENT_PLAN_UPDATE" && (
                <p className="mt-1 text-[11px] text-success">
                  Plan status: {ev.status}
                </p>
              )}
              {ev.type === "agent_tool" && (
                <div className="mt-1">
                  <div className="text-[10px] text-hud font-semibold">{ev.action}</div>
                  <p className="mt-0.5 text-[11px] text-muted-foreground line-clamp-2">
                    {ev.observation}
                  </p>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </Panel>
  );
}
