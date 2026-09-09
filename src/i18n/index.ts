import i18n from 'i18next';
import { initReactI18next, useTranslation as useReactTranslation } from 'react-i18next';
import { resources, english } from './resources';

export const LOCALE_STORAGE_KEY = 'tinting-voxel.locale';
export const supportedLocales = [
  { code: 'en', label: 'English', aliases: ['en'] },
  { code: 'zh-CN', label: '简体中文', aliases: ['zh', 'zh-hans'] },
] as const;
export type Locale = typeof supportedLocales[number]['code'];

export function resolveLocale(preferences: readonly string[]): Locale {
  for (const preference of preferences) {
    const language = preference.toLowerCase().replace(/_/g, '-');
    const exact = supportedLocales.find(locale => locale.code.toLowerCase() === language);
    if (exact) return exact.code;
    const compatible = supportedLocales.find(locale => locale.aliases.some(alias => language === alias || language.startsWith(alias + '-')));
    if (compatible) return compatible.code;
  }
  return 'en';
}

const namespaces = Object.keys(english) as Array<keyof typeof english>;

// Resources are bundled so first render and switching never suspend the workspace.
void i18n.use(initReactI18next).init({
  resources,
  ns: namespaces,
  lng: 'en',
  fallbackLng: 'en',
  supportedLngs: supportedLocales.map(locale => locale.code),
  defaultNS: 'common',
  initAsync: false,
  interpolation: { escapeValue: false },
  react: { useSuspense: false },
});

function updateDocumentLanguage(): void {
  document.documentElement.lang = i18n.resolvedLanguage ?? 'en';
  document.documentElement.dir = i18n.dir();
  document.title = i18n.t('title', { ns: 'converter' });
}

export function initializeLocale(): void {
  let saved: string | null = null;
  try { saved = localStorage.getItem(LOCALE_STORAGE_KEY); } catch { /* Storage is optional. */ }
  const locale = supportedLocales.some(item => item.code === saved)
    ? saved as Locale
    : resolveLocale(navigator.languages?.length ? navigator.languages : [navigator.language]);
  i18n.off('languageChanged', updateDocumentLanguage);
  i18n.on('languageChanged', updateDocumentLanguage);
  void i18n.changeLanguage(locale);
  updateDocumentLanguage();
}

export function setLocale(locale: Locale): void {
  try { localStorage.setItem(LOCALE_STORAGE_KEY, locale); } catch { /* Keep switching available in private browsing. */ }
  void i18n.changeLanguage(locale);
}

export function useTranslation() {
  return useReactTranslation(namespaces);
}
export { i18n };
