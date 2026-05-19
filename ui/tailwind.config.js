/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          primary: '#0a0e17',
          secondary: '#111827',
          tertiary: '#1f2937',
        },
        accent: {
          green: '#10b981',
          red: '#ef4444',
          yellow: '#f59e0b',
          blue: '#3b82f6',
          purple: '#8b5cf6',
        },
        text: {
          primary: '#f9fafb',
          secondary: '#9ca3af',
          muted: '#6b7280',
        },
        border: {
          default: '#1f2937',
          active: '#374151',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
}
