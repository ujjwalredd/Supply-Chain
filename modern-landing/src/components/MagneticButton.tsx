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
}

export function MagneticButton({ children, className = '', onClick, href, target, rel }: MagneticButtonProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ x: 0, y: 0 });

  const handleMouse = (e: MouseEvent<HTMLDivElement>) => {
    const { clientX, clientY } = e;
    const { height, width, left, top } = ref.current!.getBoundingClientRect();
    const middleX = clientX - (left + width / 2);
    const middleY = clientY - (top + height / 2);

    // Magnetic pull strength (higher is more pull, max is 0.5 usually)
    setPosition({ x: middleX * 0.2, y: middleY * 0.2 });
  };

  const reset = () => {
    setPosition({ x: 0, y: 0 });
  };

  const content = (
    <motion.div
      className={className}
      animate={{ x: position.x, y: position.y }}
      transition={{ type: 'spring', stiffness: 150, damping: 15, mass: 0.1 }}
    >
      {children}
    </motion.div>
  );

  return (
    <div 
      ref={ref} 
      onMouseMove={handleMouse} 
      onMouseLeave={reset} 
      className="inline-block p-4" // padding acts as the "magnetic field" radius
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
