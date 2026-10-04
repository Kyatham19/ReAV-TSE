/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: '#09090b',
        surface: '#111116',
        'surface-elevated': '#181820',
        'surface-border': 'rgba(255, 255, 255, 0.08)',
        'surface-border-hover': 'rgba(255, 255, 255, 0.16)',
        accent: {
          DEFAULT: '#8b5cf6', // Violet
          hover: '#9d75f7',
          muted: 'rgba(139, 92, 246, 0.15)',
          glow: 'rgba(139, 92, 246, 0.3)',
        },
        lavender: {
          400: '#a78bfa',
          300: '#c4b5fd',
          200: '#ddd6fe',
        }
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        display: ['Plus Jakarta Sans', 'Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      animation: {
        'pulse-subtle': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow-pulse': 'glow 2.5s ease-in-out infinite',
      },
      keyframes: {
        glow: {
          '0%, 100%': { opacity: '0.4' },
          '50%': { opacity: '0.8' },
        }
      }
    },
  },
  plugins: [],
}
