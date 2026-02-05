/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/**/*.{js,jsx,ts,tsx}',
    './index.html',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter Variable', 'Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      colors: {
        surface: {
          0: 'var(--surface-0)',
          1: 'var(--surface-1)',
          2: 'var(--surface-2)',
          3: 'var(--surface-3)',
        },
        border: {
          DEFAULT: 'var(--border)',
          subtle: 'var(--border-subtle)',
        },
        text: {
          primary: 'var(--text-primary)',
          secondary: 'var(--text-secondary)',
          tertiary: 'var(--text-tertiary)',
        },
        accent: {
          DEFAULT: 'var(--accent)',
          hover: 'var(--accent-hover)',
          muted: 'var(--accent-muted)',
          subtle: 'var(--accent-subtle)',
        },
        sidebar: {
          bg: 'var(--sidebar-bg)',
          active: 'var(--sidebar-active-bg)',
          'active-border': 'var(--sidebar-active-border)',
          hover: 'var(--sidebar-hover-bg)',
        },
        success: {
          DEFAULT: 'var(--success)',
          muted: 'var(--success-muted)',
        },
        warning: {
          DEFAULT: 'var(--warning)',
          hover: 'var(--warning-hover)',
          muted: 'var(--warning-muted)',
        },
        error: {
          DEFAULT: 'var(--error)',
          hover: 'var(--error-hover)',
          muted: 'var(--error-muted)',
        },
        info: {
          DEFAULT: 'var(--info)',
          muted: 'var(--info-muted)',
        },
        overlay: 'var(--overlay)',
        'card-glow': 'var(--card-glow)',
      },
      spacing: {
        sidebar: '260px',
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
      },
      boxShadow: {
        'card': '0 1px 3px 0 rgba(0,0,0,0.06), 0 1px 2px -1px rgba(0,0,0,0.04)',
        'card-hover': '0 4px 16px 0 rgba(0,0,0,0.08), 0 2px 4px -1px rgba(0,0,0,0.05)',
        'glow': '0 0 20px var(--card-glow)',
        'card-dark': '0 1px 4px 0 rgba(0,0,0,0.3), 0 0 0 1px rgba(255,255,255,0.03)',
        'card-dark-hover': '0 4px 16px 0 rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.05)',
      },
      transitionDuration: {
        DEFAULT: '150ms',
      },
      borderRadius: {
        DEFAULT: '8px',
      },
      keyframes: {
        'fade-in': {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'overlay-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        'modal-in': {
          from: { opacity: '0', transform: 'scale(0.97)' },
          to: { opacity: '1', transform: 'scale(1)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 0.3s ease-out',
        'overlay-in': 'overlay-in 150ms ease-out',
        'modal-in': 'modal-in 200ms ease-out',
      },
    },
  },
  plugins: [],
};
