/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        sidebar: {
          DEFAULT: '#1a1a2e',
          dark: '#0f0f1a',
          light: '#252542',
          border: '#2a2a45',
        },
        primary: {
          DEFAULT: '#f5a623',
          dark: '#e09000',
          light: '#ffb84d',
          50: '#fff8eb',
          100: '#ffecc7',
          500: '#f5a623',
          600: '#e09000',
          700: '#c27800',
        },
        accent: {
          DEFAULT: '#3b82f6',
          dark: '#2563eb',
          light: '#60a5fa',
        },
        surface: {
          DEFAULT: '#f5f5f5',
          card: '#ffffff',
          muted: '#e5e5e5',
        },
      },
      backgroundImage: {
        'header-gradient': 'linear-gradient(135deg, #8B6914 0%, #5C4A0F 50%, #3D310A 100%)',
        'header-gradient-light': 'linear-gradient(135deg, #C4A035 0%, #8B6914 50%, #5C4A0F 100%)',
      },
      boxShadow: {
        'card': '0 2px 8px rgba(0, 0, 0, 0.08)',
        'card-hover': '0 4px 16px rgba(0, 0, 0, 0.12)',
      },
    },
  },
  plugins: [],
}
