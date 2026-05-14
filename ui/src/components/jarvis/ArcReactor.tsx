interface ArcReactorProps {
  active?: boolean;
  speaking?: boolean;
}

export function ArcReactor({ active = false, speaking = false }: ArcReactorProps) {
  return (
    <div className="relative w-56 h-56 flex items-center justify-center">
      {/* Background Glow */}
      <div className={`absolute inset-0 rounded-full bg-hud/5 blur-3xl transition-opacity duration-1000 ${active ? "opacity-100" : "opacity-0"}`} />

      {/* Outer Rotating Segmented Ring */}
      <svg className="absolute inset-0 w-full h-full animate-spin-slow" viewBox="0 0 100 100">
        <circle cx="50" cy="50" r="48" fill="none" stroke="var(--hud)" strokeWidth="0.15" strokeDasharray="1 3" opacity="0.3" />
        <path d="M 50 2 A 48 48 0 0 1 98 50" fill="none" stroke="var(--hud)" strokeWidth="1" strokeDasharray="4 8" opacity="0.6" />
        <path d="M 50 98 A 48 48 0 0 1 2 50" fill="none" stroke="var(--hud)" strokeWidth="1" strokeDasharray="4 8" opacity="0.6" />
      </svg>

      {/* Static Concentric Detail Rings */}
      <svg className="absolute inset-0 w-full h-full" viewBox="0 0 100 100">
        <circle cx="50" cy="50" r="42" fill="none" stroke="var(--hud)" strokeWidth="0.5" opacity="0.15" />
        <circle cx="50" cy="50" r="40" fill="none" stroke="var(--hud)" strokeWidth="0.1" opacity="0.2" />
        <circle cx="50" cy="50" r="35" fill="none" stroke="var(--hud)" strokeWidth="0.2" strokeDasharray="0.5 1.5" opacity="0.4" />
      </svg>

      {/* The J.A.R.V.I.S. Text Ring */}
      <svg className="absolute inset-0 w-full h-full animate-spin-slow" style={{ animationDirection: 'reverse', animationDuration: '40s' }} viewBox="0 0 100 100">
        <defs>
          <path id="textPath" d="M 50 50 m -32, 0 a 32,32 0 1,1 64,0 a 32,32 0 1,1 -64,0" />
        </defs>
        <text className="text-[4.5px] fill-hud font-bold tracking-[0.5em] uppercase opacity-80">
          <textPath href="#textPath">
            J.A.R.V.I.S. // JUST A RATHER VERY INTELLIGENT SYSTEM // J.A.R.V.I.S. //
          </textPath>
        </text>
      </svg>

      {/* Pulse rings when active */}
      {active && (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="absolute w-28 h-28 border border-hud/40 rounded-full animate-ring-pulse" />
          <div className="absolute w-28 h-28 border border-hud/40 rounded-full animate-ring-pulse" style={{ animationDelay: "1.25s" }} />
        </div>
      )}

      {/* Core Interface */}
      <div className={`relative w-24 h-24 rounded-full border border-hud/30 flex flex-col items-center justify-center bg-panel/20 backdrop-blur-sm ${speaking ? "animate-pulse-soft" : ""}`}>
        <div className="absolute inset-1 rounded-full border border-hud/10" />
        <div className="absolute inset-4 rounded-full border border-hud/5" />
        
        {/* Animated Inner Bits */}
        <div className="flex gap-0.5 items-end h-6 mb-1">
          {Array.from({ length: 5 }).map((_, i) => (
            <div 
              key={i} 
              className="w-1 bg-hud transition-all duration-150" 
              style={{ 
                height: speaking ? `${20 + Math.random() * 80}%` : '20%',
                opacity: active ? 0.8 : 0.2
              }} 
            />
          ))}
        </div>

        <div className="text-[8px] font-bold tracking-[0.2em] text-hud z-10 leading-none">
          {active ? "ONLINE" : "STDBY"}
        </div>
        <div className="text-[6px] tracking-[0.1em] text-muted-foreground mt-1 opacity-60">
          MARK LXXXV
        </div>
      </div>

      {/* Tech Brackets (Fixed Position) */}
      {[
        "top-4 left-4 border-l border-t",
        "top-4 right-4 border-r border-t",
        "bottom-4 left-4 border-l border-b",
        "bottom-4 right-4 border-r border-b",
      ].map((c, i) => (
        <div key={i} className={`absolute w-4 h-4 border-hud/60 ${c}`} />
      ))}
    </div>
  );
}
