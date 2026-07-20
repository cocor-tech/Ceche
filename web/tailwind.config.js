/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{astro,html,js,jsx,md,mdx,ts,tsx}"],
  plugins: [require("daisyui"), require("@tailwindcss/typography")],
  daisyui: {
    themes: [
      {
        ceche: {
          "primary": "#ff8800",
          "primary-content": "#ffffff",
          "secondary": "#22c55e",
          "accent": "#ff8800",
          "neutral": "#0d120d",
          "base-100": "#050805",
          "base-200": "#0d120d",
          "base-300": "#141c14",
          "base-content": "#ffffff",
          "info": "#9ca3af",
          "success": "#22c55e",
          "warning": "#ff8800",
          "error": "#ef4444",
        },
      },
      {
        cechelight: {
          "primary": "#ff8800",
          "primary-content": "#ffffff",
          "secondary": "#22c55e",
          "accent": "#ff8800",
          "neutral": "#f8faf8",
          "base-100": "#f8faf8",
          "base-200": "#ffffff",
          "base-300": "#f0f0f0",
          "base-content": "#1a1a1a",
          "info": "#6b7280",
          "success": "#22c55e",
          "warning": "#ff8800",
          "error": "#ef4444",
        },
      },
    ],
  },
};
