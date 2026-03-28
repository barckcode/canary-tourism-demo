import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { stagger, fadeUp } from "../utils/animations";
import Panel from "../components/layout/Panel";

export default function AboutPage() {
  const { t } = useTranslation();

  const capabilities = [
    {
      titleKey: "about.capDevelopmentTitle",
      descKey: "about.capDevelopmentDesc",
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
      titleKey: "about.capDataPipelinesTitle",
      descKey: "about.capDataPipelinesDesc",
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
      titleKey: "about.capMLTitle",
      descKey: "about.capMLDesc",
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
      titleKey: "about.capInfraTitle",
      descKey: "about.capInfraDesc",
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
      titleKey: "about.capSecurityTitle",
      descKey: "about.capSecurityDesc",
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
      titleKey: "about.capMonitoringTitle",
      descKey: "about.capMonitoringDesc",
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
      descKey: "about.istacDesc",
      color: "text-ocean-400",
      borderColor: "border-ocean-500/30",
    },
    {
      acronym: "INE",
      name: "Instituto Nacional de Estadistica",
      descKey: "about.ineDesc",
      color: "text-tropical-400",
      borderColor: "border-tropical-500/30",
    },
    {
      acronym: "EGT",
      name: "Encuesta sobre Gasto Turistico",
      descKey: "about.egtDesc",
      color: "text-volcanic-400",
      borderColor: "border-volcanic-500/30",
    },
  ];

  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="show"
      className="space-y-8 max-w-5xl mx-auto"
    >
      {/* Header */}
      <motion.div variants={fadeUp} className="text-center pt-4">
        <h1 className="text-3xl font-bold gradient-text">{t('about.title')}</h1>
        <p className="text-sm text-gray-400 mt-2">
          {t('about.subtitle')}
        </p>
      </motion.div>

      {/* Main explanation */}
      <motion.div variants={fadeUp}>
        <Panel>
          <div className="space-y-4 text-gray-300 leading-relaxed">
            <p>
              {t('about.introP1')}{" "}
              <span className="text-white font-semibold">
                {t('about.introHighlight')}
              </span>{" "}
              {t('about.introPoweredBy')}{" "}
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
              {t('about.introP2')}
            </p>
          </div>
        </Panel>
      </motion.div>

      {/* What the AI agents handle */}
      <motion.div variants={fadeUp} className="space-y-4">
        <h3 className="text-lg font-semibold text-gray-200">
          {t('about.whatAgentsHandle')}
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {capabilities.map(({ titleKey, descKey, color, icon }) => (
            <Panel key={titleKey}>
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
                      aria-hidden="true"
                    >
                      {icon}
                    </svg>
                  </div>
                  <h4 className={`text-sm font-semibold ${color}`}>{t(titleKey)}</h4>
                </div>
                <p className="text-xs text-gray-400 leading-relaxed">
                  {t(descKey)}
                </p>
              </div>
            </Panel>
          ))}
        </div>
      </motion.div>

      {/* Real Data Sources */}
      <motion.div variants={fadeUp} className="space-y-4">
        <h3 className="text-lg font-semibold text-gray-200">
          {t('about.realDataSources')}
        </h3>
        <Panel>
          <p className="text-sm text-gray-300 mb-5 leading-relaxed">
            {t('about.realDataIntro')}{" "}
            <span className="text-white font-semibold">{t('about.realDataHighlight')}</span>
            {t('about.realDataIntroEnd')}
          </p>
          <div className="space-y-4">
            {dataSources.map(
              ({ acronym, name, descKey, color, borderColor }) => (
                <div
                  key={acronym}
                  className={`border-l-2 ${borderColor} pl-4 py-1`}
                >
                  <div className="flex items-baseline gap-2">
                    <span className={`text-sm font-bold ${color}`}>
                      {acronym}
                    </span>
                    <span className="text-xs text-gray-400">{name}</span>
                  </div>
                  <p className="text-xs text-gray-400 mt-1">{t(descKey)}</p>
                </div>
              )
            )}
          </div>
          <p className="text-xs text-gray-400 mt-5 border-t border-gray-800/50 pt-4">
            {t('about.dataUpdateSchedule')}
          </p>
        </Panel>
      </motion.div>

      {/* Footer links */}
      <motion.div variants={fadeUp}>
        <div className="flex items-center justify-center gap-6 py-4 text-sm">
          <span className="text-gray-400">
            {t('about.builtWith')}{" "}
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
          <span className="text-gray-400">
            {t('about.sourceCodeOn')}{" "}
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
