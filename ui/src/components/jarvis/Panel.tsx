import { ReactNode } from "react";

interface PanelProps {
  title: string;
  status?: string;
  children: ReactNode;
  className?: string;
  dense?: boolean;
}

export function Panel({ title, status, children, className = "", dense = false }: PanelProps) {
  return (
    <div className={`relative bg-panel border border-line scanlines ${className}`}>
      <div className="flex items-center justify-between border-b border-line px-3 py-1.5">
        <div className="flex items-center gap-2 text-[10px] tracking-[0.2em] text-muted-foreground uppercase">
          <span className="text-hud">&gt;</span>
          <span>{title}</span>
        </div>
        {status && (
          <div className="flex items-center gap-1.5 text-[9px] tracking-[0.2em] text-muted-foreground uppercase">
            <span className="w-1 h-1 bg-hud animate-pulse-soft" />
            {status}
          </div>
        )}
      </div>
      <div className={dense ? "p-2" : "p-3"}>{children}</div>
    </div>
  );
}
