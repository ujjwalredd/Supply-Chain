import { useRef, useState } from 'react';
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
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isHovered, setIsHovered] = useState(false);

  const handleMouse = (e: MouseEvent<HTMLDivElement>) => {
    const { clientX, clientY } = e;
    const { height, width, left, top } = ref.current!.getBoundingClientRect();
    const middleX = clientX - (left + width / 2);
    const middleY = clientY - (top + height / 2);

    setPosition({ x: middleX * strength, y: middleY * strength });
    setIsHovered(true);
  };

  const reset = () => {
    setPosition({ x: 0, y: 0 });
    setIsHovered(false);
  };

  const content = (
    <motion.div
      className={`${className} relative overflow-hidden`}
      animate={{ 
        x: position.x, 
        y: position.y,
        scale: isHovered ? 1.02 : 1,
      }}
      transition={{ type: 'spring', stiffness: 200, damping: 15, mass: 0.1 }}
    >
      {/* Shine sweep on hover */}
      <motion.div 
        className="absolute inset-0 pointer-events-none"
        initial={{ x: '-100%', opacity: 0 }}
        animate={isHovered ? { x: '200%', opacity: 0.15 } : { x: '-100%', opacity: 0 }}
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
      onMouseMove={handleMouse} 
      onMouseLeave={reset} 
      className="inline-block p-4" // padding = magnetic field radius
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
