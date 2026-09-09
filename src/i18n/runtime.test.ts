import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { i18n, initializeLocale, LOCALE_STORAGE_KEY, resolveLocale, setLocale, supportedLocales } from './index';
import { english, resources } from './resources';

beforeEach(() => {
  localStorage.clear();
  vi.spyOn(navigator, 'languages', 'get').mockReturnValue(['en-US']);
  initializeLocale();
});
afterEach(() => { vi.restoreAllMocks(); setLocale('en'); localStorage.clear(); });

describe('locale resolution and persistence', () => {
  it.each([
    [['zh-CN'], 'zh-CN'], [['zh_Hans_CN'], 'zh-CN'], [['zh-TW'], 'zh-CN'],
    [['en-GB', 'zh-CN'], 'en'], [['fr-FR', 'zh-SG'], 'zh-CN'], [['fr'], 'en'], [[], 'en'],
  ] as const)('resolves %j to %s', (preferences, expected) => {
    expect(resolveLocale(preferences)).toBe(expected);
  });

  it('uses the browser preference until a user chooses a language', () => {
    vi.spyOn(navigator, 'languages', 'get').mockReturnValue(['zh-CN']);
    initializeLocale();
    expect(i18n.resolvedLanguage).toBe('zh-CN');
    expect(document.documentElement.lang).toBe('zh-CN');
    expect(document.title).toContain('图片转 STL');
    setLocale('en');
    initializeLocale();
    expect(i18n.resolvedLanguage).toBe('en');
    expect(localStorage.getItem(LOCALE_STORAGE_KEY)).toBe('en');
    expect(document.title).toContain('Image to STL');
  });

  it('ignores an unsupported stored preference', () => {
    localStorage.setItem(LOCALE_STORAGE_KEY, 'invalid-locale');
    vi.spyOn(navigator, 'languages', 'get').mockReturnValue(['zh-CN']);
    initializeLocale();
    expect(i18n.resolvedLanguage).toBe('zh-CN');
  });

  it('works when browser storage is unavailable', () => {
    vi.spyOn(localStorage, 'getItem').mockImplementation(() => { throw new Error('Unavailable'); });
    vi.spyOn(localStorage, 'setItem').mockImplementation(() => { throw new Error('Unavailable'); });
    expect(() => initializeLocale()).not.toThrow();
    expect(() => setLocale('zh-CN')).not.toThrow();
    expect(document.documentElement.lang).toBe('zh-CN');
  });
});

describe('translation contracts', () => {
  it('registers every available language resource', () => {
    expect(supportedLocales.map(locale => locale.code).sort()).toEqual(Object.keys(resources).sort());
  });

  it('has matching namespaces, keys and interpolation parameters', () => {
    const parameters = (value: string) => [...value.matchAll(/{{\s*([^},]+)(?:,[^}]+)?}}/g)].map(match => match[1]).sort();
    for (const [locale, translation] of Object.entries(resources)) {
      expect(Object.keys(translation).sort(), locale).toEqual(Object.keys(english).sort());
      for (const namespace of Object.keys(english) as Array<keyof typeof english>) {
        const source = english[namespace] as Record<string, string>;
        const target = translation[namespace] as Record<string, string>;
        expect(Object.keys(target).sort(), `${locale}:${namespace}`).toEqual(Object.keys(source).sort());
        for (const key of Object.keys(source)) {
          expect(target[key].trim(), `${locale}:${namespace}:${key}`).not.toBe('');
          expect(parameters(target[key]), `${locale}:${namespace}:${key}`).toEqual(parameters(source[key]));
        }
      }
    }
  });

  it('formats counts and plural forms using the selected language', () => {
    const englishT = i18n.getFixedT('en', 'common');
    const chineseT = i18n.getFixedT('zh-CN', 'common');
    expect(englishT('pixels', { count: 1 })).toBe('1 pixel');
    expect(englishT('pixels', { count: 1250000 })).toBe('1,250,000 pixels');
    expect(chineseT('pixels', { count: 1250000 })).toBe('1,250,000 像素');
  });

  it('falls back to English for a missing translation', () => {
    const isolated = i18n.cloneInstance({ lng: 'zh-CN', forkResourceStore: true });
    isolated.removeResourceBundle('zh-CN', 'common');
    expect(isolated.getFixedT('zh-CN', 'common')('cancel')).toBe('Cancel');
    expect(i18n.getFixedT('zh-CN', 'common')('cancel')).toBe('取消');
  });
});
