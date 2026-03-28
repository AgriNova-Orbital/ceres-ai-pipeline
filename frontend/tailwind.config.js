/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: "#185574",
        "primary-dark": "#143d5a",
      },
    },
  },
  plugins: [],
};
