/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        primary: '#1E3A5F',
        accent: '#FF6B6B',
        success: '#10B981',
        warning: '#F59E0B',
        muted: '#6B7280',
      },
      boxShadow: {
        card: '0 10px 30px rgba(30, 58, 95, 0.08)',
      },
    },
  },
  plugins: [],
}
