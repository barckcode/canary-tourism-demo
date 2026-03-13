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
  const spring = useSpring(0, { duration: 1200 });
  const display = useTransform(spring, (latest) => format(Math.round(latest)));
  const [text, setText] = useState(format(0));

  useEffect(() => {
    spring.set(value);
  }, [value, spring]);

  useEffect(() => {
    const unsubscribe = display.on("change", (v) => setText(v));
    return unsubscribe;
  }, [display]);

  return (
    <motion.span className={`tabular-nums ${className}`}>{text}</motion.span>
  );
}
