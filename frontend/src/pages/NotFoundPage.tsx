import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { fadeUp } from "../utils/animations";

export default function NotFoundPage() {
  const { t } = useTranslation();

  return (
    <motion.div
      className="flex flex-col items-center justify-center h-[60vh] text-center px-4"
      variants={fadeUp}
      initial="hidden"
      animate="show"
    >
      <h1 className="text-6xl font-bold text-gray-500 mb-4">404</h1>
      <h2 className="text-xl font-semibold text-white mb-2">
        {t("notFound.title")}
      </h2>
      <p className="text-gray-400 mb-8">{t("notFound.message")}</p>
      <Link
        to="/"
        className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-ocean-600 hover:bg-ocean-500 text-white text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-ocean-400 focus:ring-offset-2 focus:ring-offset-gray-900"
      >
        <svg
          className="w-4 h-4"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M10 19l-7-7m0 0l7-7m-7 7h18"
          />
        </svg>
        {t("notFound.backHome")}
      </Link>
    </motion.div>
  );
}
