/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'bleu-orange': '#007BFF', // Ton bleu signature pour le projet
      },
    },
  },
  plugins: [],
}