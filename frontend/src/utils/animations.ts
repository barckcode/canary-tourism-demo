/**
 * Shared Framer Motion animation variants used across pages.
 */
import type { Variants } from "framer-motion";

/** Stagger children on enter. */
export const stagger: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } },
};

/** Fade-up entrance for individual elements. */
export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};
