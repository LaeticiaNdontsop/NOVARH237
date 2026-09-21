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
        // Palette NOVA RH (bleu des maquettes)
        primary: {
          50: "#eff6ff",
          100: "#dbeafe",
          200: "#bfdbfe",
          500: "#1a5fe6",
          600: "#0b52d9",
          700: "#0a44b3",
          800: "#0a3585",
          900: "#0a1f4d",
          950: "#071740",
        },
      },
    },
  },
  plugins: [],
};
