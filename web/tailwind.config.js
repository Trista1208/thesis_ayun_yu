/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ayun: {
          green: "#2e7d52",
          dark: "#1a4d35",
          light: "#eef7f1",
          muted: "#5a6356",
        },
        ink: "#2c2c2c",
        rule: "#e5e0d8",
      },
      fontFamily: {
        sans: ["DM Sans", "system-ui", "sans-serif"],
        serif: ["Libre Baskerville", "Georgia", "serif"],
      },
    },
  },
  plugins: [],
};
