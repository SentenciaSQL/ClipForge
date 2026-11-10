/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{html,ts}'],
  theme: {
    extend: {
      colors: {
        canvas: '#0b0d12',
        panel: '#12151d',
        panelElevated: '#181c27',
        line: '#2a3142',
        ink: '#e8ecf5',
        muted: '#939bb0',
        accent: '#3dd6c6',
        accentSoft: '#1f6f68',
        warn: '#f0b429',
        danger: '#ff5c7a',
      },
      fontFamily: {
        display: ['"Space Grotesk"', 'Segoe UI', 'sans-serif'],
        body: ['"IBM Plex Sans"', 'Segoe UI', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'Consolas', 'monospace'],
      },
      boxShadow: {
        glow: '0 0 0 1px rgba(61, 214, 198, 0.18), 0 18px 40px rgba(0, 0, 0, 0.35)',
      },
    },
  },
  plugins: [],
};
