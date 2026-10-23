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
        surface: {
          950: '#050506',
          900: '#09090b',
          800: '#18181b',
          700: '#27272a',
          600: '#3f3f46',
        },
        primary: {
          400: '#818cf8',
          500: '#6366f1',
          600: '#4f46e5',
        },
        success: {
          400: '#34d399',
          500: '#10b981',
          900: '#064e3b',
        },
        danger: {
          400: '#fb7185',
          500: '#f43f5e',
          900: '#881337',
        },
        warning: {
          400: '#fbbf24',
          500: '#f59e0b',
          900: '#78350f',
        },
        info: {
          400: '#38bdf8',
          500: '#0ea5e9',
        },
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
