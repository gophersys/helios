/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{html,js,svelte,ts}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter Variable', 'Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
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
      // ═══════════════════════════════════════════════════════════════
      // SPACING SYSTEM - 4px base unit (Tailwind default)
      // All custom spacing should align to 4px/8px grid
      // ═══════════════════════════════════════════════════════════════
      spacing: {
        // Sidebar widths (aligned to 8px grid)
        'sidebar': '256px',           // 32 * 8 = 256px (expanded)
        'sidebar-collapsed': '64px',  // 8 * 8 = 64px (collapsed)
        // Content max-widths
        'content-sm': '640px',
        'content-md': '768px',
        'content-lg': '1024px',
        'content-xl': '1280px',
        'content-2xl': '1440px',
        // Component heights (aligned to 8px grid)
        'input-sm': '32px',   // 4 * 8 = 32px
        'input-md': '40px',   // 5 * 8 = 40px
        'input-lg': '48px',   // 6 * 8 = 48px
        'btn-sm': '32px',
        'btn-md': '40px',
        'btn-lg': '48px',
        'header': '64px',     // 8 * 8 = 64px
        'card-hero': '160px', // 20 * 8 = 160px
      },
      // ═══════════════════════════════════════════════════════════════
      // TYPOGRAPHY - Major Third scale (1.25 ratio)
      // ═══════════════════════════════════════════════════════════════
      fontSize: {
        // Extra small for labels/badges
        '2xs': ['0.6875rem', { lineHeight: '1rem', letterSpacing: '0.01em' }],  // 11px
        // Standard scale with optimal line heights
        'xs': ['0.75rem', { lineHeight: '1.125rem' }],     // 12px / 18px (1.5)
        'sm': ['0.875rem', { lineHeight: '1.375rem' }],    // 14px / 22px (1.57)
        'base': ['1rem', { lineHeight: '1.5rem' }],        // 16px / 24px (1.5)
        'lg': ['1.125rem', { lineHeight: '1.75rem' }],     // 18px / 28px (1.56)
        'xl': ['1.25rem', { lineHeight: '1.875rem' }],     // 20px / 30px (1.5)
        '2xl': ['1.5rem', { lineHeight: '2rem' }],         // 24px / 32px (1.33)
        '3xl': ['1.875rem', { lineHeight: '2.25rem' }],    // 30px / 36px (1.2)
        '4xl': ['2.25rem', { lineHeight: '2.5rem' }],      // 36px / 40px (1.11)
      },
      // ═══════════════════════════════════════════════════════════════
      // BORDER RADIUS - Consistent scale
      // ═══════════════════════════════════════════════════════════════
      borderRadius: {
        'none': '0',
        'sm': '4px',
        DEFAULT: '6px',
        'md': '8px',
        'lg': '12px',
        'xl': '16px',
        '2xl': '24px',
        'full': '9999px',
      },
      // ═══════════════════════════════════════════════════════════════
      // BOX SHADOWS
      // ═══════════════════════════════════════════════════════════════
      boxShadow: {
        'xs': '0 1px 2px 0 rgba(0,0,0,0.05)',
        'card': '0 1px 3px 0 rgba(0,0,0,0.06), 0 1px 2px -1px rgba(0,0,0,0.04)',
        'card-hover': '0 4px 16px 0 rgba(0,0,0,0.08), 0 2px 4px -1px rgba(0,0,0,0.05)',
        'elevated': '0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -2px rgba(0,0,0,0.1)',
        'modal': '0 20px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.1)',
        'glow': '0 0 20px var(--card-glow)',
        'card-dark': '0 1px 4px 0 rgba(0,0,0,0.3), 0 0 0 1px rgba(255,255,255,0.03)',
        'card-dark-hover': '0 4px 16px 0 rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.05)',
      },
      // ═══════════════════════════════════════════════════════════════
      // TRANSITIONS
      // ═══════════════════════════════════════════════════════════════
      transitionDuration: {
        DEFAULT: '150ms',
        'fast': '100ms',
        'normal': '200ms',
        'slow': '300ms',
      },
      transitionTimingFunction: {
        'smooth': 'cubic-bezier(0.4, 0, 0.2, 1)',
      },
      // ═══════════════════════════════════════════════════════════════
      // ANIMATIONS
      // ═══════════════════════════════════════════════════════════════
      keyframes: {
        'fade-in': {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in-up': {
          from: { opacity: '0', transform: 'translateY(8px)' },
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
        'slide-in-right': {
          from: { transform: 'translateX(100%)' },
          to: { transform: 'translateX(0)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 0.2s ease-out',
        'fade-in-up': 'fade-in-up 0.3s ease-out',
        'overlay-in': 'overlay-in 150ms ease-out',
        'modal-in': 'modal-in 200ms ease-out',
        'slide-in-right': 'slide-in-right 0.3s ease-out',
      },
      // ═══════════════════════════════════════════════════════════════
      // MAX WIDTHS
      // ═══════════════════════════════════════════════════════════════
      maxWidth: {
        'prose': '65ch',
        'form': '480px',
      },
      // ═══════════════════════════════════════════════════════════════
      // Z-INDEX SCALE
      // ═══════════════════════════════════════════════════════════════
      zIndex: {
        'dropdown': '50',
        'sticky': '100',
        'fixed': '200',
        'modal-backdrop': '300',
        'modal': '400',
        'popover': '500',
        'tooltip': '600',
      },
    },
  },
  plugins: [],
};
