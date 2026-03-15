import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';

// Compute points along a cubic bezier curve
function cubicBezierPoints(
  p0: { x: number; y: number },
  cp1: { x: number; y: number },
  cp2: { x: number; y: number },
  p3: { x: number; y: number },
  steps = 30
) {
  return Array.from({ length: steps + 1 }, (_, i) => {
    const t = i / steps;
    const mt = 1 - t;
    return {
      x: mt ** 3 * p0.x + 3 * mt ** 2 * t * cp1.x + 3 * mt * t ** 2 * cp2.x + t ** 3 * p3.x,
      y: mt ** 3 * p0.y + 3 * mt ** 2 * t * cp1.y + 3 * mt * t ** 2 * cp2.y + t ** 3 * p3.y,
    };
  });
}

const NODES = [
  { id: 'hamburg',    label: 'Hamburg',    x: 98,  y: 52  },
  { id: 'rotterdam',  label: 'Rotterdam',  x: 82,  y: 95  },
  { id: 'chicago',    label: 'Chicago',    x: 72,  y: 180 },
  { id: 'la',         label: 'Los Angeles',x: 42,  y: 255 },
  { id: 'dubai',      label: 'Dubai',      x: 305, y: 100 },
  { id: 'mumbai',     label: 'Mumbai',     x: 345, y: 178, alert: true },
  { id: 'singapore',  label: 'Singapore',  x: 418, y: 258 },
  { id: 'shanghai',   label: 'Shanghai',   x: 448, y: 92  },
];

// Edges as SVG path strings
const EDGES = [
  'M98,52 C92,70 86,82 82,95',
  'M82,95 C80,130 76,158 72,180',
  'M72,180 C62,210 50,232 42,255',
  'M98,52 C170,50 248,70 305,100',
  'M305,100 C318,128 336,155 345,178',
  'M305,100 C355,95 405,93 448,92',
  'M345,178 C372,208 398,238 418,258',
  'M448,92 C442,158 432,218 418,258',
  'M72,180 C145,158 235,120 305,100',
  'M42,255 C128,302 318,308 418,258',
];

// Packets: { path string, dur, delay, color }
const PACKETS = [
  { path: 'M98,52 C170,50 248,70 305,100',      dur: 3.2, delay: 0,   color: '#0070F3' },
  { path: 'M305,100 C318,128 336,155 345,178',   dur: 2.2, delay: 1.5, color: '#F59E0B' }, // to alert node
  { path: 'M305,100 C355,95 405,93 448,92',      dur: 2.8, delay: 0.8, color: '#0070F3' },
  { path: 'M345,178 C372,208 398,238 418,258',   dur: 2.5, delay: 3.2, color: '#10B981' }, // resolved
  { path: 'M448,92 C442,158 432,218 418,258',    dur: 3.0, delay: 0.4, color: '#0070F3' },
  { path: 'M72,180 C145,158 235,120 305,100',    dur: 3.5, delay: 1.2, color: '#0070F3' },
  { path: 'M42,255 C128,302 318,308 418,258',    dur: 4.2, delay: 2.0, color: '#0070F3' },
  { path: 'M82,95 C80,130 76,158 72,180',        dur: 2.0, delay: 0.6, color: '#0070F3' },
  { path: 'M98,52 C92,70 86,82 82,95',           dur: 1.5, delay: 2.8, color: '#10B981' },
];

function PacketDot({ path, dur, delay, color }: { path: string; dur: number; delay: number; color: string }) {
  // Parse the path to extract start/end and control points for bezier
  // Format: M x0,y0 C cp1x,cp1y cp2x,cp2y x3,y3
  const parsed = path.match(/M\s*([\d.]+),([\d.]+)\s+C\s*([\d.]+),([\d.]+)\s+([\d.]+),([\d.]+)\s+([\d.]+),([\d.]+)/);
  if (!parsed) return null;

  const [, x0, y0, cp1x, cp1y, cp2x, cp2y, x3, y3] = parsed.map(Number);
  const pts = cubicBezierPoints(
    { x: x0, y: y0 },
    { x: cp1x, y: cp1y },
    { x: cp2x, y: cp2y },
    { x: x3, y: y3 },
    30
  );

  return (
    <motion.circle
      cx={0}
      cy={0}
      r={2.5}
      fill={color}
      animate={{
        x: pts.map(p => p.x),
        y: pts.map(p => p.y),
        opacity: [0, 0, 1, 1, 1, 1, 0],
      }}
      transition={{
        duration: dur,
        delay,
        repeat: Infinity,
        ease: 'linear',
        repeatDelay: 1.2,
      }}
      style={{ filter: `drop-shadow(0 0 4px ${color})` }}
    />
  );
}

export function NetworkSVG() {
  const [alertPhase, setAlertPhase] = useState<'alert' | 'resolving' | 'resolved'>('resolved');
  const cycleRef = useRef<ReturnType<typeof setTimeout>>(null);

  useEffect(() => {
    function cycle() {
      setAlertPhase('alert');
      cycleRef.current = setTimeout(() => {
        setAlertPhase('resolving');
        cycleRef.current = setTimeout(() => {
          setAlertPhase('resolved');
          cycleRef.current = setTimeout(cycle, 5000);
        }, 2000);
      }, 3000);
    }
    cycleRef.current = setTimeout(cycle, 2000);
    return () => { if (cycleRef.current) clearTimeout(cycleRef.current); };
  }, []);

  const mumbai = NODES.find(n => n.id === 'mumbai')!;
  const alertColor = alertPhase === 'alert' ? '#EF4444' : alertPhase === 'resolving' ? '#F59E0B' : '#10B981';
  const alertLabel = alertPhase === 'alert' ? '⚠ +72h delay' : alertPhase === 'resolving' ? '↻ rerouting…' : '✓ resolved';

  return (
    <svg
      viewBox="0 0 520 310"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="w-full h-full"
    >
      {/* Ambient glow behind the network */}
      <defs>
        <radialGradient id="net-glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#0070F3" stopOpacity="0.06" />
          <stop offset="100%" stopColor="#0070F3" stopOpacity="0" />
        </radialGradient>
        <filter id="node-glow">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>

      <ellipse cx="245" cy="155" rx="240" ry="140" fill="url(#net-glow)" />

      {/* Edges */}
      {EDGES.map((d, i) => (
        <path
          key={i}
          d={d}
          stroke="rgba(255,255,255,0.07)"
          strokeWidth="1"
          strokeLinecap="round"
        />
      ))}

      {/* Animated packets */}
      {PACKETS.map((p, i) => (
        <PacketDot key={i} {...p} />
      ))}

      {/* Nodes */}
      {NODES.map((node) => {
        const isAlert = node.alert;
        const nodeColor = isAlert ? alertColor : '#0070F3';
        return (
          <g key={node.id}>
            {/* Pulse ring */}
            <motion.circle
              cx={node.x}
              cy={node.y}
              r={isAlert ? 14 : 10}
              fill={nodeColor}
              fillOpacity={isAlert ? 0.08 : 0.04}
              animate={isAlert ? {
                r: [10, 18, 10],
                fillOpacity: [0.06, 0.02, 0.06],
              } : {
                r: [8, 12, 8],
                fillOpacity: [0.03, 0.01, 0.03],
              }}
              transition={{ duration: isAlert ? 1.5 : 3, repeat: Infinity, ease: 'easeInOut' }}
            />
            {/* Node dot */}
            <circle
              cx={node.x}
              cy={node.y}
              r={isAlert ? 5 : 4}
              fill={nodeColor}
              opacity={0.9}
              filter={isAlert ? 'url(#node-glow)' : undefined}
            />
            {/* Inner dot */}
            <circle cx={node.x} cy={node.y} r={isAlert ? 2.5 : 1.8} fill="white" opacity={0.9} />
            {/* Label */}
            <text
              x={node.x}
              y={node.y - 10}
              textAnchor="middle"
              fontSize="7.5"
              fill={isAlert ? alertColor : 'rgba(255,255,255,0.5)'}
              fontFamily="JetBrains Mono, monospace"
              fontWeight={isAlert ? '600' : '400'}
            >
              {node.label}
            </text>
          </g>
        );
      })}

      {/* Mumbai alert bubble */}
      <motion.g
        animate={{ opacity: alertPhase === 'resolved' ? 0 : 1 }}
        transition={{ duration: 0.4 }}
      >
        <rect
          x={mumbai.x + 10}
          y={mumbai.y - 8}
          width={68}
          height={16}
          rx={4}
          fill={alertColor}
          fillOpacity={0.15}
          stroke={alertColor}
          strokeOpacity={0.4}
          strokeWidth={0.5}
        />
        <text
          x={mumbai.x + 44}
          y={mumbai.y + 4}
          textAnchor="middle"
          fontSize="7"
          fill={alertColor}
          fontFamily="JetBrains Mono, monospace"
          fontWeight="600"
        >
          {alertLabel}
        </text>
      </motion.g>
    </svg>
  );
}
