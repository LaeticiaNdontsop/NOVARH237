/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./*/templates/**/*.html",
    "./*/**/*.py",
    "!./venv/**",
    "!./node_modules/**",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: "#eef2ff",
          100: "#e0e7ff",
          500: "#4f46e5",
          600: "#4338ca",
          700: "#3730a3",
          900: "#1e1b4b",
        },
        // Palette de la page d'accueil publique (maquette KUMBA RH)
        kumba: {
          50: "#eff6ff",
          100: "#dbeafe",
          500: "#1a5fe6",
          600: "#0b52d9",
          700: "#0a44b3",
          900: "#0a1f4d",
        },
      },
    },
  },
  plugins: [],
};
