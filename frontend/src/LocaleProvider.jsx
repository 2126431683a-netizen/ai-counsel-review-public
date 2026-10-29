import { useEffect, useMemo, useState } from 'react';
import { I18nContext, translate } from './i18n';

const LANGUAGE_STORAGE_KEY = 'the-ai-counsel-ui-language';

function getInitialLanguage() {
  try {
    const saved = localStorage.getItem(LANGUAGE_STORAGE_KEY);
    return ['zh-CN', 'zh-TW', 'en'].includes(saved) ? saved : 'zh-CN';
  } catch {
    return 'zh-CN';
  }
}

export default function LocaleProvider({ children }) {
  const [language, setLanguage] = useState(getInitialLanguage);

  useEffect(() => {
    document.documentElement.lang = language;
    try {
      localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
    } catch {
      // Keep the selected language for this session when storage is unavailable.
    }
  }, [language]);

  const context = useMemo(() => ({
    language,
    setLanguage,
    t: (source, values) => translate(source, language, values),
  }), [language]);

  return <I18nContext.Provider value={context}>{children}</I18nContext.Provider>;
}
