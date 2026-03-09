import { useState } from 'react';
import type { MouseEvent } from 'react';
import { motion } from 'framer-motion';

interface TiltCardProps {
  children: React.ReactNode;
  className?: string;
  glareOpacity?: number;
  rotationIntensity?: number;
}

export function TiltCard({ children, className = '', glareOpacity = 0.2, rotationIntensity = 15 }: TiltCardProps) {
  const [rotateX, setRotateX] = useState(0);
  const [rotateY, setRotateY] = useState(0);
  const [glarePosition, setGlarePosition] = useState({ x: 50, y: 50, opacity: 0 });

  const handleMouseMove = (e: MouseEvent<HTMLDivElement>) => {
    const card = e.currentTarget;
    const { left, top, width, height } = card.getBoundingClientRect();

    const mouseX = e.clientX - left;
    const mouseY = e.clientY - top;

    // Calculate rotation (-15 to +15 depending on rotationIntensity)
    const rX = ((mouseY / height) - 0.5) * -rotationIntensity;
    const rY = ((mouseX / width) - 0.5) * rotationIntensity;

    setRotateX(rX);
    setRotateY(rY);

    // Glare moves to follow mouse exactly (percentages 0-100)
    const glareX = (mouseX / width) * 100;
    const glareY = (mouseY / height) * 100;
    
    setGlarePosition({ x: glareX, y: glareY, opacity: glareOpacity });
  };

  const handleMouseLeave = () => {
    setRotateX(0);
    setRotateY(0);
    setGlarePosition({ ...glarePosition, opacity: 0 });
  };

  return (
    <motion.div
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      animate={{
        rotateX,
        rotateY,
      }}
      transition={{ type: 'spring', stiffness: 300, damping: 20 }}
      style={{ perspective: 1000 }} // Gives it the true 3D depth
      className={`relative overflow-hidden group ${className}`}
    >
      {/* Glare effect tracking mouse */}
      <div 
        className="absolute inset-0 pointer-events-none z-50 transition-opacity duration-300 rounded-inherit"
        style={{
          opacity: glarePosition.opacity,
          background: `radial-gradient(circle at ${glarePosition.x}% ${glarePosition.y}%, rgba(255,255,255,0.8) 0%, rgba(255,255,255,0) 60%)`,
        }}
      />
      {children}
    </motion.div>
  );
}
