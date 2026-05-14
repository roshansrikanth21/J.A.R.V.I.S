import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  Brain,
  CheckCircle2,
  ChevronRight,
  Circle,
  CopyCheck,
  Clock,
  Cpu,
  Database,
  Eye,
  Gauge,
  HardDrive,
  Lock,
  Mic,
  MicOff,
  Minus,
  Music,
  Network,
  Newspaper,
  Radio,
  Search,
  Send,
  Settings,
  ShieldCheck,
  Terminal,
  Volume2,
  Wrench,
  X,
  XOctagon,
  Zap,
} from "lucide-react";
import { Panel } from "@/components/jarvis/Panel";
import { Waveform } from "@/components/jarvis/Waveform";
import { SettingsDrawer } from "@/components/jarvis/SettingsDrawer";
import { AgentTaskBoard, type AgentEvent } from "@/components/jarvis/AgentTaskBoard";
import { ReactorVisualizer } from "@/components/jarvis/ReactorVisualizer";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "JARVIS Command Deck" },
      {
        name: "description",
        content: "Minimal autonomous-agent dashboard for JARVIS.",
      },
    ],
    links: [
      { rel: "preconnect", href: "https://fonts.googleapis.com" },
      { rel: "preconnect", href: "https://fonts.gstatic.com", crossOrigin: "anonymous" },
      {
        rel: "stylesheet",
        href: "https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&display=swap",
      },
    ],
  }),
  component: Page,
});

type Tone = "online" | "warn" | "idle";
type Line = { id: string; role: "user" | "agent" | "system" | "tool"; text: string; at: string };
type Task = { id: number; t: string; eta?: string; status: "queued" | "active" | "done"; at?: string };
type ToolInfo = { name: string; description: string; args_schema: Record<string, string> };
type AgentTrace = { step: number; action: string; args: Record<string, unknown>; observation: string };
type AgentStatus = {
  brain?: {
    primary_llm: string;
    local_model: string;
    max_agent_steps: number;
    use_llm_intent_router: boolean;
  };
  memory?: { available: boolean; count: number; error?: string };
  tools?: ToolInfo[];
  tasks?: Task[];
  trace?: AgentTrace[];
  events?: AgentEvent[];
  safety?: Record<string, boolean | string>;
};
type NewsArticle = { title: string; url: string; source: string };

declare global {
  interface Window {
    electronAPI?: {
      minimizeWindow?: () => void;
      closeWindow?: () => void;
      restartBackend?: () => Promise<void>;
    };
  }
}

const QUICK_COMMANDS = [
  { label: "Scan Screen", command: "what is on my screen", icon: Eye },
  { label: "Fix Screen", command: "look at my screen and tell me exactly what mistake to correct", icon: CopyCheck },
  { label: "Latest News", command: "get me the latest news", icon: Radio },
  { label: "Recall Memory", command: "what do you remember about me", icon: Database },
];

const STAGES = [
  { label: "Sense", value: "voice, screen, events", tone: "online" as Tone },
  { label: "Think", value: "bounded JSON agent", tone: "online" as Tone },
  { label: "Act", value: "tools and desktop ops", tone: "online" as Tone },
  { label: "Verify", value: "trace, safety, tests", tone: "warn" as Tone },
];

function Page() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  return mounted ? <CommandDeck /> : <LoadingShell />;
}

function LoadingShell() {
  return (
    <main className="min-h-screen bg-background text-foreground font-mono grid place-items-center">
      <div className="terminal-frame px-5 py-4 text-xs tracking-[0.18em] uppercase text-muted-foreground">
        <span className="text-hud">jarvis</span> booting command deck<span className="terminal-cursor" />
      </div>
    </main>
  );
}

function CommandDeck() {
  const [connected, setConnected] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const connectingRef = useRef(false);
  const [speaking, setSpeaking] = useState(false);
  const speakingTimeoutRef = useRef<number | null>(null);
  const [listening, setListening] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [lines, setLines] = useState<Line[]>([
    mkLine("system", "Terminal ready. Awaiting directive."),
  ]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [agentStatus, setAgentStatus] = useState<AgentStatus>({});
  const [agentEvents, setAgentEvents] = useState<AgentEvent[]>([]);
  const [news, setNews] = useState<NewsArticle[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const transcriptRef = useRef<HTMLDivElement | null>(null);

  const addLine = useCallback((role: Line["role"], text: string) => {
    if (!text) return;
    setLines((prev) => [...prev.slice(-80), mkLine(role, text)]);
  }, []);

  const refreshAgentStatus = useCallback(async () => {
    if (!connected) return; // Don't poll if not connected
    try {
      const response = await fetch("/api/agent/status");
      if (!response.ok) throw new Error("agent status unavailable");
      const data = await response.json();
      setAgentStatus(data);
      if (Array.isArray(data.tasks)) setTasks(data.tasks);
    } catch {
      // Quietly fail or show initializing status
    }
  }, [connected]);

  const connectWs = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN || connectingRef.current) return;

    connectingRef.current = true;
    setConnecting(true);
    const wsUrl = import.meta.env.DEV ? "ws://localhost:8000/ws" : `ws://${window.location.host}/ws`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      setConnecting(false);
      connectingRef.current = false;
      setError(null);
      addLine("system", "WebSocket uplink established.");
      refreshAgentStatus();
    };

    ws.onclose = () => {
      setConnected(false);
      setListening(false);
      setSpeaking(false);
      setConnecting(false);
      connectingRef.current = false;
    };

    ws.onerror = () => {
      setError("Backend link standby. Initializing modules...");
      setConnecting(false);
      connectingRef.current = false;
      // Retry after 5 seconds
      setTimeout(connectWs, 5000);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const text = data.text ?? data.message ?? "";

        if (data.type === "state" || data.type === "status") {
          setSpeaking(data.status === "speaking");
          if (text) addLine("system", text);
        }
        if (data.type === "transcription" || data.type === "transcript") addLine("user", text);
        if (data.type === "llm_response" || data.type === "response") {
          setIsProcessing(false);
          setSpeaking(true);
          if (speakingTimeoutRef.current) window.clearTimeout(speakingTimeoutRef.current);
          speakingTimeoutRef.current = window.setTimeout(() => setSpeaking(false), 4500);
          addLine("agent", text);
          refreshAgentStatus();
        }
        if (data.type === "audio_level") setAudioLevel(Number(data.level) || 0);
        if (data.type === "news_data" && Array.isArray(data.articles)) setNews(data.articles);
        if (data.type === "tasks" && Array.isArray(data.tasks)) setTasks(data.tasks);
        if (data.type === "agent_event" && data.event) {
          const ev = data.event;
          setAgentEvents((prev) => [...prev, {
            id: `${Date.now()}-${Math.random()}`,
            type: ev.type || "agent_tool",
            text: ev.text,
            action: ev.action,
            args: ev.args,
            observation: ev.observation,
            status: ev.status,
            step: ev.step,
            at: new Date().toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" }),
          }].slice(-50));
        }
        if (data.type === "agent_tool" && data.step) {
          const step = data.step as AgentTrace;
          addLine("tool", `${step.action}: ${step.observation}`);
          setAgentStatus((prev) => ({ ...prev, trace: [...(prev.trace ?? []), step].slice(-25) }));
        }
      } catch {
        addLine("system", "Received an unreadable backend packet.");
      }
    };
  }, [addLine, refreshAgentStatus]);

  useEffect(() => {
    connectWs();
    refreshAgentStatus();
    const id = window.setInterval(refreshAgentStatus, 10000);
    return () => {
      window.clearInterval(id);
      if (speakingTimeoutRef.current) window.clearTimeout(speakingTimeoutRef.current);
      wsRef.current?.close();
    };
  }, [connectWs, refreshAgentStatus]);

  useEffect(() => {
    transcriptRef.current?.scrollTo({ top: 999999, behavior: "smooth" });
  }, [lines.length]);

  const sendCommand = useCallback(
    async (command = input) => {
      const text = command.trim();
      if (!text) return;
      addLine("user", text);
      setInput("");

      if (wsRef.current?.readyState === WebSocket.OPEN) {
        setIsProcessing(true);
        wsRef.current.send(JSON.stringify({ action: "command", text }));
        return;
      }

      try {
        setIsProcessing(true);
        const response = await fetch("/api/command", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ command: text }),
        });
        const data = await response.json();
        setIsProcessing(false);
        addLine("agent", data.response ?? "Command completed.");
        refreshAgentStatus();
      } catch {
        setIsProcessing(false);
        setError("No backend connection available.");
      }
    },
    [addLine, input, refreshAgentStatus],
  );

  const toggleListening = () => {
    if (!connected) {
      connectWs();
      return;
    }
    const next = !listening;
    setListening(next);
    wsRef.current?.send(JSON.stringify({ action: next ? "start_listening" : "stop_listening" }));
  };

  const status = connected
    ? listening
      ? ({ label: "listening", tone: "online" as Tone })
      : ({ label: "linked", tone: "online" as Tone })
    : connecting
      ? ({ label: "linking", tone: "warn" as Tone })
      : ({ label: "offline", tone: "idle" as Tone });

  const activeTask = tasks.find((task) => task.status === "active");
  const queuedTasks = tasks.filter((task) => task.status === "queued");
  const doneTasks = tasks.filter((task) => task.status === "done").slice(-4).reverse();
  const trace = agentStatus.trace ?? [];
  const tools = agentStatus.tools ?? [];
  const memoryCount = agentStatus.memory?.count ?? 0;
  const memoryOnline = Boolean(agentStatus.memory?.available);

  return (
    <main className="min-h-screen bg-background text-foreground font-mono relative overflow-hidden">
      <TerminalBackdrop />

      <header className="relative z-10 border-b border-line bg-panel/95">
        <div className="px-4 py-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="h-9 w-9 border border-hud/50 grid place-items-center brackets">
              <Terminal className="h-4 w-4 text-hud" />
            </div>
            <div className="min-w-0">
              <div className="text-sm tracking-[0.32em] uppercase font-semibold">JARVIS</div>
              <div className="text-[10px] text-muted-foreground tracking-[0.18em] uppercase truncate">
                autonomous command deck
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3 text-[10px] tracking-[0.16em] uppercase text-muted-foreground">
            <StatusPill label={status.label} tone={status.tone} />
            <span className="hidden sm:inline">{new Date().toLocaleTimeString("en-US", { hour12: false })}</span>
            <button className="icon-button" onClick={refreshAgentStatus} title="Refresh agent status">
              <Activity className="h-4 w-4" />
            </button>
            <SettingsDrawer />
            <button
              className="icon-button"
              onClick={() => globalThis.window?.electronAPI?.restartBackend?.()}
              title="Restart backend"
            >
              <Zap className="h-4 w-4" />
            </button>
            <button
              className="icon-button"
              onClick={() => globalThis.window?.electronAPI?.minimizeWindow?.()}
              title="Minimize"
            >
              <Minus className="h-4 w-4" />
            </button>
            <button
              className="icon-button"
              onClick={() => globalThis.window?.electronAPI?.closeWindow?.()}
              title="Close"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
        <div className="border-t border-line overflow-hidden py-1">
          <div className="animate-ticker flex gap-10 whitespace-nowrap text-[9px] uppercase tracking-[0.24em] text-muted-foreground">
            <span>agent loop: json</span>
            <span>memory: {memoryOnline ? `${memoryCount} vectors` : "offline"}</span>
            <span>tools: {tools.length || "loading"}</span>
            <span>safety: bounded steps</span>
            <span>backend: {connected ? "ws open" : "standby"}</span>
            <span>agent loop: json</span>
            <span>memory: {memoryOnline ? `${memoryCount} vectors` : "offline"}</span>
            <span>tools: {tools.length || "loading"}</span>
            <span>safety: bounded steps</span>
            <span>backend: {connected ? "ws open" : "standby"}</span>
          </div>
        </div>
      </header>

      <section className="relative z-10 grid grid-cols-12 gap-3 p-3">
        <aside className="col-span-12 xl:col-span-3 space-y-3">
          <Panel title="Agent Stack" status="live">
            <div className="space-y-3">
              <Metric icon={Brain} label="Brain" value={agentStatus.brain?.local_model ?? "llama local"} />
              <Metric icon={Database} label="Memory" value={memoryOnline ? `${memoryCount} items` : "offline"} />
              <Metric icon={Wrench} label="Tools" value={`${tools.length || 0} registered`} />
              <Metric icon={Lock} label="Router" value={agentStatus.brain?.use_llm_intent_router ? "llm" : "fast"} />
            </div>
          </Panel>

          <Panel title="Next Stages" status="pipeline">
            <div className="space-y-2">
              {STAGES.map((stage) => (
                <div key={stage.label} className="stage-row">
                  <StatusDot tone={stage.tone} />
                  <div className="min-w-0">
                    <div className="text-[11px] uppercase tracking-[0.18em] text-foreground">{stage.label}</div>
                    <div className="text-[10px] text-muted-foreground truncate">{stage.value}</div>
                  </div>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="Safety Kernel" status="armed">
            <div className="grid grid-cols-2 gap-2">
              <SafetyItem icon={ShieldCheck} label="Bounded" active />
              <SafetyItem icon={Lock} label="No Power Auto" active />
              <SafetyItem icon={CheckCircle2} label="JSON Tools" active />
              <SafetyItem icon={Eye} label="Traceable" active={trace.length > 0} />
            </div>
          </Panel>
        </aside>

        <section className="col-span-12 xl:col-span-6 space-y-3">
          <div className="terminal-frame relative overflow-hidden min-h-[560px] flex flex-col items-center justify-between p-4 md:p-6">
            <div className="absolute inset-0 opacity-[0.05] pointer-events-none circuit-grid" />
            <div className="absolute inset-x-0 top-0 h-px bg-hud/50 animate-scan" />

            {isProcessing && (
              <div className="processing-overlay text-center p-6">
                <div className="text-warn text-[10px] tracking-[0.3em] uppercase mb-4 animate-pulse-fast">Neural Link Active</div>
                <div className="text-xl md:text-3xl font-bold uppercase text-foreground processing-text-glow">
                  Analyzing Directive
                </div>
                {agentEvents.length > 0 && (
                  <div className="mt-6 p-3 bg-background/50 border border-warn/30 max-w-md mx-auto text-xs text-warn truncate">
                    {agentEvents[agentEvents.length - 1].type === "AGENT_THOUGHT" 
                      ? `"${agentEvents[agentEvents.length - 1].text}"`
                      : agentEvents[agentEvents.length - 1].action || "Processing..."}
                  </div>
                )}
                <div className="mt-8 flex items-center justify-center gap-2">
                  <span className="w-2 h-2 bg-warn rounded-full animate-pulse-fast" style={{ animationDelay: '0ms' }} />
                  <span className="w-2 h-2 bg-warn rounded-full animate-pulse-fast" style={{ animationDelay: '150ms' }} />
                  <span className="w-2 h-2 bg-warn rounded-full animate-pulse-fast" style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            )}

            <div className="w-full flex justify-between text-[10px] uppercase tracking-[0.22em] text-muted-foreground relative z-10">
              <span>core // mark local</span>
              <span>{speaking ? "tx" : connected ? "rx" : "idle"}</span>
            </div>

            <div className={`relative flex flex-col items-center justify-center py-6 z-10 transition-opacity duration-500 ${isProcessing ? 'opacity-20' : 'opacity-100'}`}>
              <ReactorVisualizer active={connected} level={audioLevel} thinking={isProcessing} />
              <DualAudioVisualizer
                userActive={listening && !speaking}
                jarvisActive={speaking}
                level={audioLevel}
              />
              <div className="mt-4 text-center max-w-xl min-h-[52px]">
                <div className="text-[10px] uppercase tracking-[0.28em] text-muted-foreground">neural stream</div>
                <p className="mt-2 text-sm md:text-base text-foreground leading-relaxed terminal-cursor">
                  {lines[lines.length - 1]?.text ?? "Awaiting directive."}
                </p>
              </div>
            </div>

            <div className="w-full max-w-3xl space-y-3">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {QUICK_COMMANDS.map((item) => (
                  <button key={item.label} className="quick-action" onClick={() => sendCommand(item.command)}>
                    <item.icon className="h-4 w-4" />
                    <span>{item.label}</span>
                  </button>
                ))}
              </div>

              <div className={`command-bar ${isProcessing ? 'is-disabled' : ''}`}>
                <ChevronRight className="h-4 w-4 text-hud shrink-0" />
                <input
                  value={input}
                  disabled={isProcessing}
                  onChange={(event) => setInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") sendCommand();
                  }}
                  placeholder="Ask, delegate, search, remember, act..."
                  className="flex-1 bg-transparent outline-none text-sm placeholder:text-muted-foreground/50 min-w-0"
                />
                <button className="icon-button strong" onClick={() => sendCommand()} title="Send command">
                  <Send className="h-4 w-4" />
                </button>
                <button className="icon-button" onClick={() => sendCommand("interrupt")} title="Interrupt Speech">
                  <XOctagon className="h-4 w-4 text-warn" />
                </button>
                <button className="icon-button" onClick={toggleListening} title="Toggle listening">
                  {listening ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
                </button>
              </div>
              {error && <div className="text-[11px] text-warn tracking-[0.16em] uppercase">{error}</div>}
            </div>
          </div>

          <Panel title="Terminal Stream" status={`${lines.length} lines`}>
            <div ref={transcriptRef} className="h-56 overflow-y-auto space-y-1.5 pr-1">
              {lines.map((line) => (
                <TerminalLine key={line.id} line={line} />
              ))}
            </div>
          </Panel>
        </section>

        <aside className="col-span-12 xl:col-span-3 space-y-3">
          <MusicPanel active={connected || speaking || listening} />

          {news.length > 0 && (
            <Panel title="Global Intelligence" status={`${news.length} reports`}>
              <div className="space-y-3 pr-1 max-h-64 overflow-y-auto">
                {news.map((item, idx) => (
                  <div key={idx} className="flex gap-2 min-w-0 group">
                    <Newspaper className="h-3.5 w-3.5 text-hud mt-0.5 shrink-0 opacity-70 group-hover:opacity-100 transition-opacity" />
                    <div className="min-w-0">
                      <a href={item.url} target="_blank" rel="noreferrer" className="text-[11px] leading-snug text-foreground hover:text-hud transition-colors line-clamp-2">
                        {item.title}
                      </a>
                      <div className="text-[9px] uppercase tracking-[0.1em] text-muted-foreground mt-1">
                        {item.source || "UNKNOWN SOURCE"}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </Panel>
          )}

          <Panel title="Execution Queue" status={activeTask ? "active" : `${queuedTasks.length} queued`}>
            <div className="space-y-2">
              {activeTask ? <TaskRow task={activeTask} active /> : <EmptyState text="No active operation." />}
              {queuedTasks.slice(0, 4).map((task) => (
                <TaskRow key={task.id} task={task} />
              ))}
              {doneTasks.map((task) => (
                <TaskRow key={task.id} task={task} done />
              ))}
            </div>
          </Panel>

          <AgentTaskBoard events={agentEvents} />

          <Panel title="Tool Registry" status={`${tools.length} online`}>
            <div className="grid grid-cols-1 gap-2 max-h-72 overflow-y-auto pr-1">
              {tools.slice(0, 12).map((tool) => (
                <div key={tool.name} className="tool-chip">
                  <Wrench className="h-3.5 w-3.5 text-hud/80 shrink-0" />
                  <div className="min-w-0">
                    <div className="text-[10px] uppercase tracking-[0.16em] text-foreground truncate">{tool.name}</div>
                    <div className="text-[10px] text-muted-foreground truncate">{tool.description}</div>
                  </div>
                </div>
              ))}
            </div>
          </Panel>
        </aside>
      </section>
    </main>
  );
}

function DualAudioVisualizer({
  userActive,
  jarvisActive,
  level,
}: {
  userActive: boolean;
  jarvisActive: boolean;
  level: number;
}) {
  return (
    <div className="mt-4 w-full max-w-2xl dual-audio-grid">
      <VoiceChannel
        label="you"
        status={userActive ? "mic input" : "passive"}
        active={userActive}
        level={level}
        tone="user"
      />
      <VoiceChannel
        label="jarvis"
        status={jarvisActive ? "speaking" : "ready"}
        active={jarvisActive}
        level={jarvisActive ? 21000 : 0}
        tone="jarvis"
      />
    </div>
  );
}

function VoiceChannel({
  label,
  status,
  active,
  level,
  tone,
}: {
  label: string;
  status: string;
  active: boolean;
  level: number;
  tone: "user" | "jarvis";
}) {
  const bars = Array.from({ length: 24 });
  const normalized = Math.max(6, Math.min(100, (level / 26000) * 100));

  return (
    <div className={`voice-channel ${tone} ${active ? "is-active" : ""}`}>
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          {tone === "user" ? <Mic className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
          <span className="uppercase tracking-[0.22em] text-[10px] truncate">{label}</span>
        </div>
        <span className="text-[9px] uppercase tracking-[0.16em] opacity-70">{status}</span>
      </div>
      <div className="voice-bars" aria-label={`${label} audio visualizer`}>
        {bars.map((_, index) => {
          const offset = Math.abs(Math.sin(index * 0.62)) * 34;
          const height = active ? Math.min(100, normalized * 0.55 + offset + 16) : 10 + (index % 5) * 3;
          return (
            <span
              key={index}
              style={{
                height: `${height}%`,
                animationDelay: `${index * 42}ms`,
              }}
            />
          );
        })}
      </div>
    </div>
  );
}

function MusicPanel({ active }: { active: boolean }) {
  const tracks = ["Local Neural Mix", "Ambient Compute", "Arc Pulse"];

  return (
    <Panel title="Music" status={active ? "playing" : "idle"}>
      <div className={`music-card ${active ? "is-active" : ""}`}>
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="music-disc">
              <Music className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <div className="text-xs uppercase tracking-[0.16em] text-foreground truncate">{tracks[0]}</div>
              <div className="text-[10px] text-muted-foreground truncate">system ambience</div>
            </div>
          </div>
          <StatusDot tone={active ? "warn" : "idle"} />
        </div>
        <div className="music-eq">
          {Array.from({ length: 18 }).map((_, index) => (
            <span key={index} style={{ animationDelay: `${index * 58}ms` }} />
          ))}
        </div>
        <div className="music-progress">
          <span />
        </div>
      </div>
    </Panel>
  );
}

function TerminalBackdrop() {
  return (
    <div className="pointer-events-none fixed inset-0 z-0">
      <div className="absolute inset-0 circuit-grid opacity-60" />
      <div className="absolute inset-0 scanline-overlay" />
      <div className="absolute left-0 top-0 h-full w-px bg-hud/20 animate-scan-x" />
    </div>
  );
}

function Metric({ icon: Icon, label, value }: { icon: typeof Cpu; label: string; value: string }) {
  return (
    <div className="flex items-center gap-3 min-w-0">
      <div className="h-8 w-8 border border-line grid place-items-center">
        <Icon className="h-4 w-4 text-hud/80" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">{label}</div>
        <div className="text-xs text-foreground truncate">{value}</div>
      </div>
    </div>
  );
}

function SafetyItem({ icon: Icon, label, active }: { icon: typeof Lock; label: string; active: boolean }) {
  return (
    <div className={`safety-item ${active ? "is-active" : ""}`}>
      <Icon className="h-4 w-4" />
      <span>{label}</span>
    </div>
  );
}

function TaskRow({ task, active = false, done = false }: { task: Task; active?: boolean; done?: boolean }) {
  return (
    <div className={`task-row ${active ? "is-active" : ""} ${done ? "is-done" : ""}`}>
      {active ? <Radio className="h-3.5 w-3.5 animate-pulse-soft" /> : done ? <CheckCircle2 className="h-3.5 w-3.5" /> : <Clock className="h-3.5 w-3.5" />}
      <span className="truncate flex-1">{task.t}</span>
      <span className="text-[9px] text-muted-foreground">{task.at ?? task.eta ?? ""}</span>
    </div>
  );
}

function TerminalLine({ line }: { line: Line }) {
  const roleClass =
    line.role === "user"
      ? "text-hud"
      : line.role === "agent"
        ? "text-success"
        : line.role === "tool"
          ? "text-warn"
          : "text-muted-foreground";

  return (
    <div className="grid grid-cols-[52px_42px_1fr] gap-2 text-xs leading-relaxed">
      <span className="text-muted-foreground/60">{line.at}</span>
      <span className={`${roleClass} uppercase tracking-[0.14em]`}>{line.role}</span>
      <span className="text-foreground/90 break-words">{line.text}</span>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="text-[11px] text-muted-foreground/60 italic py-2">{text}</div>;
}

function StatusPill({ label, tone }: { label: string; tone: Tone }) {
  return (
    <span className={`status-pill ${tone}`}>
      <StatusDot tone={tone} />
      {label}
    </span>
  );
}

function StatusDot({ tone }: { tone: Tone }) {
  return <span className={`status-dot ${tone}`} />;
}

function mkLine(role: Line["role"], text: string): Line {
  return {
    id: `${Date.now()}-${Math.random()}`,
    role,
    text,
    at: new Date().toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" }),
  };
}
