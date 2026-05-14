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
          events.slice(-20).reverse().map((ev, index) => {
            const isLatest = index === 0;
            return (
              <div key={`${ev.id}-${index}`} className={`relative pl-4 border-l pb-2 last:pb-0 ${isLatest ? 'border-warn animate-pulse-soft' : 'border-line/50'}`}>
                <div className="absolute -left-[5px] top-1 bg-background">
                  {ev.type === "AGENT_THOUGHT" && <Lightbulb className={`h-2.5 w-2.5 ${isLatest ? 'text-warn' : 'text-hud'}`} />}
                  {ev.type === "AGENT_TOOL_CALL" && <Play className={`h-2.5 w-2.5 ${isLatest ? 'text-warn' : 'text-warn'}`} />}
                  {ev.type === "AGENT_TOOL_RESULT" && <CheckCircle2 className={`h-2.5 w-2.5 ${isLatest ? 'text-warn' : 'text-success'}`} />}
                  {ev.type === "AGENT_PLAN_UPDATE" && <CheckCircle2 className={`h-2.5 w-2.5 ${isLatest ? 'text-warn' : 'text-success'}`} />}
                  {ev.type === "agent_tool" && <Wrench className={`h-2.5 w-2.5 ${isLatest ? 'text-warn' : 'text-hud'}`} />}
                </div>
                <div className="flex items-center justify-between gap-2">
                  <span className={`text-[10px] uppercase tracking-[0.16em] font-semibold ${isLatest ? 'text-warn' : 'text-foreground'}`}>
                    {ev.type.replace("AGENT_", "").replace("_", " ")}
                  </span>
                  <span className="text-[9px] text-muted-foreground">{ev.at}</span>
                </div>
                {ev.type === "AGENT_THOUGHT" && (
                  <p className={`mt-1 text-[11px] italic leading-relaxed ${isLatest ? 'text-foreground' : 'text-muted-foreground'}`}>
                    "{ev.text}"
                  </p>
                )}
                {ev.type === "AGENT_TOOL_CALL" && (
                  <div className={`mt-1 p-1.5 rounded-sm border ${isLatest ? 'bg-warn/10 border-warn/30' : 'bg-hud/5 border-hud/10'}`}>
                    <div className={`text-[10px] font-semibold ${isLatest ? 'text-warn' : 'text-hud'}`}>{ev.action}</div>
                    <div className="text-[9px] text-muted-foreground mt-0.5 whitespace-pre-wrap break-words">
                      {JSON.stringify(ev.args, null, 2)}
                    </div>
                  </div>
                )}
                {ev.type === "AGENT_TOOL_RESULT" && (
                  <p className={`mt-1 text-[11px] line-clamp-3 ${isLatest ? 'text-foreground' : 'text-muted-foreground'}`}>
                    {ev.observation}
                  </p>
                )}
                {ev.type === "AGENT_PLAN_UPDATE" && (
                  <p className={`mt-1 text-[11px] ${isLatest ? 'text-warn' : 'text-success'}`}>
                    Plan status: {ev.status}
                  </p>
                )}
                {ev.type === "agent_tool" && (
                  <div className="mt-1">
                    <div className={`text-[10px] font-semibold ${isLatest ? 'text-warn' : 'text-hud'}`}>{ev.action}</div>
                    <p className={`mt-0.5 text-[11px] line-clamp-2 ${isLatest ? 'text-foreground' : 'text-muted-foreground'}`}>
                      {ev.observation}
                    </p>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </Panel>
  );
}
