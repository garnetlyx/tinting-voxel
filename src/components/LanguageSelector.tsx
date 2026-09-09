import { Languages } from 'lucide-react';
import { setLocale, supportedLocales, useTranslation, type Locale } from '../i18n';

export function LanguageSelector() {
  const { t, i18n } = useTranslation();
  return (
    <label className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-sm text-gray-700">
      <Languages className="h-4 w-4" aria-hidden="true" />
      <select
        aria-label={t('common:language')}
        value={i18n.resolvedLanguage ?? 'en'}
        onChange={event => setLocale(event.target.value as Locale)}
        className="min-w-0 bg-transparent focus:outline-purple-600"
      >
        {supportedLocales.map(locale => <option key={locale.code} value={locale.code} lang={locale.code}>{locale.label}</option>)}
      </select>
    </label>
  );
}
