import { useRef, useState, useCallback } from 'react';
import type { MouseEvent } from 'react';
import { motion } from 'framer-motion';

interface MagneticButtonProps {
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
  href?: string;
  target?: string;
  rel?: string;
  strength?: number;
}

export function MagneticButton({ children, className = '', onClick, href, target, rel, strength = 0.3 }: MagneticButtonProps) {
  const ref = useRef<HTMLDivElement>(null);
  // Cache rect on enter, not every move, to avoid forced layout per frame
  const rectCache = useRef<DOMRect | null>(null);
  const [state, setState] = useState({ x: 0, y: 0, hovered: false });

  const handleEnter = useCallback(() => {
    rectCache.current = ref.current?.getBoundingClientRect() ?? null;
  }, []);

  const handleMouse = useCallback((e: MouseEvent<HTMLDivElement>) => {
    const rect = rectCache.current;
    if (!rect) return;
    const middleX = e.clientX - (rect.left + rect.width / 2);
    const middleY = e.clientY - (rect.top + rect.height / 2);
    setState({ x: middleX * strength, y: middleY * strength, hovered: true });
  }, [strength]);

  const reset = useCallback(() => {
    rectCache.current = null;
    setState({ x: 0, y: 0, hovered: false });
  }, []);

  const content = (
    <motion.div
      className={`${className} relative overflow-hidden`}
      animate={{
        x: state.x,
        y: state.y,
        scale: state.hovered ? 1.02 : 1,
      }}
      transition={{ type: 'spring', stiffness: 200, damping: 15, mass: 0.1 }}
      style={{ willChange: 'transform' }}
    >
      {/* Shine sweep on hover */}
      <motion.div
        className="absolute inset-0 pointer-events-none"
        initial={{ x: '-100%', opacity: 0 }}
        animate={state.hovered ? { x: '200%', opacity: 0.15 } : { x: '-100%', opacity: 0 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        style={{
          background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.5), transparent)',
          width: '50%',
        }}
      />
      {children}
    </motion.div>
  );

  return (
    <div
      ref={ref}
      onMouseEnter={handleEnter}
      onMouseMove={handleMouse}
      onMouseLeave={reset}
      className="inline-block p-4"
    >
      {href ? (
        <a href={href} target={target} rel={rel} onClick={onClick} className="inline-block">
          {content}
        </a>
      ) : (
        <button onClick={onClick} className="inline-block">
          {content}
        </button>
      )}
    </div>
  );
}
