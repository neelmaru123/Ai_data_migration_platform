/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        accent: {
          DEFAULT: "var(--accent-primary)",
          hover: "var(--accent-primary-hover)",
          light: "var(--accent-light)",
          dark: "var(--accent-dark)",
        },
        brand: {
          primary: "#38bdf8",
          hover: "#0ea5e9",
        },
      },
      borderColor: {
        glass: "var(--glass-border)",
        "glass-hover": "var(--glass-border-hover)",
      },
    },
  },
  plugins: [],
};
