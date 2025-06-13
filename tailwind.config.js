/** @type {import('tailwindcss').Config} */
module.exports = {
   darkMode: 'class', // Enable dark mode based on the 'data-theme' attribute

  content: [
    './backend/templates/**/*.html',
    './backend/static/src/**/*.js', // If you plan to use JS to manipulate classes
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
