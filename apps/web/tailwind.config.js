/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          'var(--font-inter)',
          '-apple-system',
          'BlinkMacSystemFont',
          'SF Pro Display',
          'SF Pro Text',
          'Helvetica Neue',
          'Helvetica',
          'Arial',
          'sans-serif',
        ],
        mono: [
          'SF Mono',
          'Menlo',
          'Monaco',
          'Cascadia Mono',
          'Consolas',
          'Courier New',
          'monospace',
        ],
      },
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
