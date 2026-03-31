import { useEffect } from "react";
import { useTranslation } from "react-i18next";

/**
 * Sets `document.title` to the translated value of `titleKey` suffixed with
 * the application name. Restores the base title on unmount.
 */
export function usePageTitle(titleKey: string) {
  const { t } = useTranslation();

  useEffect(() => {
    const pageName = t(titleKey);
    document.title = `${pageName} - Tenerife Tourism Intelligence`;

    return () => {
      document.title = "Tenerife Tourism Intelligence";
    };
  }, [t, titleKey]);
}
