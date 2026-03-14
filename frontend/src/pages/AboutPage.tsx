import { motion } from "framer-motion";
import Panel from "../components/layout/Panel";

const stagger = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } },
};

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

const capabilities = [
  {
    title: "Development",
    description:
      "Frontend (React, D3, Deck.gl) and backend (FastAPI, SQLAlchemy) code is written, reviewed, and deployed by AI agents.",
    color: "text-ocean-400",
    icon: (
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"
      />
    ),
  },
  {
    title: "Data Pipelines",
    description:
      "Automated ETL fetches real data from public APIs on scheduled intervals.",
    color: "text-tropical-400",
    icon: (
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4"
      />
    ),
  },
  {
    title: "Machine Learning",
    description:
      "Ensemble forecasting models (SARIMA, Holt-Winters) and tourist segmentation (K-Means) are trained automatically.",
    color: "text-volcanic-400",
    icon: (
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
      />
    ),
  },
  {
    title: "Infrastructure",
    description:
      "Docker containerization, Nginx reverse proxy, Cloudflare SSL/TLS — all configured by AI.",
    color: "text-ocean-300",
    icon: (
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01"
      />
    ),
  },
  {
    title: "Security",
    description:
      "Code reviews, vulnerability scanning, firewall rules, and HTTPS configuration — all managed by AI.",
    color: "text-purple-400",
    icon: (
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
      />
    ),
  },
  {
    title: "Monitoring & Maintenance",
    description:
      "Scheduled health checks, dependency updates, and bug fixes.",
    color: "text-tropical-300",
    icon: (
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
      />
    ),
  },
];

const dataSources = [
  {
    acronym: "ISTAC",
    name: "Instituto Canario de Estadistica",
    description:
      "Tourist arrivals, hotel occupancy, ADR, RevPAR, and 14 other indicators for Tenerife.",
    color: "text-ocean-400",
    borderColor: "border-ocean-500/30",
  },
  {
    acronym: "INE",
    name: "Instituto Nacional de Estadistica",
    description:
      "National tourism statistics, hotel surveys, apartment occupancy.",
    color: "text-tropical-400",
    borderColor: "border-tropical-500/30",
  },
  {
    acronym: "EGT",
    name: "Encuesta sobre Gasto Turistico",
    description:
      "Individual tourist spending surveys with demographics, accommodation, and satisfaction data.",
    color: "text-volcanic-400",
    borderColor: "border-volcanic-500/30",
  },
];

export default function AboutPage() {
  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="show"
      className="space-y-8 max-w-5xl mx-auto"
    >
      {/* Header */}
      <motion.div variants={fadeUp} className="text-center pt-4">
        <h2 className="text-3xl font-bold gradient-text">About This Project</h2>
        <p className="text-sm text-gray-500 mt-2">
          An autonomous AI experiment
        </p>
      </motion.div>

      {/* Main explanation */}
      <motion.div variants={fadeUp}>
        <Panel>
          <div className="space-y-4 text-gray-300 leading-relaxed">
            <p>
              This website is an experiment — a fully operational tourism
              intelligence platform that is{" "}
              <span className="text-white font-semibold">
                entirely built, deployed, and maintained by autonomous AI agents
              </span>{" "}
              powered by{" "}
              <a
                href="https://agentcrew.sh/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-ocean-400 hover:text-ocean-300 underline transition-colors"
              >
                AgentCrew
              </a>
              .
            </p>
            <p>
              Everything you see — from the code that renders these pages, to the
              data pipelines that fetch real tourism data, to the ML models that
              generate forecasts, to the server infrastructure and security — is
              operated by AI agents working autonomously.
            </p>
          </div>
        </Panel>
      </motion.div>

      {/* What the AI agents handle */}
      <motion.div variants={fadeUp} className="space-y-4">
        <h3 className="text-lg font-semibold text-gray-200">
          What the AI Agents Handle
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {capabilities.map(({ title, description, color, icon }) => (
            <Panel key={title}>
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <div
                    className={`w-9 h-9 rounded-lg bg-gray-800/80 flex items-center justify-center ${color} shrink-0`}
                  >
                    <svg
                      className="w-5 h-5"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      {icon}
                    </svg>
                  </div>
                  <h4 className={`text-sm font-semibold ${color}`}>{title}</h4>
                </div>
                <p className="text-xs text-gray-400 leading-relaxed">
                  {description}
                </p>
              </div>
            </Panel>
          ))}
        </div>
      </motion.div>

      {/* Real Data Sources */}
      <motion.div variants={fadeUp} className="space-y-4">
        <h3 className="text-lg font-semibold text-gray-200">
          Real Data Sources
        </h3>
        <Panel>
          <p className="text-sm text-gray-300 mb-5 leading-relaxed">
            While the platform is AI-operated, the data is{" "}
            <span className="text-white font-semibold">100% real</span>, sourced
            from official public institutions:
          </p>
          <div className="space-y-4">
            {dataSources.map(
              ({ acronym, name, description, color, borderColor }) => (
                <div
                  key={acronym}
                  className={`border-l-2 ${borderColor} pl-4 py-1`}
                >
                  <div className="flex items-baseline gap-2">
                    <span className={`text-sm font-bold ${color}`}>
                      {acronym}
                    </span>
                    <span className="text-xs text-gray-500">{name}</span>
                  </div>
                  <p className="text-xs text-gray-400 mt-1">{description}</p>
                </div>
              )
            )}
          </div>
          <p className="text-xs text-gray-500 mt-5 border-t border-gray-800/50 pt-4">
            Data is updated automatically: weekly (ISTAC/INE), bi-monthly (EGT
            microdata).
          </p>
        </Panel>
      </motion.div>

      {/* Footer links */}
      <motion.div variants={fadeUp}>
        <div className="flex items-center justify-center gap-6 py-4 text-sm">
          <span className="text-gray-500">
            Built with{" "}
            <a
              href="https://agentcrew.sh/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-ocean-400 hover:text-ocean-300 underline transition-colors"
            >
              AgentCrew
            </a>
          </span>
          <span className="text-gray-700">|</span>
          <span className="text-gray-500">
            Source code on{" "}
            <a
              href="https://github.com/barckcode/canary-tourism-demo"
              target="_blank"
              rel="noopener noreferrer"
              className="text-ocean-400 hover:text-ocean-300 underline transition-colors"
            >
              GitHub
            </a>
          </span>
        </div>
      </motion.div>
    </motion.div>
  );
}
