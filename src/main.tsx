import React from 'react';
import ReactDOM from 'react-dom/client';
import Converter from './pages/Converter';
import '@fontsource-variable/archivo/wdth.css';
import '@fontsource/dm-mono/400.css';
import '@fontsource/dm-mono/500.css';
import './index.css';
import { i18n, initializeLocale } from './i18n';
import { initializeBugReportDiagnostics } from './utils/bugReport';
import { initializeTelemetry } from './utils/telemetry';

initializeLocale();
initializeBugReportDiagnostics();
initializeTelemetry(i18n.resolvedLanguage ?? 'en');

ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
        <Converter />
    </React.StrictMode>,
);
