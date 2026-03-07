/**
 * Pulse skeleton used as Suspense fallback for dashboard panels.
 * rows: number of skeleton lines to show (default 4).
 */
export function PanelSkeleton({ rows = 4, height = "h-4" }: { rows?: number; height?: string }) {
  return (
    <div className="rounded-xl p-5 space-y-3" style={{ background: "#111117", border: "1px solid rgba(255,255,255,0.07)" }}>
      <div className="h-3.5 w-1/4 skeleton rounded-md" />
      <div className="h-1.5 w-1/3 skeleton rounded-md" style={{ opacity: 0.5 }} />
      <div className="h-px" style={{ background: "rgba(255,255,255,0.06)" }} />
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className={`${height} skeleton rounded-md`} style={{ width: `${80 - i * 8}%` }} />
      ))}
    </div>
  );
}
