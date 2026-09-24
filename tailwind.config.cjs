/** @type {import('tailwindcss').Config} */
const token = (name) => `rgb(var(--${name}) / <alpha-value>)`;

module.exports = {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      // Print-shop palette: paper stock, ink, and the process inks the app
      // separates images into. Values live in src/index.css.
      colors: {
        paper: { DEFAULT: token('paper'), raised: token('paper-raised'), sunk: token('paper-sunk') },
        ink: { DEFAULT: token('ink'), soft: token('ink-soft'), muted: token('ink-muted') },
        rule: { DEFAULT: token('rule'), strong: token('rule-strong') },
        cyan: { DEFAULT: token('cyan') },
        magenta: { DEFAULT: token('magenta'), deep: token('magenta-deep') },
        yellow: { DEFAULT: token('yellow') },
        signal: { error: token('error'), ok: token('ok'), warn: token('warn') },
      },
      fontFamily: {
        sans: ['"Archivo Variable"', '"PingFang SC"', '"Hiragino Sans GB"', '"Noto Sans SC"', '"Microsoft YaHei"', 'system-ui', 'sans-serif'],
        mono: ['"DM Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      borderRadius: { sheet: '3px' },
      boxShadow: {
        sheet: '0 1px 0 rgb(var(--rule)), 0 18px 40px -28px rgb(var(--ink) / 0.45)',
        lift: '0 10px 24px -16px rgb(var(--ink) / 0.5)',
      },
    },
  },
};
