'use client';
import { motion, useReducedMotion } from 'framer-motion';

export default function Reveal({ children, delay = 0, className = '' }: { children: React.ReactNode; delay?: number; className?: string }) {
  const reduce = useReducedMotion();
  return (
    <motion.div className={className} initial={reduce ? false : { opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.15 }} transition={{ duration: reduce ? 0.01 : 0.6, delay, ease: [0.2, 0.75, 0.25, 1] }}>
      {children}
    </motion.div>
  );
}
