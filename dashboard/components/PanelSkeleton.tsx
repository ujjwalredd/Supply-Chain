/**
 * Pulse skeleton used as Suspense fallback for dashboard panels.
 * rows: number of skeleton lines to show (default 4).
 */
export function PanelSkeleton({ rows = 4, height = "h-4" }: { rows?: number; height?: string }) {
  return (
    <div className="rounded-lg border border-border bg-card p-5 animate-pulse space-y-3">
      {/* Title bar */}
      <div className="h-3 w-1/3 bg-muted rounded" />
      <div className="h-px bg-border" />
      {/* Content rows */}
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className={`${height} bg-muted rounded`}
          style={{ width: `${75 - i * 10}%` }}
        />
      ))}
    </div>
  );
}
