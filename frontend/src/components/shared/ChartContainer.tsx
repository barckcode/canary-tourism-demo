import { ReactNode, useRef, useState, useEffect } from "react";

interface ChartContainerProps {
  children: (dimensions: { width: number; height: number }) => ReactNode;
  height?: number;
  className?: string;
}

export default function ChartContainer({
  children,
  height = 400,
  className = "",
}: ChartContainerProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setWidth(entry.contentRect.width);
      }
    });
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={ref} className={`w-full ${className}`} style={{ height }}>
      {width > 0 && children({ width, height })}
    </div>
  );
}
