import { motion } from "framer-motion";
import { ReactNode } from "react";

interface PanelProps {
  title?: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
  noPadding?: boolean;
}

export default function Panel({
  title,
  subtitle,
  children,
  className = "",
  noPadding = false,
}: PanelProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className={`glass-panel ${className}`}
    >
      {(title || subtitle) && (
        <div className={`${noPadding ? "px-6 pt-5 pb-2" : "px-6 pt-5 pb-0"}`}>
          {title && (
            <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
              {title}
            </h2>
          )}
          {subtitle && (
            <p className="text-xs text-gray-500 mt-0.5">{subtitle}</p>
          )}
        </div>
      )}
      <div className={noPadding ? "" : "p-6"}>{children}</div>
    </motion.div>
  );
}
