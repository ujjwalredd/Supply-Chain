import { useRef, useState, useCallback } from 'react';
import type { MouseEvent } from 'react';
import { motion } from 'framer-motion';

interface TiltCardProps {
  children: React.ReactNode;
  className?: string;
  glareOpacity?: number;
  rotationIntensity?: number;
}

interface TiltState {
  rX: number;
  rY: number;
  glareX: number;
  glareY: number;
  glareVisible: boolean;
}

const IDLE: TiltState = { rX: 0, rY: 0, glareX: 50, glareY: 50, glareVisible: false };

export function TiltCard({ children, className = '', glareOpacity = 0.2, rotationIntensity = 15 }: TiltCardProps) {
  const rectCache = useRef<DOMRect | null>(null);
  const [tilt, setTilt] = useState<TiltState>(IDLE);

  // Cache rect on enter to avoid getBoundingClientRect on every mousemove
  const handleEnter = useCallback((e: MouseEvent<HTMLDivElement>) => {
    rectCache.current = e.currentTarget.getBoundingClientRect();
  }, []);

  const handleMouseMove = useCallback((e: MouseEvent<HTMLDivElement>) => {
    const rect = rectCache.current;
    if (!rect) return;
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    setTilt({
      rX: ((mouseY / rect.height) - 0.5) * -rotationIntensity,
      rY: ((mouseX / rect.width) - 0.5) * rotationIntensity,
      glareX: (mouseX / rect.width) * 100,
      glareY: (mouseY / rect.height) * 100,
      glareVisible: true,
    });
  }, [rotationIntensity]);

  const handleMouseLeave = useCallback(() => {
    rectCache.current = null;
    setTilt(IDLE);
  }, []);

  return (
    <motion.div
      onMouseEnter={handleEnter}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      animate={{ rotateX: tilt.rX, rotateY: tilt.rY }}
      transition={{ type: 'spring', stiffness: 300, damping: 20 }}
      style={{ perspective: 1000, willChange: 'transform' }}
      className={`relative overflow-hidden group ${className}`}
    >
      {/* Glare effect */}
      <div
        className="absolute inset-0 pointer-events-none z-50 transition-opacity duration-300 rounded-inherit"
        style={{
          opacity: tilt.glareVisible ? glareOpacity : 0,
          background: `radial-gradient(circle at ${tilt.glareX}% ${tilt.glareY}%, rgba(255,255,255,0.8) 0%, rgba(255,255,255,0) 60%)`,
        }}
      />
      {children}
    </motion.div>
  );
}
