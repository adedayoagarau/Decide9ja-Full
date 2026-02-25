/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        'c-red': 'var(--c-red)',
        'c-blue': 'var(--c-blue)',
        'c-green': 'var(--c-green)',
        'c-yellow': 'var(--c-yellow)',
        'c-beige': 'var(--c-beige)',
        'c-brown': 'var(--c-brown)',
        'c-black': 'var(--c-black)',
        'c-border': 'var(--c-border)',
      },
      fontFamily: {
        display: ['system-ui', '-apple-system', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'monospace'],
      },
    },
  },
  plugins: [],
}
