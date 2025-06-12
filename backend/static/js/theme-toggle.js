// backend/static/js/theme-toggle.js
(function() {
  const THEME_KEY = 'themePreference';
  const LIGHT_THEME = 'light';
  const DARK_THEME = 'dark';
  const themeToggleBtn = document.getElementById('theme-toggle-btn'); // Assuming a button with this ID

  function getPreferredTheme() {
    const storedTheme = localStorage.getItem(THEME_KEY);
    if (storedTheme) {
      return storedTheme;
    }
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? DARK_THEME : LIGHT_THEME;
  }

  function applyTheme(theme) {
    if (theme === DARK_THEME) {
      document.documentElement.setAttribute('data-theme', DARK_THEME);
    } else {
      document.documentElement.removeAttribute('data-theme'); // Or set to 'light'
    }
    // Update button text/icon if you have one
    if (themeToggleBtn) {
        themeToggleBtn.textContent = theme === DARK_THEME ? 'Switch to Light Mode' : 'Switch to Dark Mode';
    }
  }

  function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme') === DARK_THEME ? DARK_THEME : LIGHT_THEME;
    const newTheme = currentTheme === DARK_THEME ? LIGHT_THEME : DARK_THEME;
    localStorage.setItem(THEME_KEY, newTheme);
    applyTheme(newTheme);
  }

  // Apply theme on initial load
  const initialTheme = getPreferredTheme();
  applyTheme(initialTheme);

  // Add event listener to the toggle button
  if (themeToggleBtn) {
    themeToggleBtn.addEventListener('click', toggleTheme);
  } else {
    // Fallback: make toggleTheme globally available if button might not exist yet
    // or if you want to call it from other places.
    window.toggleTheme = toggleTheme;
    console.log("Theme toggle button with id 'theme-toggle-btn' not found. 'window.toggleTheme()' is available.");
  }
})();
