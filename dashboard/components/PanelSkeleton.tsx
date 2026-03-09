/**
 * Pulse skeleton used as Suspense fallback for dashboard panels.
 */
export function PanelSkeleton({ rows = 4, height = "h-4" }: { rows?: number; height?: string }) {
  return (
    <div className="rounded-xl p-5 space-y-3 bg-surface border border-border">
      <div className="h-3.5 w-1/4 skeleton rounded" />
      <div className="h-2 w-1/3 skeleton rounded" style={{ opacity: 0.6 }} />
      <div className="h-px bg-border" />
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className={`${height} skeleton rounded`} style={{ width: `${82 - i * 8}%` }} />
      ))}
    </div>
  );
}
