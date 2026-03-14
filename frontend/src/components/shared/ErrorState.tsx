import { motion } from "framer-motion";

interface ErrorStateProps {
  /** Custom error message. Defaults to a generic message. */
  message?: string;
  /** Callback fired when the user clicks the Retry button. */
  onRetry?: () => void;
}

/**
 * Reusable error state component displayed when an API call fails.
 * Shows an error icon, a descriptive message and an optional retry button.
 */
export default function ErrorState({
  message = "Failed to load data. Please try again.",
  onRetry,
}: ErrorStateProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className="flex flex-col items-center justify-center gap-4 p-8 rounded-2xl bg-gray-900/60 border border-red-700/30"
      role="alert"
    >
      <div className="w-12 h-12 rounded-full bg-red-500/15 flex items-center justify-center">
        <svg
          className="w-6 h-6 text-red-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z"
          />
        </svg>
      </div>

      <div className="text-center">
        <h3 className="text-sm font-semibold text-gray-200 mb-1">
          Something went wrong
        </h3>
        <p className="text-xs text-gray-500 max-w-xs">{message}</p>
      </div>

      {onRetry && (
        <button
          onClick={onRetry}
          className="px-4 py-2 text-xs font-medium rounded-lg bg-ocean-600 hover:bg-ocean-500 text-white transition-colors"
        >
          Retry
        </button>
      )}
    </motion.div>
  );
}
