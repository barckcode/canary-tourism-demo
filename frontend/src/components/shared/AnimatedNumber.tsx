import { useEffect, useState } from "react";
import { useSpring, useTransform, motion, useReducedMotion } from "framer-motion";

interface AnimatedNumberProps {
  value: number;
  format?: (n: number) => string;
  className?: string;
}

export default function AnimatedNumber({
  value,
  format = (n) => n.toLocaleString(),
  className = "",
}: AnimatedNumberProps) {
  const isInvalid =
    value == null || Number.isNaN(value) || !Number.isFinite(value);
  const prefersReducedMotion = useReducedMotion();

  const spring = useSpring(0, { duration: 1200 });
  const display = useTransform(spring, (latest) => format(Math.round(latest)));
  const [text, setText] = useState(isInvalid ? "\u2014" : format(0));

  useEffect(() => {
    if (isInvalid) {
      setText("\u2014");
      return;
    }
    if (prefersReducedMotion) {
      setText(format(value));
      return;
    }
    spring.set(value);
  }, [value, spring, isInvalid, prefersReducedMotion, format]);

  useEffect(() => {
    if (isInvalid || prefersReducedMotion) return;
    const unsubscribe = display.on("change", (v) => setText(v));
    return unsubscribe;
  }, [display, isInvalid, prefersReducedMotion]);

  if (prefersReducedMotion) {
    return (
      <span className={`tabular-nums ${className}`}>{text}</span>
    );
  }

  return (
    <motion.span className={`tabular-nums ${className}`}>{text}</motion.span>
  );
}
