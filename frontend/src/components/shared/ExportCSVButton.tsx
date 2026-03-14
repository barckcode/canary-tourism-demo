import { useState, useCallback } from "react";
import { motion } from "framer-motion";
import { exportCSV, type CSVMetadata } from "../../utils/csv";

interface ExportCSVButtonProps {
  headers: string[];
  rows: (string | number)[][];
  filename: string;
  metadata?: CSVMetadata;
  /** Disable the button when there is no data to export */
  disabled?: boolean;
  /** Optional accessible label override */
  ariaLabel?: string;
}

export default function ExportCSVButton({
  headers,
  rows,
  filename,
  metadata,
  disabled = false,
  ariaLabel = "Export data as CSV",
}: ExportCSVButtonProps) {
  const [exported, setExported] = useState(false);

  const handleExport = useCallback(() => {
    if (disabled || rows.length === 0) return;
    exportCSV(headers, rows, filename, metadata);
    setExported(true);
    const timer = setTimeout(() => setExported(false), 2000);
    return () => clearTimeout(timer);
  }, [headers, rows, filename, metadata, disabled]);

  return (
    <motion.button
      onClick={handleExport}
      disabled={disabled || rows.length === 0}
      aria-label={ariaLabel}
      whileHover={{ scale: 1.03 }}
      whileTap={{ scale: 0.97 }}
      className={`
        inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-lg
        transition-colors focus:outline-none focus:ring-2 focus:ring-ocean-500/50
        ${
          disabled || rows.length === 0
            ? "bg-gray-800 text-gray-600 cursor-not-allowed"
            : exported
              ? "bg-tropical-600/20 text-tropical-400 border border-tropical-600/30"
              : "bg-ocean-600/20 text-ocean-400 border border-ocean-600/30 hover:bg-ocean-600/30"
        }
      `}
    >
      {exported ? (
        <>
          {/* Checkmark icon */}
          <svg
            className="w-3.5 h-3.5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M5 13l4 4L19 7"
            />
          </svg>
          <span>Exported</span>
        </>
      ) : (
        <>
          {/* Download icon */}
          <svg
            className="w-3.5 h-3.5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
            />
          </svg>
          <span>Export CSV</span>
        </>
      )}
    </motion.button>
  );
}
