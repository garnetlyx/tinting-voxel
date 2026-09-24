import { Languages } from 'lucide-react';
import { setLocale, supportedLocales, useTranslation, type Locale } from '../i18n';
import { track } from '../utils/telemetry';

export function LanguageSelector() {
  const { t, i18n } = useTranslation();
  return (
    <label className="inline-flex shrink-0 items-center gap-1.5 rounded-sheet border border-rule-strong bg-paper-raised px-2 py-1.5 text-sm text-ink transition-colors focus-within:border-ink hover:border-ink">
      <Languages className="h-4 w-4 text-ink-muted" aria-hidden="true" />
      <select
        aria-label={t('common:language')}
        value={i18n.resolvedLanguage ?? 'en'}
        onChange={event => {
          setLocale(event.target.value as Locale);
          track('language_changed', { locale: event.target.value });
        }}
        className="min-w-0 cursor-pointer bg-transparent focus:outline-none"
      >
        {supportedLocales.map(locale => <option key={locale.code} value={locale.code} lang={locale.code}>{locale.label}</option>)}
      </select>
    </label>
  );
}
