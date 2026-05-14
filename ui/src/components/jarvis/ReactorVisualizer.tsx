import React, { useEffect, useRef } from "react";

export function ReactorVisualizer({ level, active }: { level: number; active: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    
    let animationId: number;
    
    const draw = () => {
      const width = canvas.width;
      const height = canvas.height;
      const centerX = width / 2;
      const centerY = height / 2;
      
      ctx.clearRect(0, 0, width, height);
      
      // Calculate normalized level (RMS is typically lower than peak, maybe 0-8000)
      // We scale it for visual effect
      const normalizedLevel = Math.min(1, Math.max(0, level / 6000));
      const targetRadius = active ? 40 + (normalizedLevel * 50) : 30;
      
      // Inner core glow
      const gradient = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, targetRadius);
      gradient.addColorStop(0, "rgba(0, 240, 255, 0.8)");
      gradient.addColorStop(0.5, "rgba(0, 150, 255, 0.4)");
      gradient.addColorStop(1, "rgba(0, 50, 100, 0)");
      
      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.arc(centerX, centerY, targetRadius, 0, Math.PI * 2);
      ctx.fill();
      
      // Outer ring
      ctx.strokeStyle = `rgba(0, 200, 255, ${active ? 0.6 : 0.2})`;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(centerX, centerY, targetRadius * 1.2, 0, Math.PI * 2);
      ctx.stroke();
      
      animationId = requestAnimationFrame(draw);
    };
    
    draw();
    return () => cancelAnimationFrame(animationId);
  }, [level, active]);
  
  return (
    <div className="relative flex items-center justify-center">
      <canvas ref={canvasRef} width={200} height={200} className="pointer-events-none" />
      {!active && <div className="absolute inset-0 flex items-center justify-center text-[10px] text-hud/50 uppercase tracking-widest font-mono">Idle</div>}
    </div>
  );
}
