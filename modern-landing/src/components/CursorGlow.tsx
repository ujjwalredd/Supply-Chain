import { useEffect } from 'react';
import { motion, useMotionValue, useSpring } from 'framer-motion';

export function CursorGlow() {
  const cursorX = useMotionValue(-100);
  const cursorY = useMotionValue(-100);

  const springX = useSpring(cursorX, { stiffness: 80, damping: 20 });
  const springY = useSpring(cursorY, { stiffness: 80, damping: 20 });

  useEffect(() => {
    const move = (e: MouseEvent) => {
      cursorX.set(e.clientX);
      cursorY.set(e.clientY);
    };
    window.addEventListener('mousemove', move);
    return () => window.removeEventListener('mousemove', move);
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
      }}
    />
  );
}
