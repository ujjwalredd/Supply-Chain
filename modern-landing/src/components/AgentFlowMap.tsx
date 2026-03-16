import { useCallback, useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const VB_W = 1000;
const VB_H = 490;

type NodeState = 'idle' | 'alert' | 'active' | 'resolved';

interface AgentNode {
  id: string;
  label: string;
  tier: 1 | 2 | 3;
  cx: number;
  cy: number;
  w: number;
  h: number;
  color: string;
  model: string;
  interval: string;
  parentId: string | null;
  description: string;
  heals: string;
}

// All cx values shifted +40 vs v1 to leave room for tier labels on left
const NODES: AgentNode[] = [
  // ── Tier 1 ──────────────────────────────────────────────────
  {
    id: 'orchestrator', label: 'orchestrator',
    tier: 1, cx: 520, cy: 72, w: 196, h: 60,
    color: '#0070F3', model: 'Claude Sonnet 4.6', interval: '5 min', parentId: null,
    description: 'deepagents LangGraph with 3 sub-agents and 7 tools. Cross-agent root cause analysis.',
    heals: 'Issues structured corrections to all agents via Redis pub/sub',
  },
  // ── Tier 2 ──────────────────────────────────────────────────
  {
    id: 'kafka_guardian', label: 'kafka_guardian',
    tier: 2, cx: 200, cy: 222, w: 148, h: 50,
    color: '#F59E0B', model: 'Claude Haiku 4.5', interval: '30 sec', parentId: 'orchestrator',
    description: 'Consumer lag, DLQ spikes, producer silence detection.',
    heals: 'Restarts Kafka containers via Docker API',
  },
  {
    id: 'dagster_guardian', label: 'dagster_guardian',
    tier: 2, cx: 520, cy: 222, w: 160, h: 50,
    color: '#8B5CF6', model: 'Claude Haiku 4.5', interval: '2 min', parentId: 'orchestrator',
    description: 'Run failures, asset freshness, schedule health.',
    heals: 'Triggers medallion_full_pipeline or incremental job',
  },
  {
    id: 'mlflow_guardian', label: 'mlflow_guardian',
    tier: 2, cx: 840, cy: 222, w: 148, h: 50,
    color: '#EC4899', model: 'Claude Haiku 4.5', interval: '5 min', parentId: 'orchestrator',
    description: 'ROC-AUC drift monitoring. Hard floor: never promotes if roc_auc < 0.60.',
    heals: 'Resets cooldown and triggers real MLflow retraining',
  },
  // ── Tier 3 — kafka children ──────────────────────────────────
  {
    id: 'data_ingestion_agent', label: 'data_ingestion',
    tier: 3, cx: 90, cy: 392, w: 96, h: 42,
    color: '#10B981', model: 'Claude Haiku 4.5', interval: '60 sec', parentId: 'kafka_guardian',
    description: 'Watches /data/source/. Iterative: read → generate loader → validate → fix (up to 3 attempts).',
    heals: 'Auto-retries loader generation up to 3 times',
  },
  {
    id: 'bronze_agent', label: 'bronze_agent',
    tier: 3, cx: 200, cy: 392, w: 96, h: 42,
    color: '#71717A', model: 'Claude Haiku 4.5', interval: '5 min', parentId: 'kafka_guardian',
    description: 'Parquet existence, schema drift, freshness validation on raw Bronze layer.',
    heals: 'Triggers Dagster asset materialization',
  },
  {
    id: 'silver_agent', label: 'silver_agent',
    tier: 3, cx: 310, cy: 392, w: 96, h: 42,
    color: '#10B981', model: 'Claude Haiku 4.5', interval: '5 min', parentId: 'kafka_guardian',
    description: 'Null rates, dedup verification, status enum validation across Silver layer.',
    heals: 'Escalates to medallion_supervisor on repeated failure',
  },
  // ── Tier 3 — dagster children ────────────────────────────────
  {
    id: 'gold_agent', label: 'gold_agent',
    tier: 3, cx: 410, cy: 392, w: 96, h: 42,
    color: '#F59E0B', model: 'Claude Haiku 4.5', interval: '10 min', parentId: 'dagster_guardian',
    description: 'Financial formula re-validation, ML output bounds, forecast sanity on Gold layer.',
    heals: 'Escalates to medallion_supervisor',
  },
  {
    id: 'medallion_supervisor', label: 'medallion_sup',
    tier: 3, cx: 520, cy: 392, w: 96, h: 42,
    color: '#EC4899', model: 'Claude Haiku 4.5', interval: '3 min', parentId: 'dagster_guardian',
    description: 'Data contract enforcement across Bronze → Silver → Gold dependency chain.',
    heals: 'Publishes cross-layer correction alerts',
  },
  {
    id: 'database_health', label: 'db_health',
    tier: 3, cx: 630, cy: 392, w: 96, h: 42,
    color: '#0070F3', model: 'Claude Haiku 4.5', interval: '60 sec', parentId: 'dagster_guardian',
    description: 'Connection count, long queries, lock detection, table sizes in PostgreSQL.',
    heals: 'Alerts on long-running locks and pool exhaustion',
  },
  // ── Tier 3 — mlflow children ─────────────────────────────────
  {
    id: 'feature_engineer', label: 'feature_eng',
    tier: 3, cx: 730, cy: 392, w: 96, h: 42,
    color: '#8B5CF6', model: 'Claude Haiku 4.5', interval: '15 min', parentId: 'mlflow_guardian',
    description: 'Reads Gold layer, generates 5 features, validates via 5-gate sandbox.',
    heals: 'Triggers incremental ML retraining after feature write',
  },
  {
    id: 'ai_quality_monitor', label: 'ai_quality',
    tier: 3, cx: 840, cy: 392, w: 96, h: 42,
    color: '#EF4444', model: 'Claude Haiku 4.5', interval: '60 sec', parentId: 'mlflow_guardian',
    description: 'Stuck pending actions, low-confidence re-triggers, REROUTE validation.',
    heals: 'Re-triggers low-confidence actions automatically',
  },
  {
    id: 'dashboard_agent', label: 'dashboard',
    tier: 3, cx: 950, cy: 392, w: 96, h: 42,
    color: '#0070F3', model: 'Claude Haiku 4.5', interval: '10 min', parentId: 'mlflow_guardian',
    description: 'Reads agent heartbeats + Gold metrics. Builds Grafana JSON. Pushes via API.',
    heals: 'Auto-regenerates and pushes broken Grafana panels',
  },
];

const nodeById: Record<string, AgentNode> = {};
for (const n of NODES) nodeById[n.id] = n;

// ── Connections (computed from parent relationships) ──────────
interface Conn { id: string; pathD: string; color: string; fromId: string; toId: string; }

const CONNS: Conn[] = NODES
  .filter(n => n.parentId !== null)
  .map(n => {
    const p = nodeById[n.parentId!];
    const sx = p.cx, sy = p.cy + p.h / 2;
    const ex = n.cx, ey = n.cy - n.h / 2;
    const my = (sy + ey) / 2;
    return { id: `${p.id}--${n.id}`, pathD: `M ${sx} ${sy} C ${sx} ${my} ${ex} ${my} ${ex} ${ey}`, color: n.color, fromId: p.id, toId: n.id };
  });

// ── Worker group zone backgrounds ────────────────────────────
const ZONES = [
  { guardianId: 'kafka_guardian',   color: '#F59E0B', x: 42,  y: 355, w: 316, h: 80 },
  { guardianId: 'dagster_guardian', color: '#8B5CF6', x: 362, y: 355, w: 316, h: 80 },
  { guardianId: 'mlflow_guardian',  color: '#EC4899', x: 682, y: 355, w: 316, h: 80 },
];

// ── Subtree utility ───────────────────────────────────────────
function getSubtreeIds(nodeId: string): Set<string> {
  const ids = new Set<string>([nodeId]);
  let curr = nodeById[nodeId];
  while (curr.parentId) { ids.add(curr.parentId); curr = nodeById[curr.parentId]; }
  const addChildren = (id: string) => {
    for (const n of NODES) { if (n.parentId === id) { ids.add(n.id); addChildren(n.id); } }
  };
  addChildren(nodeId);
  return ids;
}

// ── Incident simulation ───────────────────────────────────────
interface IncidentStep {
  alertIds: string[]; activeIds: string[]; pulseConnIds: string[];
  prefix: string; msg: string; msgColor: string; duration: number;
}

const INCIDENT: IncidentStep[] = [
  { alertIds: ['kafka_guardian'], activeIds: [], pulseConnIds: [],
    prefix: 'kafka_guardian', msg: 'ALERT: Supplier XJ-4421 delay +72h detected', msgColor: '#F59E0B', duration: 1600 },
  { alertIds: ['kafka_guardian'], activeIds: ['orchestrator'], pulseConnIds: ['orchestrator--kafka_guardian'],
    prefix: 'orchestrator', msg: 'analyzing 847 data points across 13 agents...', msgColor: '#0070F3', duration: 1600 },
  { alertIds: [], activeIds: ['orchestrator', 'dagster_guardian'], pulseConnIds: ['orchestrator--dagster_guardian'],
    prefix: 'orchestrator', msg: 'issuing correction to dagster_guardian — reroute alt carrier CN-7', msgColor: '#0070F3', duration: 1600 },
  { alertIds: [], activeIds: ['dagster_guardian', 'medallion_supervisor', 'gold_agent'], pulseConnIds: ['dagster_guardian--medallion_supervisor', 'dagster_guardian--gold_agent'],
    prefix: 'dagster_guardian', msg: 'pipeline healthy · 0 stale assets · medallion cascade triggered', msgColor: '#8B5CF6', duration: 1600 },
  { alertIds: [], activeIds: ['bronze_agent', 'silver_agent', 'data_ingestion_agent'], pulseConnIds: ['kafka_guardian--bronze_agent', 'kafka_guardian--silver_agent', 'kafka_guardian--data_ingestion_agent'],
    prefix: 'data_ingestion', msg: 'Alt carrier CN-7 available · ETA delta: +6h · pipeline healthy', msgColor: '#10B981', duration: 1600 },
  { alertIds: [], activeIds: ['feature_engineer', 'mlflow_guardian'], pulseConnIds: ['mlflow_guardian--feature_engineer'],
    prefix: 'feature_engineer', msg: 'demand spike +18% next 14d · confidence 91% · retraining triggered', msgColor: '#8B5CF6', duration: 1600 },
  { alertIds: [], activeIds: [], pulseConnIds: [],
    prefix: 'ai_quality_monitor', msg: 'RESOLVED — no human intervention required · all agents healthy · offline=0', msgColor: '#10B981', duration: 3000 },
];

interface LogLine { key: number; prefix: string; msg: string; color: string; }

const MONO = "ui-monospace, 'Cascadia Code', 'Source Code Pro', Menlo, monospace";

const TIER_LABELS = [
  { y: 72,  label: 'ORCH.' },
  { y: 222, label: 'GUARDS' },
  { y: 392, label: 'WORKERS' },
];

export function AgentFlowMap() {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hovered, setHovered]     = useState<string | null>(null);
  const [locked, setLocked]       = useState<string | null>(null);
  const [step, setStep]           = useState<number | null>(null);
  const [resolved, setResolved]   = useState(false);
  const [cycleCount, setCycleCount] = useState(0);
  const [logLines, setLogLines]   = useState<LogLine[]>([]);
  const logKeyRef = useRef(0);

  // ── Incident loop ─────────────────────────────────────────
  useEffect(() => {
    const timers: ReturnType<typeof setTimeout>[] = [];

    const run = () => {
      setCycleCount(c => c + 1);
      let delay = 0;
      INCIDENT.forEach((s, i) => {
        const t = setTimeout(() => {
          setStep(i);
          if (i === INCIDENT.length - 1) setResolved(true);
          setLogLines(prev =>
            [...prev, { key: logKeyRef.current++, prefix: s.prefix, msg: s.msg, color: s.msgColor }].slice(-4)
          );
        }, delay);
        timers.push(t);
        delay += s.duration;
      });
      const reset = setTimeout(() => {
        setStep(null);
        setResolved(false);
        const clearLog = setTimeout(() => setLogLines([]), 2000);
        timers.push(clearLog);
        const next = setTimeout(run, 3000);
        timers.push(next);
      }, delay);
      timers.push(reset);
    };

    const start = setTimeout(run, 4000);
    timers.push(start);
    return () => timers.forEach(clearTimeout);
  }, []);

  // ── Derived state ─────────────────────────────────────────
  const currentStep = step !== null ? INCIDENT[step] : null;
  const alertSet    = new Set(currentStep?.alertIds   ?? []);
  const activeSet   = new Set(currentStep?.activeIds  ?? []);
  const pulseSet    = new Set(currentStep?.pulseConnIds ?? []);

  const getNodeState = (id: string): NodeState => {
    if (resolved)        return 'resolved';
    if (alertSet.has(id)) return 'alert';
    if (activeSet.has(id)) return 'active';
    return 'idle';
  };

  // Subtree highlight
  const focusId    = locked ?? hovered;
  const subtreeIds = focusId ? getSubtreeIds(focusId) : null;
  const isDimmedNode = (id: string)  => subtreeIds !== null && !subtreeIds.has(id);
  const isDimmedConn = (c: Conn)     => subtreeIds !== null && (!subtreeIds.has(c.fromId) || !subtreeIds.has(c.toId));
  const isZoneDimmed = (gId: string) => {
    if (subtreeIds === null) return false;
    return !subtreeIds.has(gId) && !NODES.some(n => n.parentId === gId && subtreeIds.has(n.id));
  };

  const tooltipNode = (locked ?? hovered) ? nodeById[locked ?? hovered!] : null;

  const getTooltipTransform = (cx: number) => {
    if (cx < VB_W * 0.2) return 'translate(0%, -108%)';
    if (cx > VB_W * 0.8) return 'translate(-100%, -108%)';
    return 'translate(-50%, -108%)';
  };

  const handleNodeClick = useCallback((id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setLocked(prev => prev === id ? null : id);
  }, []);

  return (
    <section className="bg-paper py-20 border-t border-black/5 overflow-hidden">
      <div className="max-w-7xl mx-auto px-6">

        {/* ── Header ── */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="mb-10"
        >
          <span className="text-[10px] font-mono tracking-[0.25em] text-steel uppercase block mb-3">
            Meet the team
          </span>
          <h2 className="text-3xl md:text-4xl font-bold text-ink tracking-tight">
            13 agents.{' '}
            <span className="text-accent">Every one autonomous.</span>
          </h2>
          <p className="text-steel text-base mt-2 font-light max-w-xl">
            Each agent runs independently on its own schedule, self-heals on failure, and escalates only when genuinely needed.
          </p>
        </motion.div>

        {/* ── SVG diagram (md+) ── */}
        <div className="hidden md:block">

          {/* Top bar: live log line + cycle counter */}
          <div className="h-7 mb-2 flex items-center justify-between">
            <AnimatePresence mode="wait">
              {currentStep ? (
                <motion.div
                  key={step}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.22 }}
                  className="flex items-center gap-2 font-mono text-[11px]"
                >
                  <span className="text-steel/40">›</span>
                  <span className="font-semibold" style={{ color: currentStep.msgColor }}>
                    {currentStep.prefix}
                  </span>
                  <span className="text-steel/40">·</span>
                  <span className="text-ink/60">{currentStep.msg}</span>
                </motion.div>
              ) : (
                <motion.div
                  key="idle"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.4 }}
                  className="flex items-center gap-2 font-mono text-[11px] text-steel/50"
                >
                  <span>›</span>
                  <motion.span
                    animate={{ opacity: [1, 0, 1] }}
                    transition={{ repeat: Infinity, duration: 1.1 }}
                    className="w-1.5 h-3 bg-steel/30 inline-block rounded-sm"
                  />
                  <span>13 agents healthy · offline=0 · cycle 300s</span>
                </motion.div>
              )}
            </AnimatePresence>
            {cycleCount > 0 && (
              <motion.span
                key={cycleCount}
                initial={{ opacity: 0, scale: 0.85 }}
                animate={{ opacity: 1, scale: 1 }}
                className="font-mono text-[9px] text-steel/40 bg-black/[0.03] px-2 py-0.5 rounded-full"
              >
                cycle #{cycleCount}
              </motion.span>
            )}
          </div>

          {/* Micro hint — vanishes after first lock */}
          <AnimatePresence>
            {!locked && (
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="text-[9px] font-mono text-steel/30 mb-2 select-none"
              >
                hover to inspect · click to pin
              </motion.p>
            )}
          </AnimatePresence>

          {/* SVG wrapper */}
          <div
            className="relative w-full"
            style={{ paddingBottom: `${(VB_H / VB_W) * 100}%`, willChange: 'transform' }}
            onClick={() => setLocked(null)}
          >
            <svg
              ref={svgRef}
              viewBox={`0 0 ${VB_W} ${VB_H}`}
              className="absolute inset-0 w-full h-full"
              style={{ contain: 'paint layout' }}
            >
              <defs>
                {CONNS.map(c => (
                  <path key={`def-${c.id}`} id={`path-${c.id}`} d={c.pathD} />
                ))}
                <filter id="afm-shadow" x="-20%" y="-20%" width="140%" height="140%">
                  <feDropShadow dx="0" dy="2" stdDeviation="3" floodColor="#000" floodOpacity="0.07" />
                </filter>
              </defs>

              {/* ── Tier labels (left Y-axis) ── */}
              {TIER_LABELS.map(({ y, label }) => (
                <text
                  key={label}
                  x="4" y={y}
                  textAnchor="start" dominantBaseline="middle"
                  fontFamily={MONO}
                  fontSize="7" fontWeight="600"
                  fill="#71717A" opacity="0.4"
                  style={{ letterSpacing: '0.08em' }}
                >
                  {label}
                </text>
              ))}

              {/* ── Tier separator lines ── */}
              <line x1="42" y1="138" x2={VB_W - 4} y2="138" stroke="#0A0A0A" strokeOpacity="0.04" strokeWidth="1" />
              <line x1="42" y1="286" x2={VB_W - 4} y2="286" stroke="#0A0A0A" strokeOpacity="0.04" strokeWidth="1" />

              {/* ── Worker group zone backgrounds ── */}
              {ZONES.map(z => (
                <rect
                  key={z.guardianId}
                  x={z.x} y={z.y} width={z.w} height={z.h}
                  rx="14"
                  fill={z.color}
                  opacity={isZoneDimmed(z.guardianId) ? 0.02 : 0.05}
                  style={{ transition: 'opacity 0.25s' }}
                />
              ))}

              {/* ── Connections ── */}
              {CONNS.map((c, ci) => {
                const isPulsing = pulseSet.has(c.id);
                const dimmed    = isDimmedConn(c);
                return (
                  <g key={c.id} opacity={dimmed ? 0.07 : 1} style={{ transition: 'opacity 0.2s' }}>
                    <path
                      d={c.pathD} fill="none"
                      stroke={c.color}
                      strokeWidth={isPulsing ? 2 : 1.5}
                      strokeOpacity={isPulsing ? 0.55 : 0.15}
                    />
                    {/* Idle traveling dot */}
                    <circle r="2.8" fill={c.color} opacity={isPulsing ? 0 : 0.45}>
                      <animateMotion
                        dur={`${3 + (ci % 5) * 0.7}s`}
                        repeatCount="indefinite"
                        begin={`${ci * 0.35}s`}
                      >
                        <mpath href={`#path-${c.id}`} />
                      </animateMotion>
                    </circle>
                    {/* Incident pulse dot */}
                    {isPulsing && (
                      <circle r="4" fill={c.color} opacity="0.92">
                        <animateMotion dur="0.75s" repeatCount="indefinite" begin="0s">
                          <mpath href={`#path-${c.id}`} />
                        </animateMotion>
                      </circle>
                    )}
                  </g>
                );
              })}

              {/* ── Nodes ── */}
              {NODES.map(node => {
                const state     = getNodeState(node.id);
                const isHov     = hovered === node.id;
                const isLocked  = locked  === node.id;
                const dimmed    = isDimmedNode(node.id);
                const isHighlit = state === 'alert' || state === 'active';

                const borderColor =
                  state === 'alert'    ? '#F59E0B' :
                  state === 'active'   ? node.color :
                  state === 'resolved' ? '#10B981' :
                  (isHov || isLocked)  ? node.color : '#e5e7eb';

                const textColor = (state !== 'idle' || isHov || isLocked) ? node.color : '#0A0A0A';
                const x = node.cx - node.w / 2;
                const y = node.cy - node.h / 2;
                const nameFontSize = node.tier === 1 ? 11.5 : node.tier === 2 ? 10 : 9;
                const ringR = Math.max(node.w, node.h) / 2 + 4;

                return (
                  <g
                    key={node.id}
                    transform={`translate(${x}, ${y})`}
                    onMouseEnter={() => setHovered(node.id)}
                    onMouseLeave={() => setHovered(null)}
                    onClick={(e) => handleNodeClick(node.id, e)}
                    opacity={dimmed ? 0.18 : 1}
                    style={{ cursor: 'pointer', transition: 'opacity 0.2s' }}
                  >
                    {/* ── Sonar pulse ring (active / alert nodes) ── */}
                    {isHighlit && (
                      <circle cx={node.w / 2} cy={node.h / 2} r={ringR} fill="none" stroke={borderColor} strokeWidth="1.5">
                        <animate attributeName="r"       values={`${ringR};${ringR + 18};${ringR + 18}`} dur="1.4s" repeatCount="indefinite" />
                        <animate attributeName="opacity" values="0.5;0;0"                                dur="1.4s" repeatCount="indefinite" />
                      </circle>
                    )}

                    {/* ── Glow backdrop ── */}
                    {(state !== 'idle' || isHov || isLocked) && (
                      <rect
                        x="-4" y="-4" width={node.w + 8} height={node.h + 8} rx="14"
                        fill={borderColor} opacity="0.11"
                      />
                    )}

                    {/* ── Card ── */}
                    <rect
                      width={node.w} height={node.h} rx="10"
                      fill="white"
                      stroke={borderColor}
                      strokeWidth={(state !== 'idle' || isHov || isLocked) ? 1.5 : 1}
                      filter="url(#afm-shadow)"
                    />

                    {/* Lock ring (double-border) */}
                    {isLocked && (
                      <rect x="-2.5" y="-2.5" width={node.w + 5} height={node.h + 5} rx="12"
                        fill="none" stroke={node.color} strokeWidth="0.75" opacity="0.35"
                      />
                    )}

                    {/* Left accent bar */}
                    <rect x="0" y="0" width="3.5" height={node.h} rx="10" fill={node.color} opacity="0.75" />

                    {/* Status dot (top-right) */}
                    <circle cx={node.w - 9} cy={9} r="3"
                      fill={state === 'alert' ? '#F59E0B' : '#10B981'}
                    >
                      {state === 'alert' && (
                        <>
                          <animate attributeName="fill"    values="#F59E0B;#fff;#F59E0B"  dur="0.65s" repeatCount="indefinite" />
                          <animate attributeName="r"       values="3;4.5;3"               dur="0.65s" repeatCount="indefinite" />
                        </>
                      )}
                      {state !== 'alert' && (
                        <animate attributeName="fill" values="#10B981;#6ee7b7;#10B981" dur="3s" repeatCount="indefinite" />
                      )}
                    </circle>

                    {/* Orchestrator cycle badge */}
                    {node.id === 'orchestrator' && cycleCount > 0 && (
                      <text
                        x={node.w - 9} y={node.h - 8}
                        textAnchor="middle" dominantBaseline="middle"
                        fontFamily={MONO} fontSize="7" fill="#71717A" opacity="0.55"
                      >
                        #{cycleCount}
                      </text>
                    )}

                    {/* Name */}
                    <text
                      x={node.w / 2 + 1.75} y={node.h * 0.46}
                      textAnchor="middle" dominantBaseline="middle"
                      fontFamily={MONO} fontSize={nameFontSize} fontWeight="600"
                      fill={textColor}
                    >
                      {node.label}
                    </text>

                    {/* Sub-label */}
                    <text
                      x={node.w / 2 + 1.75} y={node.h * 0.73}
                      textAnchor="middle" dominantBaseline="middle"
                      fontFamily={MONO} fontSize="7.5" fill="#71717A" opacity="0.85"
                    >
                      {node.tier === 1 ? node.model : `↻ ${node.interval}`}
                    </text>
                  </g>
                );
              })}
            </svg>

            {/* ── Tooltip overlay ── */}
            <AnimatePresence>
              {tooltipNode && (
                <motion.div
                  key={tooltipNode.id}
                  initial={{ opacity: 0, y: 6, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 6, scale: 0.96 }}
                  transition={{ duration: 0.14 }}
                  className="absolute z-20"
                  style={{
                    left: `${(tooltipNode.cx / VB_W) * 100}%`,
                    top: `${((tooltipNode.cy - tooltipNode.h / 2) / VB_H) * 100}%`,
                    transform: getTooltipTransform(tooltipNode.cx),
                    width: '252px',
                    pointerEvents: locked ? 'auto' : 'none',
                  }}
                  onClick={e => e.stopPropagation()}
                >
                  <div className="bg-white/96 backdrop-blur-xl border border-black/8 rounded-2xl shadow-2xl p-3.5">
                    <div className="flex items-center gap-2 mb-2">
                      <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: tooltipNode.color }} />
                      <span className="font-mono text-[11px] font-semibold text-ink truncate">{tooltipNode.id}</span>
                      {locked === tooltipNode.id && (
                        <span className="text-[8px] font-mono text-accent bg-accent/10 px-1.5 py-0.5 rounded flex-shrink-0">pinned</span>
                      )}
                      <span className="ml-auto text-[9px] font-mono text-success bg-success/10 px-1.5 py-0.5 rounded flex-shrink-0">live</span>
                    </div>
                    <p className="text-[10px] text-steel leading-relaxed mb-2.5">{tooltipNode.description}</p>
                    <div className="text-[9px] font-mono text-ink/45 bg-black/[0.03] rounded-lg px-2 py-1.5 mb-2 leading-snug">
                      ↺ {tooltipNode.heals}
                    </div>
                    <div className="flex items-center justify-between text-[9px] font-mono text-steel/60 pt-1.5 border-t border-black/5">
                      <span>{tooltipNode.model}</span>
                      <span>↻ {tooltipNode.interval}</span>
                    </div>
                    {locked && (
                      <button
                        onClick={() => setLocked(null)}
                        className="mt-2 w-full text-[9px] font-mono text-steel/40 hover:text-ink transition-colors text-center"
                      >
                        click to unpin ×
                      </button>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* ── Scrolling log terminal ── */}
          <AnimatePresence>
            {logLines.length > 0 && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.28 }}
                className="mt-3 overflow-hidden"
              >
                <div className="bg-[#FAFAFA] border border-black/5 rounded-xl px-4 py-3 font-mono text-[10px] space-y-1.5">
                  {logLines.map(line => (
                    <motion.div
                      key={line.key}
                      initial={{ opacity: 0, x: -6 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.18 }}
                      className="flex items-start gap-2"
                    >
                      <span className="text-steel/40 flex-shrink-0">›</span>
                      <span className="font-semibold flex-shrink-0" style={{ color: line.color }}>{line.prefix}</span>
                      <span className="text-steel/40 flex-shrink-0">·</span>
                      <span className="text-ink/55">{line.msg}</span>
                    </motion.div>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* ── Footer stats ── */}
          <div className="flex items-center justify-between mt-4 text-[10px] font-mono text-steel/50">
            <div className="flex items-center gap-1.5">
              {NODES.map(n => (
                <div key={n.id} className="w-1.5 h-1.5 rounded-full" style={{ background: n.color, opacity: 0.5 }} />
              ))}
            </div>
            <span>{NODES.length} agents · all healthy · offline=0</span>
          </div>
        </div>

        {/* ── Mobile: tiered card grid ── */}
        <div className="md:hidden space-y-6">
          {([1, 2, 3] as const).map(tier => {
            const tierNodes  = NODES.filter(n => n.tier === tier);
            const tierLabel  = tier === 1 ? 'Orchestrator' : tier === 2 ? 'Guardians' : 'Workers';
            return (
              <div key={tier}>
                <div className="flex items-center gap-3 mb-2.5">
                  <span className="text-[9px] font-mono font-semibold text-steel/50 uppercase tracking-widest whitespace-nowrap">
                    Tier {tier} — {tierLabel}
                  </span>
                  <div className="flex-1 h-px bg-black/6" />
                </div>
                <div className="grid grid-cols-2 gap-2.5">
                  {tierNodes.map((node, i) => (
                    <motion.div
                      key={node.id}
                      initial={{ opacity: 0, y: 10 }}
                      whileInView={{ opacity: 1, y: 0 }}
                      viewport={{ once: true }}
                      transition={{ duration: 0.35, delay: i * 0.05 }}
                      className="glass-card p-3 flex flex-col gap-1.5"
                    >
                      <div className="flex items-center justify-between">
                        <div className="w-2 h-2 rounded-full" style={{ background: node.color }} />
                        <div className="flex items-center gap-1">
                          <div className="w-1 h-1 rounded-full bg-success" />
                          <span className="text-[8px] font-mono text-success">live</span>
                        </div>
                      </div>
                      <h3 className="text-[10px] font-mono font-semibold" style={{ color: node.color }}>
                        {node.id}
                      </h3>
                      <p className="text-steel text-[9px] leading-relaxed line-clamp-2">{node.description}</p>
                      <div className="flex items-center justify-between pt-1 border-t border-black/5 mt-auto">
                        <span className="text-[8px] font-mono text-steel/60 truncate max-w-[110px]">{node.model}</span>
                        <span className="text-[8px] font-mono text-steel/50 flex-shrink-0">↻ {node.interval}</span>
                      </div>
                    </motion.div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

      </div>
    </section>
  );
}
