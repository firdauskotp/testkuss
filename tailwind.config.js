/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './backend/templates/**/*.html',
    './backend/static/src/**/*.js', // If you plan to use JS to manipulate classes
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
