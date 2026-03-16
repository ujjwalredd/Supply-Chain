import { useEffect } from 'react';
import { motion, useMotionValue, useSpring } from 'framer-motion';

export function CursorGlow() {
  const cursorX = useMotionValue(-100);
  const cursorY = useMotionValue(-100);

  const springX = useSpring(cursorX, { stiffness: 60, damping: 25 });
  const springY = useSpring(cursorY, { stiffness: 60, damping: 25 });

  useEffect(() => {
    let rafId: number;
    let pendingX = -100;
    let pendingY = -100;

    const move = (e: MouseEvent) => {
      pendingX = e.clientX;
      pendingY = e.clientY;
      if (rafId) return;
      rafId = requestAnimationFrame(() => {
        cursorX.set(pendingX);
        cursorY.set(pendingY);
        rafId = 0;
      });
    };
    window.addEventListener('mousemove', move, { passive: true });
    return () => {
      window.removeEventListener('mousemove', move);
      if (rafId) cancelAnimationFrame(rafId);
    };
  }, [cursorX, cursorY]);

  return (
    <motion.div
      className="fixed pointer-events-none z-0"
      style={{
        left: springX,
        top: springY,
        translateX: '-50%',
        translateY: '-50%',
        width: 500,
        height: 500,
        background: 'radial-gradient(circle, rgba(0,112,243,0.04) 0%, transparent 70%)',
        borderRadius: '50%',
        willChange: 'transform',
      }}
    />
  );
}
