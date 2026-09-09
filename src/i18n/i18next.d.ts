import 'i18next';
import type { english } from './resources';

declare module 'i18next' {
  interface CustomTypeOptions {
    defaultNS: 'common';
    resources: typeof english;
    returnNull: false;
    strictKeyChecks: true;
  }
}
