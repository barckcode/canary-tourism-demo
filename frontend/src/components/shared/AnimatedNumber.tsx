import { useEffect, useState } from "react";
import { useSpring, useTransform, motion } from "framer-motion";

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

  const spring = useSpring(0, { duration: 1200 });
  const display = useTransform(spring, (latest) => format(Math.round(latest)));
  const [text, setText] = useState(isInvalid ? "\u2014" : format(0));

  useEffect(() => {
    if (isInvalid) {
      setText("\u2014");
      return;
    }
    spring.set(value);
  }, [value, spring, isInvalid]);

  useEffect(() => {
    if (isInvalid) return;
    const unsubscribe = display.on("change", (v) => setText(v));
    return unsubscribe;
  }, [display, isInvalid]);

  return (
    <motion.span className={`tabular-nums ${className}`}>{text}</motion.span>
  );
}
