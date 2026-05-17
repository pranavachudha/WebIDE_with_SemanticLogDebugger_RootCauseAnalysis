/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#0d1117",
        surface: "#161b22",
        primary: "#58a6ff",
        error: "#f85149",
        text: "#c9d1d9",
        textSecondary: "#8b949e",
        border: "#30363d",
      }
    },
  },
  plugins: [],
}
