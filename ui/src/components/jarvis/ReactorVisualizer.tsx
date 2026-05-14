import React, { useEffect, useRef } from "react";

export function ReactorVisualizer({ level, active, thinking = false }: { level: number; active: boolean; thinking?: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    
    let animationId: number;
    let rotation = 0;
    
    const draw = () => {
      const width = canvas.width;
      const height = canvas.height;
      const centerX = width / 2;
      const centerY = height / 2;
      
      ctx.clearRect(0, 0, width, height);
      
      // Calculate normalized level (RMS is typically lower than peak, maybe 0-8000)
      // We scale it for visual effect
      const normalizedLevel = Math.min(1, Math.max(0, level / 6000));
      const targetRadius = active || thinking ? 40 + (normalizedLevel * 50) : 30;
      
      // Define colors based on thinking state
      const coreColor = thinking ? "rgba(255, 170, 0, 0.8)" : "rgba(0, 240, 255, 0.8)";
      const midColor = thinking ? "rgba(255, 100, 0, 0.4)" : "rgba(0, 150, 255, 0.4)";
      const glowColor = thinking ? "rgba(100, 40, 0, 0)" : "rgba(0, 50, 100, 0)";
      const ringColor = thinking ? `rgba(255, 150, 0, ${active || thinking ? 0.6 : 0.2})` : `rgba(0, 200, 255, ${active || thinking ? 0.6 : 0.2})`;
      
      // Inner core glow
      const gradient = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, targetRadius);
      gradient.addColorStop(0, coreColor);
      gradient.addColorStop(0.5, midColor);
      gradient.addColorStop(1, glowColor);
      
      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.arc(centerX, centerY, targetRadius, 0, Math.PI * 2);
      ctx.fill();
      
      // Outer ring with rotation if thinking
      ctx.save();
      ctx.translate(centerX, centerY);
      
      if (thinking) {
        rotation += 0.05;
        ctx.rotate(rotation);
        // Draw segmented ring for thinking
        ctx.strokeStyle = ringColor;
        ctx.lineWidth = 3;
        for (let i = 0; i < 4; i++) {
          ctx.beginPath();
          ctx.arc(0, 0, targetRadius * 1.2, i * (Math.PI / 2) + 0.2, (i + 1) * (Math.PI / 2) - 0.2);
          ctx.stroke();
        }
      } else {
        ctx.strokeStyle = ringColor;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(0, 0, targetRadius * 1.2, 0, Math.PI * 2);
        ctx.stroke();
      }
      
      ctx.restore();
      
      animationId = requestAnimationFrame(draw);
    };
    
    draw();
    return () => cancelAnimationFrame(animationId);
  }, [level, active, thinking]);
  
  return (
    <div className="relative flex items-center justify-center">
      <canvas ref={canvasRef} width={200} height={200} className="pointer-events-none" />
      {(!active && !thinking) && <div className="absolute inset-0 flex items-center justify-center text-[10px] text-hud/50 uppercase tracking-widest font-mono">Idle</div>}
    </div>
  );
}
